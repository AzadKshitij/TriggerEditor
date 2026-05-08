from typing import Optional, List, Dict, Any, TYPE_CHECKING
import polars as pl
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QGroupBox,
    QLineEdit,
    QPushButton,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal, QSize, Slot
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
from nodeeditor.utils_no_qt import dumpException
from nodeeditor.node_scene_history import SceneHistory
from nodeeditor.node_scene import Scene


class UniqueContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """
    Content widget for unique node that removes duplicate rows based on selected columns.

    This class provides a user interface for selecting columns to use for uniqueness
    determination and removes duplicate rows while preserving the first occurrence.
    Uses Polars for efficient data processing with LazyFrame operations.

    Attributes:
        evaluate: Qt signal emitted when unique configuration changes
        selected_columns: List of column names selected for uniqueness check
        incoming_variable: Name of the incoming data variable
        incom_data: The incoming polars LazyFrame
        variable_name: Variable name for the output
    """

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        # Configuration variables
        self.selected_columns: list[str] = []
        self.history: SceneHistory = self.node.scene.history

        # Incoming data variables
        self.incoming_variable: str = ""
        self.incom_data: pl.DataFrame | pl.LazyFrame | None = None

        # Output variables
        self.data: pl.DataFrame | pl.LazyFrame | None = None
        self.duplicate_data: pl.DataFrame | pl.LazyFrame | None = None
        self.variable_name: str = f"var_unique_{self.id}"
        self.duplicate_variable_name: str = f"var_duplicate_{self.id}"

        # UI components
        self.search_bar: QLineEdit | None = None
        self.column_list: QListWidget | None = None
        self.all_columns: list[str] = []  # Store all available columns for filtering

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        """Initialize the user interface for the unique content widget."""
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        """
        Create the layout for the unique content widget.

        Sets up UI components for selecting columns to use for uniqueness determination.
        Shows appropriate message if no data is available.

        Args:
            dock_layout: The layout to add components to
        """
        if self.incom_data is not None:
            # Main configuration group
            config_group = QGroupBox("Unique Configuration")
            config_layout = QVBoxLayout()
            config_layout.setSpacing(10)
            config_layout.setContentsMargins(15, 15, 15, 15)

            # Instructions
            instruction_label = QLabel("Select columns to determine uniqueness:")
            instruction_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
            config_layout.addWidget(instruction_label)

            # Search bar
            search_layout = QHBoxLayout()
            search_label = QLabel("Search:")
            search_label.setStyleSheet("font-weight: normal;")
            self.search_bar = QLineEdit()
            self.search_bar.setPlaceholderText("Type to filter columns...")
            self.search_bar.textChanged.connect(self._filter_columns)
            search_layout.addWidget(search_label)
            search_layout.addWidget(self.search_bar)
            config_layout.addLayout(search_layout)

            # Selection buttons
            button_layout = QHBoxLayout()
            select_all_btn = QPushButton("Select All")
            deselect_all_btn = QPushButton("Deselect All")

            select_all_btn.clicked.connect(self._select_all_columns)
            deselect_all_btn.clicked.connect(self._deselect_all_columns)

            # # Style buttons
            # button_style = """
            #     QPushButton {
            #         padding: 6px 12px;
            #         font-size: 11px;
            #         border: 1px solid #ccc;
            #         border-radius: 4px;
            #         background-color: #f8f9fa;
            #     }
            #     QPushButton:hover {
            #         background-color: #e9ecef;
            #     }
            #     QPushButton:pressed {
            #         background-color: #dee2e6;
            #     }
            # """
            # select_all_btn.setStyleSheet(button_style)
            # deselect_all_btn.setStyleSheet(button_style)

            button_layout.addWidget(select_all_btn)
            button_layout.addWidget(deselect_all_btn)
            button_layout.addStretch()
            config_layout.addLayout(button_layout)

            # Column selection list - takes all remaining vertical space
            self.column_list = QListWidget()
            self.column_list.setSelectionMode(
                QListWidget.SelectionMode.NoSelection
            )  # Disable multi-selection highlighting
            self.column_list.itemChanged.connect(self._on_item_changed)

            self.column_list.setObjectName("UniqueContentList")
            self.column_list.setAlternatingRowColors(True)

            self._update_column_list()
            config_layout.addWidget(
                self.column_list, 1
            )  # Give it stretch factor 1 to take available space

            config_group.setLayout(config_layout)
            dock_layout.addWidget(config_group, 1)  # Take all available vertical space

            self.recursively_find_widgets(dock_layout)
        else:
            no_data_label = QLabel("No incoming data available")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet("color: gray;")
            dock_layout.addWidget(no_data_label)

    def process_data(self) -> None:
        """Build unique and duplicate outputs for the current selection."""
        if self.incom_data is None:
            self.data = None
            self.duplicate_data = None
            return

        if not self.selected_columns:
            self.data = self.incom_data
            self.duplicate_data = self.incom_data.head(0)
            return

        duplicate_expr = pl.struct(self.selected_columns).is_duplicated()
        self.data = self.incom_data.unique(
            subset=self.selected_columns,
            maintain_order=True,
        )
        self.duplicate_data = self.incom_data.filter(duplicate_expr)

    def _update_column_list(self) -> None:
        """
        Update the column list when input data changes.

        Populates the column list widget with checkboxes for each available column.
        Preserves previously selected columns when data is refreshed.
        """
        if not hasattr(self, "column_list") or self.column_list is None:
            return

        self.column_list.clear()
        if self.incom_data is not None:
            try:
                # Get column names from LazyFrame and store them
                self.all_columns = self.incom_data.columns
                self._populate_column_list(self.all_columns)
            except Exception:
                # Handle case where column names can't be accessed
                self.all_columns = []

    def _populate_column_list(self, columns: List[str]) -> None:
        """
        Populate the column list widget with the given columns.

        Args:
            columns: List of column names to display
        """
        if not hasattr(self, "column_list") or self.column_list is None:
            return

        for column in columns:
            item = QListWidgetItem(column)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )

            # Set a larger size hint for better spacing and checkbox size
            item.setSizeHint(QSize(-1, 40))  # Fixed height of 40px for better spacing

            # Check if column was previously selected
            if column in self.selected_columns:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
            self.column_list.addItem(item)

    @Slot(str)
    def _filter_columns(self, search_text: str) -> None:
        """
        Filter the column list based on search text.

        Args:
            search_text: Text to filter columns by
        """
        if not hasattr(self, "column_list") or self.column_list is None:
            return

        search_text = search_text.lower()
        if search_text:
            filtered_columns = [
                col for col in self.all_columns if search_text in col.lower()
            ]
        else:
            filtered_columns = self.all_columns.copy()

        self.column_list.clear()
        self._populate_column_list(filtered_columns)

    def _select_all_columns(self) -> None:
        """Select all currently visible columns."""
        if not hasattr(self, "column_list") or self.column_list is None:
            return

        # Get currently visible columns
        visible_columns = []
        for index in range(self.column_list.count()):
            item = self.column_list.item(index)
            if item:
                visible_columns.append(item.text())

        if visible_columns:
            old_selected = self.selected_columns.copy()

            # Add all visible columns to selection
            for column in visible_columns:
                if column not in self.selected_columns:
                    self.selected_columns.append(column)

            # Update UI
            for index in range(self.column_list.count()):
                item = self.column_list.item(index)
                if item:
                    item.setCheckState(Qt.CheckState.Checked)

            # Store history if there was a change
            if old_selected != self.selected_columns:
                self._store_selection_history(old_selected, "Select All Visible")
                self.process_data()
                self.evaluate.emit()

    def _deselect_all_columns(self) -> None:
        """Deselect all currently visible columns."""
        if not hasattr(self, "column_list") or self.column_list is None:
            return

        # Get currently visible columns
        visible_columns = []
        for index in range(self.column_list.count()):
            item = self.column_list.item(index)
            if item:
                visible_columns.append(item.text())

        if visible_columns:
            old_selected = self.selected_columns.copy()

            # Remove all visible columns from selection
            for column in visible_columns:
                if column in self.selected_columns:
                    self.selected_columns.remove(column)

            # Update UI
            for index in range(self.column_list.count()):
                item = self.column_list.item(index)
                if item:
                    item.setCheckState(Qt.CheckState.Unchecked)

            # Store history if there was a change
            if old_selected != self.selected_columns:
                self._store_selection_history(old_selected, "Deselect All Visible")
                self.process_data()
                self.evaluate.emit()

    @Slot(QListWidgetItem)
    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """
        Handle item clicks to toggle checkbox state.
        Makes the entire item clickable, not just the checkbox.

        Args:
            item: The clicked list widget item
        """
        if item and item.flags() & Qt.ItemFlag.ItemIsEnabled:
            # Toggle the checkbox state when clicking anywhere on the item
            if item.checkState() == Qt.CheckState.Checked:
                item.setCheckState(Qt.CheckState.Unchecked)
            else:
                item.setCheckState(Qt.CheckState.Checked)

    @Slot(QListWidgetItem)
    def _on_item_changed(self, item: QListWidgetItem) -> None:
        """
        Handle checkbox state changes with history tracking.

        Args:
            item: The list widget item that was changed
        """
        # Prevent storing history during restoration
        if self.history.is_restoring_history:
            return

        old_selected_columns = self.selected_columns.copy()

        if item.checkState() == Qt.CheckState.Checked:
            if item.text() not in self.selected_columns:
                self.selected_columns.append(item.text())
        else:
            if item.text() in self.selected_columns:
                self.selected_columns.remove(item.text())

        # Only store history if there was an actual change
        if old_selected_columns != self.selected_columns:
            self._store_selection_history(
                old_selected_columns, f"Column '{item.text()}' Selection Changed"
            )
            self.process_data()
            self.evaluate.emit()

    def _store_selection_history(
        self, old_selected: List[str], description: str
    ) -> None:
        """
        Store selection change in history.

        Args:
            old_selected: Previous selection state
            description: Description of the change
        """
        history_data = {
            "node": self.node,
            "old_selected_columns": old_selected,
            "new_selected_columns": self.selected_columns.copy(),
        }

        self.history.storeHistory(
            desc=description,
            data=history_data,
            setModified=True,
        )

    def history_stamp_callback(
        self, history_data: Dict[str, Any], is_undo: bool
    ) -> None:
        """
        Callback for undo/redo operations to restore column selection.

        Args:
            history_data: Dictionary containing old and new states
            is_undo: True if this is an undo operation, False for redo
        """
        try:
            self.history.is_restoring_history = True

            if is_undo:
                self.selected_columns = history_data["old_selected_columns"]
            else:
                self.selected_columns = history_data["new_selected_columns"]

            # Update UI elements if they exist
            if hasattr(self, "column_list") and self.column_list is not None:
                try:
                    self.column_list.blockSignals(True)
                    self._update_column_list()
                except RuntimeError:
                    # Widget has been deleted
                    pass
                finally:
                    try:
                        self.column_list.blockSignals(False)
                    except RuntimeError:
                        pass

            self.process_data()
            self.evaluate.emit()

        finally:
            self.history.is_restoring_history = False

    def _get_selected_columns(self) -> List[str]:
        """
        Get list of currently selected column names from the UI.

        Returns:
            List of column names that are checked in the column list
        """
        selected_columns = []
        if hasattr(self, "column_list") and self.column_list is not None:
            try:
                for index in range(self.column_list.count()):
                    item = self.column_list.item(index)
                    if item and item.checkState() == Qt.CheckState.Checked:
                        selected_columns.append(item.text())
            except RuntimeError:
                # Widget has been deleted, return stored selection
                return self.selected_columns.copy()
        return selected_columns

    def get_code(self) -> str:
        """
        Generate Python code for the unique operation using Polars.

        Returns:
            String containing the generated Python code for removing duplicates
        """
        if not self.incoming_variable:
            return ""

        if not self.selected_columns:
            return (
                "import polars as pl\n"
                f"{self.variable_name} = {self.incoming_variable}\n"
                f"{self.duplicate_variable_name} = {self.incoming_variable}.head(0)\n"
            )

        columns_list = [f'"{col}"' for col in self.selected_columns]
        columns_str = "[" + ", ".join(columns_list) + "]"
        duplicate_expr = f"pl.struct({columns_str}).is_duplicated()"
        code_lines = [
            "import polars as pl",
            f"# Split into unique and duplicate records based on: {', '.join(self.selected_columns)}",
            f"{self.variable_name} = {self.incoming_variable}.unique(subset={columns_str}, maintain_order=True)",
            f"{self.duplicate_variable_name} = {self.incoming_variable}.filter({duplicate_expr})",
        ]

        return "\n".join(code_lines) + "\n"

    def serialize(self):
        res = super().serialize()
        res["selected_columns"] = self.selected_columns
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)

        try:
            self.selected_columns = data.get("selected_columns", [])
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(PreparationNodes.UNIQUE, NodeTypes.PREPARATION)
class TriggerNode_Unique(TriggerNode):
    """
    Node for removing duplicate rows based on selected columns using Polars.

    Provides functionality to remove duplicate rows from a LazyFrame based on
    one or more selected columns. Uses Polars unique() operation for efficient
    deduplication while maintaining lazy evaluation.
    """

    icon = "node_unique"
    node_code = PreparationNodes.UNIQUE
    node_type = NodeTypes.PREPARATION
    node_title = "Unique"
    content_label_objname = "trigger_node_unique"
    style = {}

    def __init__(self, scene: "Scene") -> None:
        """Initialize the Unique node with proper scene integration."""
        super().__init__(
            scene,
            inputs=[1],
            outputs=[3, 3],
            output_text=["Unique", "Duplicates"],
        )
        self.eval()

    def initInnerClasses(self) -> None:
        """Initialize inner classes for content, graphics node and connections."""
        self.content: UniqueContent = UniqueContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: List[Dict[str, Any]] = []

    def processInputs(
        self, input_values: List[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Process incoming data and prepare for unique operation.

        Args:
            input_values: List of input data from connected nodes

        Returns:
            List containing processed data with unique operation applied
        """
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)

            # Set input data for unique processing
            self.content.incom_data = input_value.get("data")
            self.content.incoming_variable = input_value.get("variable_name")
            self.content.process_data()
            self.param = [
                {
                    "data": self.content.data,
                    "variable_name": self.content.variable_name,
                },
                {
                    "data": self.content.duplicate_data,
                    "variable_name": self.content.duplicate_variable_name,
                },
            ]
            self.evalChildren()
            return self.param
        else:
            self.markDirty(True)
            self.markInvalid(True)
            if hasattr(self, "grNode") and self.grNode is not None:
                try:
                    self.grNode.setToolTip("Input is not connected")
                except RuntimeError:
                    pass
            return [None, None]

    def get_code(self) -> str:
        """
        Get the generated Python code for the unique operation.

        Returns:
            String containing Polars code for removing duplicates
        """
        return self.content.get_code()
