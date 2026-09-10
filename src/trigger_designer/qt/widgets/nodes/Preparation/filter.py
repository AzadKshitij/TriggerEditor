from typing import Optional, Union
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
    QHBoxLayout,
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
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from trigger_designer.qt.widgets.common import EmptyStateLabel
from nodeeditor.utils_no_qt import dumpException
from loguru import logger
import polars as pl


class FilterContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """
    Content widget for filter node that provides UI for filtering data based on column values.

    This class handles the user interface and logic for filtering incoming data using various
    comparison operations. It supports filtering with different data types and operations
    like equals, contains, greater than, etc.

    Attributes:
        evaluate: Qt signal emitted when filter settings change and evaluation is needed
        column: The column name to filter on
        operation: The filter operation (Equals, Contains, etc.)
        value: The value to filter against
        incoming_variable: Name of the incoming data variable
        incom_data: The incoming polars DataFrame
        data: Filtered data (true results)
        f_data: Filtered data (false results)
        variable_name: Variable name for true filter results
        f_variable_name: Variable name for false filter results
    """

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(
        self, node: "TriggerNode", parent: Optional[QDMNodeIconContentWidget] = None
    ) -> None:
        super().__init__(node, parent)
        # local variables
        # self.column: str = None
        self.column: Optional[str] = None
        # self.column: str = ""
        self.operation: str = "Equals"
        self.value: Union[str, float, int] = ""
        self.history = self.node.scene.history

        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        # incoming variables
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame] = None

        # pass on variables
        self.data: Optional[pl.DataFrame] = None
        self.f_data: Optional[pl.DataFrame] = None
        self.variable_name = f"var_t_filter_{self.id}"
        self.f_variable_name = f"var_f_filter_{self.id}"

    @property
    def node(self) -> "TriggerNode":
        """Get the associated trigger node."""
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        """Set the associated trigger node."""
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        """
        Initialize the user interface for the filter content widget.

        Args:
            icon_: Optional pixmap icon for the node
        """
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        """
        Create the layout for the filter content widget.

        Sets up UI components including column selector, operation selector,
        and value input field. If no data is available, shows appropriate message.

        Args:
            dock_layout: The layout to add components to
        """

        if self.incom_data is None:
            dock_layout.addWidget(EmptyStateLabel())
            # return layout
        else:
            main_layout = QVBoxLayout()

            # Create filter container
            filter_layout = QHBoxLayout()

            # Column selector combobox
            self.column_selector = QComboBox()
            self.column_selector.setObjectName("columnSelector")
            self.column_selector.setMinimumWidth(100)

            # Operation selector combobox
            self.operation_selector = QComboBox()
            self.operation_selector.setObjectName("operationSelector")
            # Operations will be populated dynamically based on selected column type

            # Value input line edit
            self.value_input = QLineEdit()
            self.value_input.setObjectName("valueInput")
            self.value_input.setPlaceholderText("Enter filter value...")

            # Initialize default values after creating widgets
            # self.column = self.column_selector.currentText()
            # self.operation = self.operation_selector.currentText()
            # self.value = self.value_input.text()

            self.update_columns()

            # Add widgets to filter layout
            main_layout.addWidget(self.column_selector)
            main_layout.addWidget(self.operation_selector)
            main_layout.addWidget(self.value_input)

            main_layout.addStretch()

            main_layout.addLayout(filter_layout)
            dock_layout.addLayout(main_layout)

            self.recursively_find_widgets(dock_layout)

        # Connect signals
        self.column_selector.currentTextChanged.connect(self.on_column_changed)
        self.operation_selector.currentTextChanged.connect(self.on_filter_changed)
        self.value_input.textChanged.connect(self.on_filter_changed)  # return layout

    def _get_column_type_category(self, column_name: str) -> str:
        """
        Determine the category of a column based on its data type.

        Args:
            column_name: Name of the column to check

        Returns:
            Category string: 'numeric', 'string', 'date', or 'other'
        """
        if self.incom_data is None or column_name not in self.incom_data.columns:
            return "other"

        col_dtype = self.incom_data[column_name].dtype

        # Numeric types
        if col_dtype in [
            pl.Float32,
            pl.Float64,
            pl.Int8,
            pl.Int16,
            pl.Int32,
            pl.Int64,
            pl.UInt8,
            pl.UInt16,
            pl.UInt32,
            pl.UInt64,
        ]:
            return "numeric"
        # String types
        elif col_dtype in [pl.Utf8, pl.String]:
            return "string"
        # Date/time types
        elif col_dtype in [pl.Date, pl.Datetime, pl.Time, pl.Duration]:
            return "date"
        # Other types (Boolean, List, Struct, etc.)
        else:
            return "other"

    def _update_operations_for_column_type(self, column_type: str) -> None:
        """
        Update the operation selector based on the column data type.

        Args:
            column_type: The category of the column ('numeric', 'string', 'date', 'other')
        """
        # Block signals to prevent triggering changes during update
        self.operation_selector.blockSignals(True)

        # Clear existing operations
        self.operation_selector.clear()

        # Add operations based on column type
        if column_type == "numeric":
            operations = [
                "Equals",
                "Not Equals",
                "Less Than",
                "Greater Than",
                "Less Than or Equal",
                "Greater Than or Equal",
            ]
        elif column_type == "string":
            operations = ["Equals", "Not Equals", "Contains"]
        elif column_type == "date":
            operations = [
                "Equals",
                "Not Equals",
                "Less Than",
                "Greater Than",
                "Less Than or Equal",
                "Greater Than or Equal",
            ]
        else:  # other types (Boolean, List, Struct, etc.)
            operations = ["Equals", "Not Equals"]

        # Add the operations to the selector
        self.operation_selector.addItems(operations)

        # Restore the previously selected operation if it's still available
        if hasattr(self, "operation") and self.operation:
            index = self.operation_selector.findText(self.operation)
            if index >= 0:
                self.operation_selector.setCurrentIndex(index)
            else:
                # If previous operation is not available, select the first one
                self.operation_selector.setCurrentIndex(0)
                self.operation = self.operation_selector.currentText()

        # Unblock signals
        self.operation_selector.blockSignals(False)

    def on_column_changed(self) -> None:
        """
        Handle column selection changes.

        Updates available operations based on the selected column's data type,
        then triggers the general filter change handling.
        """
        if hasattr(self, "column_selector") and self.incom_data is not None:
            selected_column = self.column_selector.currentText()
            if selected_column:
                # Get the column type category and update operations
                column_type = self._get_column_type_category(selected_column)
                self._update_operations_for_column_type(column_type)

        # Now handle the filter change as usual
        self.on_filter_changed()

    def update_data(self) -> None:
        """
        Update the filtered data based on current filter settings.

        Applies the selected filter operation to the incoming data and creates
        both true and false result datasets. Uses polars for data processing.
        """
        if self.incom_data is not None:
            if self.column and self.operation and self.value:
                try:
                    print("Updating data with filter settings:")
                    # Get column data type for value conversion
                    col_dtype = self.incom_data[self.column].dtype

                    # Convert value based on column type
                    if col_dtype in [
                        pl.Float32,
                        pl.Float64,
                        pl.Int8,
                        pl.Int16,
                        pl.Int32,
                        pl.Int64,
                        pl.UInt8,
                        pl.UInt16,
                        pl.UInt32,
                        pl.UInt64,
                    ]:
                        converted_value = float(self.value)
                    else:
                        # For string, date, and other types - let polars handle the conversion
                        converted_value = self.value

                    # Apply filter based on operation using polars expressions
                    # Since operations are now filtered by column type, we don't need type validation
                    if self.operation == "Equals":
                        filter_expr = pl.col(self.column) == converted_value
                    elif self.operation == "Not Equals":
                        filter_expr = pl.col(self.column) != converted_value
                    elif self.operation == "Contains":
                        # Only available for string columns, so no type check needed
                        filter_expr = pl.col(self.column).str.contains(converted_value)
                    elif self.operation == "Less Than":
                        filter_expr = pl.col(self.column) < converted_value
                    elif self.operation == "Greater Than":
                        filter_expr = pl.col(self.column) > converted_value
                    elif self.operation == "Less Than or Equal":
                        filter_expr = pl.col(self.column) <= converted_value
                    elif self.operation == "Greater Than or Equal":
                        filter_expr = pl.col(self.column) >= converted_value
                    else:
                        raise ValueError(f"Unsupported operation: {self.operation}")

                    # Apply the filter for true and false results
                    self.data = self.incom_data.filter(filter_expr)
                    self.f_data = self.incom_data.filter(~filter_expr)

                except Exception as e:
                    logger.error(f"Filter error: {str(e)}")
                    self.data = None
                    self.f_data = None
            else:
                print(
                    "Filter settings are incomplete. Please select a column, operation, and value."
                )
                self.data = None
                self.f_data = None

    def update_columns(self) -> None:
        """
        Update the column selector with available columns from incoming data.

        Populates the column selector combobox with column names from the
        incoming DataFrame and restores previously selected values if they exist.
        """
        if self.incom_data is not None:
            self.column_selector.clear()
            self.column_selector.addItems(list(self.incom_data.columns))

            # Block signals during initial setup
            self.column_selector.blockSignals(True)
            self.operation_selector.blockSignals(True)
            self.value_input.blockSignals(True)

            # Apply stored settings if they exist
            if hasattr(self, "column") and self.column:
                index = self.column_selector.findText(self.column)
                if index >= 0:
                    self.column_selector.setCurrentIndex(index)
                else:
                    self.column = self.column_selector.currentText()
            else:
                # Set default column if none selected
                if self.column_selector.count() > 0:
                    self.column = self.column_selector.currentText()

            # Update operations based on selected column type
            if self.column:
                column_type = self._get_column_type_category(self.column)
                self._update_operations_for_column_type(column_type)

            # Apply stored operation if it exists and is available
            if hasattr(self, "operation") and self.operation:
                index = self.operation_selector.findText(self.operation)
                if index >= 0:
                    self.operation_selector.setCurrentIndex(index)
                else:
                    # If stored operation is not available, select the first one
                    if self.operation_selector.count() > 0:
                        self.operation_selector.setCurrentIndex(0)
                        self.operation = self.operation_selector.currentText()

            if hasattr(self, "value"):
                self.value_input.setText(self.value)

            # Unblock signals
            self.column_selector.blockSignals(False)
            self.operation_selector.blockSignals(False)
            self.value_input.blockSignals(False)

    def on_filter_changed(self) -> None:
        """
        Handle changes to filter settings.

        Called when user modifies column selection, operation, or value.
        Updates internal state, stores history for undo/redo, and triggers
        data evaluation.
        """
        # Prevent storing history during restoration
        if self.history.is_restoring_history:
            return

        # Get current values before updating
        new_column = self.column_selector.currentText()
        new_operation = self.operation_selector.currentText()
        new_value = self.value_input.text()

        # Don't store history if nothing has changed
        if (
            new_column == self.column
            and new_operation == self.operation
            and new_value == self.value
        ):
            return

        # Store old state before changes
        old_state = {
            "column": self.column,
            "operation": self.operation,
            "value": self.value,
        }

        # Update current state
        self.column = new_column
        self.operation = new_operation
        self.value = new_value

        # Store new state
        new_state = {
            "column": self.column,
            "operation": self.operation,
            "value": self.value,
        }

        # Only store history if there are actual changes
        if old_state != new_state:
            history_data = {
                "node": self.node,
                "old_state": old_state,
                "new_state": new_state,
            }

            self.history.storeHistory(
                desc="Filter Settings Changed", data=history_data, setModified=True
            )

        self.evaluate.emit()
        self.update_data()

    def history_stamp_callback(self, history_data, is_undo: bool) -> None:
        """
        Callback for undo/redo operations.

        Restores filter state from history data when undo or redo operations
        are performed. Updates UI elements and data without triggering
        additional history entries.

        Args:
            history_data: Dictionary containing old and new state information
            is_undo: True for undo operations, False for redo operations
        """
        try:
            self.history.is_restoring_history = True
            if is_undo:
                # Undo operation
                state = history_data["old_state"]
            else:
                # Redo operation
                state = history_data["new_state"]

            # Update the UI elements without triggering change events
            self.column_selector.blockSignals(True)
            self.operation_selector.blockSignals(True)
            self.value_input.blockSignals(True)

            # Set the values
            if state["column"]:
                index = self.column_selector.findText(state["column"])
                if index >= 0:
                    self.column_selector.setCurrentIndex(index)
                    self.column = state["column"]

            if state["operation"]:
                index = self.operation_selector.findText(state["operation"])
                if index >= 0:
                    self.operation_selector.setCurrentIndex(index)
                    self.operation = state["operation"]

            if state["value"] is not None:
                self.value_input.setText(state["value"])
                self.value = state["value"]

            # Unblock signals
            self.column_selector.blockSignals(False)
            self.operation_selector.blockSignals(False)
            self.value_input.blockSignals(False)

            # Update the data
            self.update_data()
        finally:
            self.history.is_restoring_history = False

    def get_code(self) -> str:
        """
        Generate Python code for the filter operation.

        Creates polars-based filter code that can be executed to reproduce
        the filter operation on the data.

        Returns:
            String containing the generated Python code
        """
        if (
            self.incom_data is None
            or self.column is None
            or self.operation is None
            or self.value is None
        ):
            return "# No data or filter settings available"

        # Get column data type
        col_dtype = self.incom_data[self.column].dtype

        # Format value based on data type
        if col_dtype in [
            pl.Float32,
            pl.Float64,
            pl.Int8,
            pl.Int16,
            pl.Int32,
            pl.Int64,
            pl.UInt8,
            pl.UInt16,
            pl.UInt32,
            pl.UInt64,
        ]:
            formatted_value = self.value  # Numeric value doesn't need quotes
        elif col_dtype in [pl.Date, pl.Datetime, pl.Time, pl.Duration]:
            formatted_value = f"'{self.value}'"  # Date/time values as strings
        else:
            formatted_value = f"'{self.value}'"  # String value needs quotes

        code_lines = []

        # Generate polars filter expression
        if self.operation == "Equals":
            filter_expr = f"pl.col('{self.column}') == {formatted_value}"
        elif self.operation == "Not Equals":
            filter_expr = f"pl.col('{self.column}') != {formatted_value}"
        elif self.operation == "Contains":
            filter_expr = f"pl.col('{self.column}').str.contains('{self.value}')"
        elif self.operation == "Less Than":
            filter_expr = f"pl.col('{self.column}') < {formatted_value}"
        elif self.operation == "Greater Than":
            filter_expr = f"pl.col('{self.column}') > {formatted_value}"
        elif self.operation == "Less Than or Equal":
            filter_expr = f"pl.col('{self.column}') <= {formatted_value}"
        elif self.operation == "Greater Than or Equal":
            filter_expr = f"pl.col('{self.column}') >= {formatted_value}"
        else:
            filter_expr = f"pl.col('{self.column}') == {formatted_value}"

        code_lines.append("# Filter data into true and false results")
        code_lines.append(
            f"{self.variable_name} = {self.incoming_variable}.filter({filter_expr})"
        )
        code_lines.append(
            f"{self.f_variable_name} = {self.incoming_variable}.filter(~({filter_expr}))"
        )

        return "\n".join(code_lines) + "\n"

    def serialize(self) -> dict:
        """
        Serialize the filter content to a dictionary.

        Returns:
            Dictionary containing serialized filter settings
        """
        res = super().serialize()
        res["column"] = self.column
        res["operation"] = self.operation
        res["value"] = self.value
        return res

    def deserialize(self, data: dict, hashmap: dict = {}) -> bool:
        """
        Deserialize filter content from a dictionary.

        Args:
            data: Dictionary containing serialized data
            hashmap: Hash map for object references

        Returns:
            True if deserialization was successful
        """
        res = super().deserialize(data, hashmap)

        try:
            # Get stored settings individually
            self.column = data.get("column", "")
            self.operation = data.get("operation", "")
            self.value = data.get("value", "")
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(PreparationNodes.FILTER, NodeTypes.PREPARATION)
class TriggerNode_Filter(TriggerNode):
    """
    A node for filtering data based on column values and comparison operations.

    This node provides a user interface for applying filters to incoming data.
    It supports various comparison operations (equals, contains, greater than, etc.)
    and produces two outputs: filtered data (true results) and excluded data (false results).

    Attributes:
        icon: Icon identifier for the node
        node_code: Unique code identifying this node type
        node_type: Category of the node (PREPARATION)
        node_title: Display title for the node
        content_label_objname: Object name for the content widget
        style: Visual styling options
    """

    icon = "node_filter"
    node_code = PreparationNodes.FILTER
    node_type = NodeTypes.PREPARATION
    node_title = "Filter"
    content_label_objname = "trigger_node_filter"
    style = {}

    def __init__(self, scene) -> None:
        """
        Initialize the filter node.

        Args:
            scene: The node editor scene containing this node
        """
        super().__init__(scene, inputs=[1], outputs=[3, 3], output_text=["T", "F"])
        # self.eval()
        self.markInvalid(True)

    def initInnerClasses(self) -> None:
        """
        Initialize the inner classes for the filter node.

        Sets up the content widget, graphics node, and connects signals.
        """
        self.content: FilterContent = FilterContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values: list) -> Optional[list]:
        """
        Process input data and apply filter operations.

        Takes incoming data, applies the configured filter, and produces
        two output datasets: one containing filtered results (true) and
        one containing excluded data (false).

        Args:
            input_values: List of input values from connected nodes

        Returns:
            List containing two dictionaries with filtered data and variable names,
            or None if no valid input is available
        """
        # Only one input for simplicity
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        print(
            "🐍 File: Preparation/filter.py | Line: 207 | processInputs ~ input_value",
            input_value,
        )

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            # Custom processing logic for the Filter node
            self.content.incom_data = input_value.get("data")
            self.content.incoming_variable = input_value.get("variable_name")
            self.content.update_data()
            self.param = [
                {
                    "data": self.content.data,
                    "variable_name": self.content.variable_name,
                },
                {
                    "data": self.content.f_data,
                    "variable_name": self.content.f_variable_name,
                },
            ]
            self.evalChildren()
            return self.param
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Input is not connected")
            return None

    def get_code(self) -> str:
        """
        Get the generated code for this filter node.

        Returns:
            String containing the Python code for the filter operation
        """
        return self.content.get_code()
