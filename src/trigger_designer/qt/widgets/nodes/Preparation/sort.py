from functools import partial
import pprint
from typing import Dict, Optional, List, Any, TYPE_CHECKING
from qtpy.QtWidgets import (
    QWidget,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLayout,
    QComboBox,
    QLineEdit,
    QLabel,
    QHBoxLayout,
)
from qtpy.QtGui import QIcon, QPixmap
from qtpy.QtCore import Qt, Signal
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
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from trigger_designer.qt.widgets.common import EmptyStateLabel
from nodeeditor.utils import dumpException
import polars as pl

if TYPE_CHECKING:
    from trigger_designer.qt.node_base import TriggerNode


class SortContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """
    Content widget for sort node that allows users to sort data by multiple columns.

    This class provides a user interface for creating sort conditions with multiple
    columns and sort orders (ascending/descending). Uses Polars for data processing.

    Attributes:
        evaluate: Qt signal emitted when sort configuration changes
        sort_data: List of sort conditions with column and order information
        row_widgets: Dictionary tracking UI widgets for each sort row
        next_row_id: Unique identifier counter for sort rows
        incoming_variable: Name of the incoming data variable
        incom_data: The incoming polars DataFrame
        data: Processed DataFrame with sorting applied
        variable_name: Variable name for the output
    """

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        # local variables
        self.sort_data: List[Dict[str, str]] = []
        # Store references to row widgets with their indices
        self.row_widgets: Dict[int, Dict[str, Any]] = {}
        self.next_row_id: int = 0  # Unique identifier for each row

        self.history = self.node.scene.history
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        # incoming variables
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.LazyFrame] = None

        # pass on variables
        self.data: Optional[pl.LazyFrame] = None
        self.variable_name: str = f"var_sort_{self.id}"

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> QLayout:
        """
        Create the basic layout for sort node with sorting conditions.

        Args:
            dock_layout: The layout to add components to

        Returns:
            The updated dock layout
        """
        if self.incom_data is None:
            dock_layout.addWidget(EmptyStateLabel())
            return dock_layout

        # Get column names from LazyFrame
        try:
            column_names = self.incom_data.columns
        except Exception:
            # If we can't get columns, show error
            error_label = QLabel("Error: Unable to read column information")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("color: red;")
            dock_layout.addWidget(error_label)
            return dock_layout

        main_layout = QVBoxLayout()
        self.sort_layout = QVBoxLayout()

        # Create rows based on saved sort_data or add initial row if none exists
        if self.sort_data:
            # Create rows for each saved sort condition
            for sort_item in self.sort_data:
                self.add_sort_row(restore_data=sort_item)
        else:
            # Add default first row if no saved data
            self.add_sort_row()

        # Add row for the add button
        add_btn = QPushButton()
        add_btn.setIcon(QIcon(self.node.rsm.get("icon_add")))
        add_btn.setToolTip("Add sort key")
        add_btn.setFixedWidth(30)
        add_btn.clicked.connect(self.add_sort_row)

        main_layout.addLayout(self.sort_layout)
        main_layout.addWidget(add_btn)
        main_layout.addStretch()

        dock_layout.addLayout(main_layout)
        self.recursively_find_widgets(dock_layout)
        return dock_layout

    def add_sort_row(self, restore_data: Optional[Dict[str, str]] = None) -> None:
        """
        Add a new sort row with column selector and order selector.

        Args:
            restore_data: Optional data to restore when loading from saved state
        """
        if not restore_data and not self.history.is_restoring_history:
            # Store old state before adding new row
            old_state = {"sort_data": [item.copy() for item in self.sort_data]}

        row_layout = QHBoxLayout()
        column_selector = QComboBox()

        # Get column names from LazyFrame
        if self.incom_data is not None:
            column_selector.addItems(self.incom_data.columns)

        row_id = self.next_row_id
        self.next_row_id += 1

        # Add column selector
        column_selector.currentTextChanged.connect(
            partial(self.on_column_changed, row_id)
        )
        row_layout.addWidget(column_selector)

        # Add order selector
        order_selector = QComboBox()
        order_selector.addItems(["Ascending", "Descending"])
        order_selector.currentTextChanged.connect(
            partial(self.on_order_changed, row_id)
        )
        row_layout.addWidget(order_selector)

        # Add remove button
        remove_button = QPushButton()
        remove_button.setIcon(QIcon(self.node.rsm.get("icon_remove")))
        remove_button.setToolTip("Remove sort key")
        remove_button.setMaximumWidth(30)
        remove_button.clicked.connect(partial(self.remove_sort_row, row_id))
        row_layout.addWidget(remove_button)

        # Store references to widgets and their layout
        self.row_widgets[row_id] = {
            "layout": row_layout,
            "column_selector": column_selector,
            "order_selector": order_selector,
            "remove_button": remove_button,
            "index": self.sort_layout.count(),
        }

        if restore_data:
            # Restoring existing data
            column_selector.setCurrentText(restore_data["column"])
            order_selector.setCurrentText(restore_data["order"])
        else:
            new_sort_item = {
                "column": column_selector.currentText(),
                "order": order_selector.currentText(),
            }
            self.sort_data.append(new_sort_item)

        self.sort_layout.addLayout(row_layout)

        if not restore_data and not self.history.is_restoring_history:
            new_state = {"sort_data": [item.copy() for item in self.sort_data]}
            self.store_history(old_state, new_state)
            self.evaluate.emit()

    def on_column_changed(self, row_id: int, text: str) -> None:
        """
        Handle column selection changes with history tracking.

        Args:
            row_id: Unique identifier for the sort row
            text: Selected column name
        """
        if self.history.is_restoring_history:
            return

        # Store old state
        old_state = {"sort_data": [item.copy() for item in self.sort_data]}

        # Get current column value
        row_index = self.row_widgets[row_id]["index"]
        old_column = self.sort_data[row_index]["column"]

        # Only update if value actually changed
        if old_column != text:
            self.sort_data[row_index]["column"] = text
            new_state = {"sort_data": [item.copy() for item in self.sort_data]}
            self.store_history(old_state, new_state)
            self.evaluate.emit()

    def on_order_changed(self, row_id: int, text: str) -> None:
        """
        Handle sort order changes with history tracking.

        Args:
            row_id: Unique identifier for the sort row
            text: Selected sort order (Ascending/Descending)
        """
        if self.history.is_restoring_history:
            return

        # Store old state
        old_state = {"sort_data": [item.copy() for item in self.sort_data]}

        # Get current order value
        row_index = self.row_widgets[row_id]["index"]
        old_order = self.sort_data[row_index]["order"]

        # Only update if value actually changed
        if old_order != text:
            self.sort_data[row_index]["order"] = text
            new_state = {"sort_data": [item.copy() for item in self.sort_data]}
            self.store_history(old_state, new_state)
            self.evaluate.emit()

    def remove_sort_row(self, row_id: int) -> None:
        """
        Remove a sort row with history tracking.

        Args:
            row_id: Unique identifier for the sort row to remove
        """
        if self.history.is_restoring_history or row_id not in self.row_widgets:
            return

        # Store old state before removal
        old_state = {"sort_data": [item.copy() for item in self.sort_data]}

        # Get the widgets for this row
        row = self.row_widgets[row_id]
        row_layout = row["layout"]
        row_index = row["index"]

        # Remove the corresponding data
        self.sort_data.pop(row_index)

        # Clean up widgets
        while row_layout.count():
            widget = row_layout.itemAt(0).widget()
            if widget:
                widget.deleteLater()
            row_layout.removeItem(row_layout.itemAt(0))

        # Remove the layout from parent layout
        self.sort_layout.removeItem(row_layout)

        # Remove from our tracking dict
        del self.row_widgets[row_id]

        # Update indices for remaining rows
        for row in self.row_widgets.values():
            if row["index"] > row_index:
                row["index"] -= 1

        # Store new state after removal
        new_state = {"sort_data": [item.copy() for item in self.sort_data]}

        # Store history only if there was a change
        self.store_history(old_state, new_state)
        self.evaluate.emit()

    def history_stamp_callback(
        self, history_data: Dict[str, Any], is_undo: bool
    ) -> None:
        """
        Callback for undo/redo operations to restore sort configuration.

        Args:
            history_data: Dictionary containing old and new states
            is_undo: True if this is an undo operation, False for redo
        """
        try:
            self.history.is_restoring_history = True

            # Get the appropriate state
            if is_undo:
                state = history_data["old_state"]
            else:
                state = history_data["new_state"]

            # Block signals during restoration
            self.blockSignals(True)
            try:
                # Store current rows before clearing
                current_row_ids = list(self.row_widgets.keys())

                # Remove all existing rows first
                for row_id in current_row_ids:
                    row = self.row_widgets[row_id]
                    row_layout = row["layout"]

                    # Clean up widgets
                    while row_layout.count():
                        item = row_layout.itemAt(0)
                        if item:
                            widget = item.widget()
                            if widget:
                                widget.deleteLater()
                            row_layout.removeItem(item)

                    # Remove layout
                    if self.sort_layout.indexOf(row_layout) >= 0:
                        self.sort_layout.removeItem(row_layout)

                # Clear the tracking dict
                self.row_widgets.clear()
                self.next_row_id = 0
                self.sort_data.clear()

                # Rebuild rows from stored state
                for sort_item in state["sort_data"]:
                    self.add_sort_row(restore_data=sort_item)

            finally:
                self.blockSignals(False)

            self.evaluate.emit()

        finally:
            self.history.is_restoring_history = False

    def store_history(
        self, old_state: Dict[str, Any], new_state: Dict[str, Any]
    ) -> None:
        """
        Store history data for undo/redo only if states are different.

        Args:
            old_state: Previous state before changes
            new_state: New state after changes
        """
        if self.history.is_restoring_history:
            return

        # Compare states
        if old_state["sort_data"] != new_state["sort_data"]:
            history_data = {
                "node": self.node,
                "old_state": old_state,
                "new_state": new_state,
            }

            self.history.storeHistory(
                desc="Sort Configuration Changed", data=history_data, setModified=True
            )

    def get_code(self) -> str:
        """
        Generate Python code for the sort operation using Polars.

        Returns:
            String containing the generated Python code for sorting
        """

        if self.incoming_variable is None or self.incoming_variable == "":
            return "print('''No Incoming Variable for sort''')\n"

        if not self.sort_data:
            return f"{self.variable_name} = {self.incoming_variable}\n"

        sort_conditions = []
        for item in self.sort_data:
            if item["column"]:  # Only add if column is selected
                # Convert to polars sort format: column name and descending flag
                descending = item["order"] == "Descending"
                sort_conditions.append((item["column"], descending))

        if not sort_conditions:
            return f"{self.variable_name} = {self.incoming_variable}\n"

        # Build polars sort expression
        code_lines = []
        if len(sort_conditions) == 1:
            # Single column sort
            column, descending = sort_conditions[0]
            code_lines.append(
                f"{self.variable_name} = {self.incoming_variable}.sort('{column}', descending={descending})"
            )
        else:
            # Multiple column sort
            columns = [f"{col}" for col, _ in sort_conditions]
            descending_flags = [desc for _, desc in sort_conditions]
            code_lines.append(
                f"{self.variable_name} = {self.incoming_variable}.sort({columns}, descending={descending_flags})"
            )

        return "\n".join(code_lines) + "\n"

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the sort content to a dictionary.

        Returns:
            Dictionary containing serialized sort configuration
        """
        res = super().serialize()
        res["sort_data"] = self.sort_data
        return res

    def deserialize(self, data: Dict[str, Any], hashmap: Dict[str, Any] = {}) -> bool:
        """
        Deserialize sort content from a dictionary.

        Args:
            data: Dictionary containing serialized data
            hashmap: Hash map for object references

        Returns:
            True if deserialization was successful
        """
        res = super().deserialize(data, hashmap)

        self.sort_data = data.get("sort_data", [])

        try:
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(PreparationNodes.SORT, NodeTypes.PREPARATION)
class TriggerNode_Sort(TriggerNode):
    """
    A node for sorting data by multiple columns in ascending or descending order.

    This node allows users to configure multiple sort conditions with different
    columns and sort orders. Uses Polars for efficient data sorting operations.

    Attributes:
        icon: Icon identifier for the node
        node_code: Unique code identifying this node type
        node_type: Category of the node (PREPARATION)
        node_title: Display title for the node
        content_label_objname: Object name for the content widget
        style: Visual styling options
    """

    icon = "node_sort"
    node_code = PreparationNodes.SORT
    node_type = NodeTypes.PREPARATION
    node_title = "Sort"
    content_label_objname = "trigger_node_sort"
    style = {}

    def __init__(self, scene) -> None:
        """
        Initialize the sort node.

        Args:
            scene: The node editor scene containing this node
        """
        super().__init__(scene, inputs=[1], outputs=[3])

    def initInnerClasses(self) -> None:
        """
        Initialize the inner classes for the sort node.

        Sets up the content widget, graphics node, and connects signals.
        """
        self.content: SortContent = SortContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: List[Dict[str, Any]] = []

    def processInputs(
        self, input_values: List[List[Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Process input data and apply sort operations.

        Takes incoming data and applies the configured sort conditions using Polars.

        Args:
            input_values: List of input values from connected nodes

        Returns:
            List containing dictionary with processed data and variable name,
            or None if no valid input is available
        """
        # Only one input for simplicity
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            # Custom processing logic for the Sort node
            self.content.incom_data = input_value.get("data")
            self.content.incoming_variable = input_value.get("variable_name")
            # Real lazy sort so previews match the generated code.
            incom = self.content.incom_data
            sort_items = [s for s in self.content.sort_data if s.get("column")]
            if incom is not None and sort_items:
                try:
                    incom = incom.sort(
                        [s["column"] for s in sort_items],
                        descending=[
                            s["order"] == "Descending" for s in sort_items
                        ],
                    )
                except Exception:
                    pass
            self.content.data = incom
            self.evalChildren()
            self.param = [
                {"data": self.content.data, "variable_name": self.content.variable_name}
            ]
            return self.param
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Input is not connected")
            return None

    def get_code(self) -> str:
        """
        Get the generated code for this sort node.

        Returns:
            String containing the Python code for the sort operation
        """
        return self.content.get_code()
