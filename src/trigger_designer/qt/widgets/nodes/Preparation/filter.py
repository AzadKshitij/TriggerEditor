from typing import Optional, Union
from qtpy.QtWidgets import (QWidget, QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget,
                            QTableWidgetItem, QHeaderView, QLayout, QComboBox, QLineEdit, QLabel, QHBoxLayout)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_designer.core.node_configuration import register_node, PreparationNodes, NodeTypes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException
from loguru import logger
import pandas as pd


class FilterContent(QDMNodeIconContentWidget, TriggerChangeHandler):

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node: 'TriggerNode', parent: Optional[QDMNodeIconContentWidget] = None) -> None:
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
        self.incoming_variable: str = ''
        self.incom_data: Optional[pd.DataFrame] = None

        # pass on variables
        self.data: Optional[pd.DataFrame] = None
        self.f_data: Optional[pd.DataFrame] = None
        self.variable_name = f'var_t_filter_{self.id}'
        self.f_variable_name = f'var_f_filter_{self.id}'

    @property
    def node(self) -> 'TriggerNode':
        return self._node

    @node.setter
    def node(self, value: 'TriggerNode') -> None:
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:

        if self.incom_data is None:
            no_data_label = QLabel("No incoming data available")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet("color: gray;")
            dock_layout.addWidget(no_data_label)
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
            self.operation_selector.addItems([
                "Equals",
                "Not Equals",
                "Contains",
                "Less Than",
                "Greater Than",
                "Less Than or Equal",
                "Greater Than or Equal"
            ])

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
            self.column_selector.currentTextChanged.connect(
                self.on_filter_changed)
            self.operation_selector.currentTextChanged.connect(
                self.on_filter_changed)
            self.value_input.textChanged.connect(self.on_filter_changed)

        # return layout

    def update_data(self) -> None:
        if self.incom_data is not None:
            if self.column and self.operation and self.value:
                try:
                    print("Updating data with default filter settings:")
                    # Get column data type
                    col_dtype = self.incom_data[self.column].dtype

                    # Convert value based on column type
                    if pd.api.types.is_numeric_dtype(col_dtype):
                        converted_value = float(self.value)
                    elif pd.api.types.is_datetime64_dtype(col_dtype):
                        converted_value = pd.to_datetime(self.value)
                    else:
                        # For string and other types
                        converted_value = str(self.value)

                    # Apply filter based on operation
                    if self.operation == "Equals":
                        mask = self.incom_data[self.column] == converted_value
                    elif self.operation == "Not Equals":
                        mask = self.incom_data[self.column] != converted_value
                    elif self.operation == "Contains" and type(converted_value) is str:
                        # Ensure the column is a string type for contains operation
                        if not pd.api.types.is_string_dtype(col_dtype):
                            raise ValueError(
                                "Contains operation only works with text columns")
                        mask = self.incom_data[self.column].str.contains(
                            converted_value, na=False)
                    elif self.operation == "Less Than":
                        if pd.api.types.is_string_dtype(col_dtype):
                            raise ValueError(
                                "Cannot perform numeric comparison on text column")
                        mask = self.incom_data[self.column] < converted_value
                    elif self.operation == "Greater Than":
                        if pd.api.types.is_string_dtype(col_dtype):
                            raise ValueError(
                                "Cannot perform numeric comparison on text column")
                        mask = self.incom_data[self.column] > converted_value
                    elif self.operation == "Less Than or Equal":
                        if pd.api.types.is_string_dtype(col_dtype):
                            raise ValueError(
                                "Cannot perform numeric comparison on text column")
                        mask = self.incom_data[self.column] <= converted_value
                    elif self.operation == "Greater Than or Equal":
                        if pd.api.types.is_string_dtype(col_dtype):
                            raise ValueError(
                                "Cannot perform numeric comparison on text column")
                        mask = self.incom_data[self.column] >= converted_value

                    # Apply the mask for true and false results
                    self.data = self.incom_data[mask]
                    self.f_data = self.incom_data[~(mask)]

                except Exception as e:
                    logger.error(f"Filter error: {str(e)}")
            else:
                print(
                    "Filter settings are incomplete. Please select a column, operation, and value.")
                self.data = None
                self.f_data = None

    def update_columns(self) -> None:
        if self.incom_data is not None:
            self.column_selector.clear()
            self.column_selector.addItems(list(self.incom_data.columns))

            # Block signals during initial setup
            self.column_selector.blockSignals(True)
            self.operation_selector.blockSignals(True)
            self.value_input.blockSignals(True)

            # Apply stored settings if they exist
            if hasattr(self, 'column'):
                index = self.column_selector.findText(self.column)
                if index >= 0:
                    self.column_selector.setCurrentIndex(index)
                    # self.column = self.column
                else:
                    self.column = self.column_selector.currentText()

            if hasattr(self, 'operation'):
                index = self.operation_selector.findText(
                    self.operation)
                if index >= 0:
                    self.operation_selector.setCurrentIndex(index)

            if hasattr(self, 'value'):
                self.value_input.setText(self.value)

            # Unblock signals
            self.column_selector.blockSignals(False)
            self.operation_selector.blockSignals(False)
            self.value_input.blockSignals(False)

    def on_filter_changed(self) -> None:
        # Prevent storing history during restoration
        if self.history.is_restoring_history:
            return

        # Get current values before updating
        new_column = self.column_selector.currentText()
        new_operation = self.operation_selector.currentText()
        new_value = self.value_input.text()

        # Don't store history if nothing has changed
        if (new_column == self.column and
            new_operation == self.operation and
                new_value == self.value):
            return

        # Store old state before changes
        old_state = {
            'column': self.column,
            'operation': self.operation,
            'value': self.value
        }

        # Update current state
        self.column = new_column
        self.operation = new_operation
        self.value = new_value

        # Store new state
        new_state = {
            'column': self.column,
            'operation': self.operation,
            'value': self.value
        }

        # Only store history if there are actual changes
        if old_state != new_state:
            history_data = {
                'node': self.node,
                'old_state': old_state,
                'new_state': new_state
            }

            self.history.storeHistory(
                desc="Filter Settings Changed",
                data=history_data,
                setModified=True
            )

        self.evaluate.emit()
        self.update_data()

    def history_stamp_callback(self, history_data, is_undo: bool) -> None:
        """Callback for undo/redo operations"""
        try:
            self.history.is_restoring_history = True
            if is_undo:
                # Undo operation
                state = history_data['old_state']
            else:
                # Redo operation
                state = history_data['new_state']

            # Update the UI elements without triggering change events
            self.column_selector.blockSignals(True)
            self.operation_selector.blockSignals(True)
            self.value_input.blockSignals(True)

            # Set the values
            if state['column']:
                index = self.column_selector.findText(state['column'])
                if index >= 0:
                    self.column_selector.setCurrentIndex(index)
                    self.column = state['column']

            if state['operation']:
                index = self.operation_selector.findText(state['operation'])
                if index >= 0:
                    self.operation_selector.setCurrentIndex(index)
                    self.operation = state['operation']

            if state['value'] is not None:
                self.value_input.setText(state['value'])
                self.value = state['value']

            # Unblock signals
            self.column_selector.blockSignals(False)
            self.operation_selector.blockSignals(False)
            self.value_input.blockSignals(False)

            # Update the data
            self.update_data()
        finally:
            self.history.is_restoring_history = False

    def get_code(self):

        if self.incom_data is None or self.column is None or self.operation is None or self.value is None:
            return "# No data or filter settings available"

        self.column = self.column
        self.operation = self.operation
        self.value = self.value

        # Get column data type
        col_dtype = self.incom_data[self.column].dtype

        # Format value based on data type
        if pd.api.types.is_numeric_dtype(col_dtype):
            formatted_value = self.value  # Numeric value doesn't need quotes
        elif pd.api.types.is_datetime64_dtype(col_dtype):
            formatted_value = f"pd.to_datetime('{self.value}')"
        else:
            formatted_value = f"'{self.value}'"  # String value needs quotes

        code_lines = []

        operations = {
            "Equals": "==",
            "Not Equals": "!=",
            "Contains": ".str.contains",
            "Less Than": "<",
            "Greater Than": ">",
            "Less Than or Equal": "<=",
            "Greater Than or Equal": ">="
        }

        if self.operation == "Contains":
            mask = f"{self.incoming_variable}['{self.column}'].str.contains('{self.value}', na=False)"
        else:
            op = operations[self.operation]
            mask = f"{self.incoming_variable}['{self.column}'] {op} {formatted_value}"

        code_lines.append(f"# Filter data into true and false results")
        code_lines.append(
            f"{self.variable_name} = {self.incoming_variable}[{mask}]")
        code_lines.append(
            f"{self.f_variable_name} = {self.incoming_variable}[~({mask})]")

        return '\n'.join(code_lines) + '\n'

    def serialize(self):
        res = super().serialize()
        res['column'] = self.column
        res['operation'] = self.operation
        res['value'] = self.value
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)

        try:
            # Get stored settings individually
            self.column = data.get('column', '')
            self.operation = data.get('operation', '')
            self.value = data.get('value', '')
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(PreparationNodes.FILTER, NodeTypes.PREPARATION)
class TriggerNode_Filter(TriggerNode):
    icon = "node_filter"
    node_code = PreparationNodes.FILTER
    node_type = NodeTypes.PREPARATION
    node_title = "Filter"
    content_label_objname = "trigger_node_filter"
    style = {}

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[
            3, 3], output_text=["T", "F"])
        # self.eval()
        self.markInvalid(True)

    def initInnerClasses(self) -> None:
        self.content: FilterContent = FilterContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values):
        # Only one input for simplicity
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        print("🐍 File: Preparation/filter.py | Line: 207 | processInputs ~ input_value", input_value)

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            # Custom processing logic for the Select node
            self.content.incom_data = input_value.get('data')
            self.content.incoming_variable = input_value.get('variable_name')
            self.content.update_data()
            self.param = [
                {
                    'data': self.content.data,
                    'variable_name': self.content.variable_name
                },
                {
                    'data': self.content.f_data,
                    'variable_name': self.content.f_variable_name
                }
            ]
            self.evalChildren()
            return self.param
        # variable = self.content.variable_name
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip('Input is not connected')
            return None

    def get_code(self):
        return self.content.get_code()
