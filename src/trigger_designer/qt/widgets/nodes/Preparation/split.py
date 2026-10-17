from typing import Optional, Dict, List, Any, TYPE_CHECKING
import polars as pl
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QSpinBox,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Signal
from trigger_designer.core.node_configuration import (
    register_node,
    PreparationNodes,
    NodeTypes,
)
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerNode,
    TriggerGraphicsNode,
)
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from trigger_designer.qt.widgets.common import (
    ConfigSection,
    EmptyStateLabel,
    FormRow,
    SegmentedControl,
)
from nodeeditor.utils_no_qt import dumpException

if TYPE_CHECKING:
    from trigger_designer.qt.node_base import TriggerNode


class SplitContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """
    Split data into estimation (training) and validation (testing) datasets.

    This node provides functionality to split incoming data into two parts:
    estimation data for training models and validation data for testing.
    Supports both random and sequential splitting with configurable percentages.

    Features:
    - Configurable estimation and validation percentages
    - Random or sequential splitting modes
    - Random seed for reproducibility
    - Polars LazyFrame processing for efficiency

    Attributes:
        evaluate: Qt signal emitted when split configuration changes
        incoming_variable: Name of the incoming data variable
        incom_data: The incoming polars LazyFrame
        estimation_data: Split estimation/training data
        validation_data: Split validation/testing data
        estimation_percent: Percentage of data for estimation (training)
        random_seed: Seed for random number generation
        is_random: Whether to use random or sequential splitting
        estimation_var: Variable name for estimation output
        validation_var: Variable name for validation output
    """

    evaluate = Signal()

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        # Data tracking
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.LazyFrame] = None
        self.estimation_data: Optional[pl.LazyFrame] = None
        self.validation_data: Optional[pl.LazyFrame] = None

        # Configuration parameters
        self.estimation_percent: int = 70  # Percentage for training/estimation data
        self.random_seed: int = 42  # Random seed for reproducibility
        self.is_random: bool = True  # Random vs sequential splitting

        # Variable names for outputs
        self.estimation_var: str = f"var_estimation_{self.id}"
        self.validation_var: str = f"var_validation_{self.id}"

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        """Initialize the user interface for the split content widget."""
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        """
        Create the layout for the split content widget.

        Sets up UI components for configuring data splitting including
        estimation percentage, random seed, and split mode selection.

        Args:
            dock_layout: The layout to add components to
        """
        if self.incom_data is None:
            dock_layout.addWidget(EmptyStateLabel())
            return

        config_group = ConfigSection()
        self.split_section = config_group

        # Mode: two exclusive states, one segmented row.
        self.mode_selector = SegmentedControl(["Random", "Sequential"])
        self.mode_selector.set_value("Random" if self.is_random else "Sequential")
        self.mode_selector.changed.connect(self._on_mode_changed)
        config_group.addWidget(FormRow("Mode", self.mode_selector, label_width=88))

        # Estimation percentage; validation takes the remainder.
        self.estimation_spin = QSpinBox()
        self.estimation_spin.setRange(1, 99)
        self.estimation_spin.setValue(self.estimation_percent)
        self.estimation_spin.valueChanged.connect(self._on_estimation_changed)
        config_group.addWidget(
            FormRow("Estimation %", self.estimation_spin, label_width=88)
        )

        validation_label = QLabel(f"Validation %: {100 - self.estimation_percent}")
        validation_label.setObjectName("ConfigSectionInfo")
        self.validation_display = validation_label
        config_group.addWidget(validation_label)

        # Random seed (only enabled in random mode)
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(1, 10000)
        self.seed_spin.setValue(self.random_seed)
        self.seed_spin.setEnabled(self.is_random)
        self.seed_spin.valueChanged.connect(self._on_seed_changed)
        config_group.addWidget(FormRow("Random seed", self.seed_spin, label_width=88))

        dock_layout.addWidget(config_group)
        dock_layout.addStretch()  # Keep the section under the context strip

        self.recursively_find_widgets(dock_layout)

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        """Configuration summary for the dock context strip."""
        held_out = 100 - self.estimation_percent
        chips: list[tuple[str, str]] = [
            (f"{self.estimation_percent}% / {held_out}%", "accent")
        ]
        if self.is_random:
            chips.append((f"random \u00b7 seed {self.random_seed}", ""))
        else:
            chips.append(("sequential", ""))
        return chips, "estimation / validation"

    def get_code(self) -> str:
        """
        Generate Python code for the split operation using Polars.

        Returns:
            String containing the generated Python code for data splitting
        """
        if self.incom_data is None or not self.incoming_variable:
            # Fallback: always define both outputs so downstream code never
            # NameErrors. Wired-but-unevaluated passes everything to
            # estimation (nothing split out yet), empty to validation.
            code = ["import polars as pl"]
            if self.incoming_variable:
                code.append(f"{self.estimation_var} = {self.incoming_variable}")
                code.append(f"{self.validation_var} = {self.incoming_variable}.head(0)")
            else:
                code.append(f"{self.estimation_var} = pl.DataFrame()")
                code.append(f"{self.validation_var} = pl.DataFrame()")
            return "\n".join(code) + "\n"

        # "__split_idx" is unlikely to collide with a user column, and the
        # max()-threshold keeps the whole plan lazy (no collect needed).
        split_col = "__split_idx"
        threshold = self.estimation_percent / 100.0
        code_lines = ["import polars as pl"]

        if self.is_random:
            # Full-row shuffle by sorting on a shuffled row index: reorders
            # whole rows, so row correlation survives (per-column shuffle
            # would destroy it). Stays lazy, deterministic per seed.
            code_lines.extend(
                [
                    f"# Random split with seed {self.random_seed} (row-safe full shuffle)",
                    f"indexed_df = {self.incoming_variable}.with_row_index('{split_col}').sort(pl.col('{split_col}').shuffle(seed={self.random_seed}))",
                ]
            )
        else:
            code_lines.extend(
                [
                    f"# Sequential split - first {self.estimation_percent}% for estimation",
                    f"indexed_df = {self.incoming_variable}.with_row_index('{split_col}')",
                ]
            )

        code_lines.extend(
            [
                f"{self.estimation_var} = indexed_df.filter(pl.col('{split_col}') < pl.col('{split_col}').max() * {threshold}).drop('{split_col}')",
                f"{self.validation_var} = indexed_df.filter(pl.col('{split_col}') >= pl.col('{split_col}').max() * {threshold}).drop('{split_col}')",
            ]
        )

        return "\n".join(code_lines) + "\n"

    def _on_estimation_changed(self, value: int) -> None:
        """
        Handle estimation percentage changes with history tracking.

        Args:
            value: New estimation percentage value
        """
        if (
            hasattr(self, "history")
            and self.history
            and not self.history.is_restoring_history
        ):
            old_state = {
                "estimation_percent": self.estimation_percent,
                "random_seed": self.random_seed,
                "is_random": self.is_random,
            }

            self.estimation_percent = value

            # Update validation display
            if hasattr(self, "validation_display"):
                self.validation_display.setText(f"Validation %: {100 - value}")

            new_state = {
                "estimation_percent": self.estimation_percent,
                "random_seed": self.random_seed,
                "is_random": self.is_random,
            }

            self._store_history(old_state, new_state)
        else:
            self.estimation_percent = value
            if hasattr(self, "validation_display"):
                self.validation_display.setText(f"Validation %: {100 - value}")

        self.refresh_dock_context()
        self.evaluate.emit()

    def _on_seed_changed(self, value: int) -> None:
        """
        Handle random seed changes with history tracking.

        Args:
            value: New random seed value
        """
        if (
            hasattr(self, "history")
            and self.history
            and not self.history.is_restoring_history
        ):
            old_state = {
                "estimation_percent": self.estimation_percent,
                "random_seed": self.random_seed,
                "is_random": self.is_random,
            }

            self.random_seed = value

            new_state = {
                "estimation_percent": self.estimation_percent,
                "random_seed": self.random_seed,
                "is_random": self.is_random,
            }

            self._store_history(old_state, new_state)
        else:
            self.random_seed = value

        self.refresh_dock_context()
        self.evaluate.emit()

    def _on_mode_changed(self, value: str) -> None:
        """
        Handle split mode changes (Random vs Sequential) with history tracking.

        Args:
            value: The newly selected mode label
        """
        is_random = value == "Random"
        if is_random == self.is_random:
            return

        if (
            hasattr(self, "history")
            and self.history
            and not self.history.is_restoring_history
        ):
            old_state = {
                "estimation_percent": self.estimation_percent,
                "random_seed": self.random_seed,
                "is_random": self.is_random,
            }

            self.is_random = is_random

            # Enable/disable seed control based on random mode
            if hasattr(self, "seed_spin"):
                self.seed_spin.setEnabled(is_random)

            new_state = {
                "estimation_percent": self.estimation_percent,
                "random_seed": self.random_seed,
                "is_random": self.is_random,
            }

            self._store_history(old_state, new_state)
        else:
            self.is_random = is_random
            if hasattr(self, "seed_spin"):
                self.seed_spin.setEnabled(is_random)

        self.evaluate.emit()

    def _store_history(
        self, old_state: Dict[str, Any], new_state: Dict[str, Any]
    ) -> None:
        """
        Store history data for undo/redo operations.

        Args:
            old_state: Previous state before changes
            new_state: New state after changes
        """
        if old_state != new_state:
            history_data = {
                "node": self.node,
                "old_state": old_state,
                "new_state": new_state,
            }

            self.history.storeHistory(
                desc="Split Configuration Changed", data=history_data, setModified=True
            )

    def history_stamp_callback(
        self, history_data: Dict[str, Any], is_undo: bool
    ) -> None:
        """
        Callback for undo/redo operations to restore split configuration.

        Args:
            history_data: Dictionary containing old and new states
            is_undo: True if this is an undo operation, False for redo
        """
        with self.history.restoring(is_undo=is_undo):
            # Get the appropriate state
            if is_undo:
                state = history_data["old_state"]
            else:
                state = history_data["new_state"]

            # Update internal state
            self.estimation_percent = state["estimation_percent"]
            self.random_seed = state["random_seed"]
            self.is_random = state["is_random"]

            # Update UI components if they exist
            if hasattr(self, "estimation_spin") and self.estimation_spin is not None:
                try:
                    self.estimation_spin.blockSignals(True)
                    self.estimation_spin.setValue(self.estimation_percent)
                    self.estimation_spin.blockSignals(False)
                except RuntimeError:
                    pass

            if hasattr(self, "seed_spin") and self.seed_spin is not None:
                try:
                    self.seed_spin.blockSignals(True)
                    self.seed_spin.setValue(self.random_seed)
                    self.seed_spin.setEnabled(self.is_random)
                    self.seed_spin.blockSignals(False)
                except RuntimeError:
                    pass

            if hasattr(self, "mode_selector") and self.mode_selector is not None:
                try:
                    self.mode_selector.set_value(
                        "Random" if self.is_random else "Sequential"
                    )
                except RuntimeError:
                    pass

            if (
                hasattr(self, "validation_display")
                and self.validation_display is not None
            ):
                try:
                    self.validation_display.setText(
                        f"Validation %: {100 - self.estimation_percent}"
                    )
                except RuntimeError:
                    pass

            self.evaluate.emit()

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the split content to a dictionary.

        Returns:
            Dictionary containing serialized split configuration
        """
        res = super().serialize()
        res.update(
            {
                "estimation_percent": self.estimation_percent,
                "random_seed": self.random_seed,
                "is_random": self.is_random,
            }
        )
        return res

    def deserialize(self, data: Dict[str, Any], hashmap: Dict[str, Any] = {}) -> bool:
        """
        Deserialize split content from a dictionary.

        Args:
            data: Dictionary containing serialized data
            hashmap: Hash map for object references

        Returns:
            True if deserialization was successful
        """
        res = super().deserialize(data, hashmap)
        try:
            self.estimation_percent = data.get("estimation_percent", 70)
            self.random_seed = data.get("random_seed", 42)
            self.is_random = data.get("is_random", True)
            return True and res
        except Exception as e:
            dumpException(e)
            return res


@register_node(PreparationNodes.SPLIT, NodeTypes.PREPARATION)
class TriggerNode_Split(TriggerNode):
    """
    A node for splitting data into estimation (training) and validation (testing) datasets.

    This node provides train-test split functionality commonly used in machine learning
    workflows. Supports both random and sequential splitting with configurable percentages.
    Uses Polars for efficient data processing.

    Attributes:
        icon: Icon identifier for the node
        node_code: Unique code identifying this node type
        node_type: Category of the node (PREPARATION)
        node_title: Display title for the node
        content_label_objname: Object name for the content widget
    """

    icon = "node_split"
    node_code = PreparationNodes.SPLIT
    node_title = "Split"
    node_type = NodeTypes.PREPARATION
    content_label_objname = "trigger_node_split"

    def __init__(self, scene) -> None:
        """
        Initialize the split node.

        Args:
            scene: The node editor scene containing this node
        """
        super().__init__(scene, inputs=[1], outputs=[3, 3], output_text=["E", "V"])
        self.markInvalid(True)

    def initInnerClasses(self) -> None:
        """
        Initialize the inner classes for the split node.

        Sets up the content widget, graphics node, and connects signals.
        """
        self.content: SplitContent = SplitContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: List[Dict[str, Any]] = []

    def processInputs(
        self, input_values: List[List[Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Process input data and apply split operations.

        Takes incoming data and splits it into estimation and validation datasets
        according to the configured parameters.

        Args:
            input_values: List of input values from connected nodes

        Returns:
            List containing dictionaries with estimation and validation data,
            or None if no valid input is available
        """
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.content.incom_data = input_value.get("data")
            self.content.incoming_variable = input_value.get("variable_name")

            if self.content.incom_data is None:
                self.markDirty(True)
                self.markInvalid(True)
                self.grNode.setToolTip("Input has no data")
                return None

            # Real lazy split so previews match the generated code.
            split_col = "__split_idx"
            threshold = self.content.estimation_percent / 100.0
            if self.content.is_random:
                indexed = self.content.incom_data.with_row_index(split_col).sort(
                    pl.col(split_col).shuffle(seed=self.content.random_seed)
                )
            else:
                indexed = self.content.incom_data.with_row_index(split_col)
            self.content.estimation_data = indexed.filter(
                pl.col(split_col) < pl.col(split_col).max() * threshold
            ).drop(split_col)
            self.content.validation_data = indexed.filter(
                pl.col(split_col) >= pl.col(split_col).max() * threshold
            ).drop(split_col)

            self.param = [
                {
                    "data": self.content.estimation_data,
                    "variable_name": self.content.estimation_var,
                },
                {
                    "data": self.content.validation_data,
                    "variable_name": self.content.validation_var,
                },
            ]
            return self.param
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Input is not connected")
            return None

    def get_code(self) -> str:
        """
        Get the generated code for this split node.

        Returns:
            String containing the Python code for the split operation
        """
        return self.content.get_code()
