from typing import Optional, Dict, List, Any, TYPE_CHECKING
import polars as pl
from qtpy.QtWidgets import (QWidget, QVBoxLayout, QLabel, QGroupBox,
                            QSpinBox, QHBoxLayout, QCheckBox)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Signal, Qt
from trigger_designer.core.node_configuration import register_node, PreparationNodes, NodeTypes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
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

    def __init__(self, node: 'TriggerNode', parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)
        
        # Data tracking
        self.incoming_variable: str = ''
        self.incom_data: Optional[pl.LazyFrame] = None
        self.estimation_data: Optional[pl.LazyFrame] = None
        self.validation_data: Optional[pl.LazyFrame] = None

        # Configuration parameters
        self.estimation_percent: int = 70  # Percentage for training/estimation data
        self.random_seed: int = 42  # Random seed for reproducibility
        self.is_random: bool = True  # Random vs sequential splitting

        # Variable names for outputs
        self.estimation_var: str = f'var_estimation_{self.id}'
        self.validation_var: str = f'var_validation_{self.id}'

    @property
    def node(self) -> 'TriggerNode':
        return self._node

    @node.setter
    def node(self, value: 'TriggerNode') -> None:
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
        if self.incom_data is not None:
            # Main configuration group
            config_group = QGroupBox("Split Configuration")
            config_layout = QVBoxLayout()
            config_layout.setSpacing(8)  # Tighter spacing between elements

            # Estimation percentage
            estimation_layout = QHBoxLayout()
            estimation_layout.setContentsMargins(0, 0, 0, 0)
            estimation_label = QLabel("Estimation %:")
            self.estimation_spin = QSpinBox()
            self.estimation_spin.setRange(1, 99)
            self.estimation_spin.setValue(self.estimation_percent)
            self.estimation_spin.valueChanged.connect(self._on_estimation_changed)
            estimation_layout.addWidget(estimation_label)
            estimation_layout.addWidget(self.estimation_spin)
            
            # Show validation percentage (calculated automatically)
            validation_label = QLabel(f"Validation %: {100 - self.estimation_percent}")
            validation_label.setStyleSheet("color: #888888;")
            self.validation_display = validation_label
            estimation_layout.addWidget(validation_label)
            estimation_layout.addStretch()  # Push elements to the left
            config_layout.addLayout(estimation_layout)

            # Split mode selection
            mode_layout = QHBoxLayout()
            mode_layout.setContentsMargins(0, 0, 0, 0)
            mode_label = QLabel("Split Mode:")
            self.random_checkbox = QCheckBox("Random Split")
            self.random_checkbox.setChecked(self.is_random)
            self.random_checkbox.stateChanged.connect(self._on_random_mode_changed)
            mode_layout.addWidget(mode_label)
            mode_layout.addWidget(self.random_checkbox)
            mode_layout.addStretch()  # Push elements to the left
            config_layout.addLayout(mode_layout)

            # Random seed (only enabled if random mode is selected)
            seed_layout = QHBoxLayout()
            seed_layout.setContentsMargins(0, 0, 0, 0)
            seed_label = QLabel("Random Seed:")
            self.seed_spin = QSpinBox()
            self.seed_spin.setRange(1, 10000)
            self.seed_spin.setValue(self.random_seed)
            self.seed_spin.setEnabled(self.is_random)
            self.seed_spin.valueChanged.connect(self._on_seed_changed)
            seed_layout.addWidget(seed_label)
            seed_layout.addWidget(self.seed_spin)
            seed_layout.addStretch()  # Push elements to the left
            config_layout.addLayout(seed_layout)

            config_group.setLayout(config_layout)
            dock_layout.addWidget(config_group)
            dock_layout.addStretch()  # Push the group box to the top
            
            self.recursively_find_widgets(dock_layout)

        else:
            no_data_label = QLabel("No incoming data available")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet("color: gray;")
            dock_layout.addWidget(no_data_label)

    def get_code(self) -> str:
        """
        Generate Python code for the split operation using Polars.
        
        Returns:
            String containing the generated Python code for data splitting
        """
        if self.incom_data is None or not self.incoming_variable:
            return "# No data available for split operation\n"

        code_lines = []
        
        if self.is_random:
            # Random split using efficient shuffle and row indexing approach
            code_lines.extend([
                "import polars as pl",
                f"# Random split with seed {self.random_seed} - efficient LazyFrame approach",
                f"# Add row index and shuffle all columns",
                f"indexed_df = {self.incoming_variable}.with_columns(pl.all().shuffle(seed={self.random_seed})).with_row_index()",
                f"# Split based on row index thresholds",
                f"{self.estimation_var} = indexed_df.filter(pl.col('index') < pl.col('index').max() * {self.estimation_percent / 100.0}).drop('index')",
                f"{self.validation_var} = indexed_df.filter(pl.col('index') >= pl.col('index').max() * {self.estimation_percent / 100.0}).drop('index')"
            ])
        else:
            # Sequential split - no shuffling, just slice based on row count
            code_lines.extend([
                "import polars as pl",
                f"# Sequential split - first {self.estimation_percent}% for estimation",
                f"indexed_df = {self.incoming_variable}.with_row_index()",
                f"{self.estimation_var} = indexed_df.filter(pl.col('index') < pl.col('index').max() * {self.estimation_percent / 100.0}).drop('index')",
                f"{self.validation_var} = indexed_df.filter(pl.col('index') >= pl.col('index').max() * {self.estimation_percent / 100.0}).drop('index')"
            ])
        
        return "\n".join(code_lines) + "\n"

    def _on_estimation_changed(self, value: int) -> None:
        """
        Handle estimation percentage changes with history tracking.
        
        Args:
            value: New estimation percentage value
        """
        if hasattr(self, 'history') and self.history and not self.history.is_restoring_history:
            old_state = {
                'estimation_percent': self.estimation_percent,
                'random_seed': self.random_seed,
                'is_random': self.is_random
            }
            
            self.estimation_percent = value
            
            # Update validation display
            if hasattr(self, 'validation_display'):
                self.validation_display.setText(f"Validation %: {100 - value}")
            
            new_state = {
                'estimation_percent': self.estimation_percent,
                'random_seed': self.random_seed,
                'is_random': self.is_random
            }
            
            self._store_history(old_state, new_state)
        else:
            self.estimation_percent = value
            if hasattr(self, 'validation_display'):
                self.validation_display.setText(f"Validation %: {100 - value}")
                
        self.evaluate.emit()

    def _on_seed_changed(self, value: int) -> None:
        """
        Handle random seed changes with history tracking.
        
        Args:
            value: New random seed value
        """
        if hasattr(self, 'history') and self.history and not self.history.is_restoring_history:
            old_state = {
                'estimation_percent': self.estimation_percent,
                'random_seed': self.random_seed,
                'is_random': self.is_random
            }
            
            self.random_seed = value
            
            new_state = {
                'estimation_percent': self.estimation_percent,
                'random_seed': self.random_seed,
                'is_random': self.is_random
            }
            
            self._store_history(old_state, new_state)
        else:
            self.random_seed = value
            
        self.evaluate.emit()

    def _on_random_mode_changed(self, state: int) -> None:
        """
        Handle random mode checkbox changes with history tracking.
        
        Args:
            state: Checkbox state (0=unchecked, 2=checked)
        """
        is_random = state == 2  # Qt.CheckState.Checked == 2
        
        if hasattr(self, 'history') and self.history and not self.history.is_restoring_history:
            old_state = {
                'estimation_percent': self.estimation_percent,
                'random_seed': self.random_seed,
                'is_random': self.is_random
            }
            
            self.is_random = is_random
            
            # Enable/disable seed control based on random mode
            if hasattr(self, 'seed_spin'):
                self.seed_spin.setEnabled(is_random)
            
            new_state = {
                'estimation_percent': self.estimation_percent,
                'random_seed': self.random_seed,
                'is_random': self.is_random
            }
            
            self._store_history(old_state, new_state)
        else:
            self.is_random = is_random
            if hasattr(self, 'seed_spin'):
                self.seed_spin.setEnabled(is_random)
                
        self.evaluate.emit()

    def _store_history(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> None:
        """
        Store history data for undo/redo operations.
        
        Args:
            old_state: Previous state before changes
            new_state: New state after changes
        """
        if old_state != new_state:
            history_data = {
                'node': self.node,
                'old_state': old_state,
                'new_state': new_state
            }

            self.history.storeHistory(
                desc="Split Configuration Changed",
                data=history_data,
                setModified=True
            )

    def history_stamp_callback(self, history_data: Dict[str, Any], is_undo: bool) -> None:
        """
        Callback for undo/redo operations to restore split configuration.
        
        Args:
            history_data: Dictionary containing old and new states
            is_undo: True if this is an undo operation, False for redo
        """
        try:
            self.history.is_restoring_history = True

            # Get the appropriate state
            if is_undo:
                state = history_data['old_state']
            else:
                state = history_data['new_state']

            # Update internal state
            self.estimation_percent = state['estimation_percent']
            self.random_seed = state['random_seed']
            self.is_random = state['is_random']

            # Update UI components if they exist
            if hasattr(self, 'estimation_spin') and self.estimation_spin is not None:
                try:
                    self.estimation_spin.blockSignals(True)
                    self.estimation_spin.setValue(self.estimation_percent)
                    self.estimation_spin.blockSignals(False)
                except RuntimeError:
                    pass

            if hasattr(self, 'seed_spin') and self.seed_spin is not None:
                try:
                    self.seed_spin.blockSignals(True)
                    self.seed_spin.setValue(self.random_seed)
                    self.seed_spin.setEnabled(self.is_random)
                    self.seed_spin.blockSignals(False)
                except RuntimeError:
                    pass

            if hasattr(self, 'random_checkbox') and self.random_checkbox is not None:
                try:
                    self.random_checkbox.blockSignals(True)
                    self.random_checkbox.setChecked(self.is_random)
                    self.random_checkbox.blockSignals(False)
                except RuntimeError:
                    pass

            if hasattr(self, 'validation_display') and self.validation_display is not None:
                try:
                    self.validation_display.setText(f"Validation %: {100 - self.estimation_percent}")
                except RuntimeError:
                    pass

            self.evaluate.emit()

        finally:
            self.history.is_restoring_history = False

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the split content to a dictionary.
        
        Returns:
            Dictionary containing serialized split configuration
        """
        res = super().serialize()
        res.update({
            'estimation_percent': self.estimation_percent,
            'random_seed': self.random_seed,
            'is_random': self.is_random
        })
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
            self.estimation_percent = data.get('estimation_percent', 70)
            self.random_seed = data.get('random_seed', 42)
            self.is_random = data.get('is_random', True)
            return True & res
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
        super().__init__(scene, inputs=[1], outputs=[3, 3], output_text=['E', 'V'])
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

    def processInputs(self, input_values: List[List[Any]]) -> Optional[List[Dict[str, Any]]]:
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
            self.markDirty(False)
            self.markInvalid(False)

            self.content.incom_data = input_value.get('data')
            self.content.incoming_variable = input_value.get('variable_name')
            
            # Set the data references for outputs (LazyFrames will be processed in generated code)
            self.content.estimation_data = self.content.incom_data
            self.content.validation_data = self.content.incom_data

            self.evalChildren()
            self.param = [
                {
                    'data': self.content.estimation_data,
                    'variable_name': self.content.estimation_var
                },
                {
                    'data': self.content.validation_data,
                    'variable_name': self.content.validation_var
                }
            ]
            return self.param
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip('Input is not connected')
            return [None, None]

    def get_code(self) -> str:
        """
        Get the generated code for this split node.
        
        Returns:
            String containing the Python code for the split operation
        """
        return self.content.get_code()
