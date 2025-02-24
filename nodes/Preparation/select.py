from qtpy.QtWidgets import (QLineEdit, QLayout, QVBoxLayout, QListWidget,
                            QListWidgetItem, QTableWidget, QTableWidgetItem, QCheckBox, QComboBox, QHeaderView, QPushButton)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, QSaveFile, Signal
from trigger_conf import register_node, OP_NODE_INPUT,  OP_NODE_SELECT
from trigger_node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils import dumpException

from widgets.select_table_widget import TableWidget

import pandas as pd
from themes.theme import Theme

theme = Theme()


class SelectContent(QDMNodeIconContentWidget):
    """_summary_

    Args:
        QDMNodeContentWidget (_type_): _description_

    Variables:
        columns (dict): {column_name: [is_selected, column_type, rename]}
        incoming_columns (list): [column_name]

    Extra: 

    """

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node, parent=None):
        super().__init__(node, parent)
        # local Variables
        self.old_data: dict = []
        self.table_data: list = []

        # incoming variables
        self.incoming_variable: str = ''
        self.incom_data: pd.DataFrame = None

        # pass on variables
        self.data: pd.DataFrame = None
        self.variable_name: str = f'var_select_{self.id}'

    def initUI(self):
        icon = QPixmap("Resource/icons/Preparation/Select.png")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> QLayout:
        if self.incom_data is not None:
            self.table_data = [
                {
                    'column_name': col,
                    'dtype': self.incom_data[col].dtype.name
                }
                for col in self.incom_data.columns
            ]
            # if self.old_data != {}:
            #     self.old_data = table_data

            self.table_widget = TableWidget(data=self.table_data)
            self.table_widget.dataChanged.connect(self.handleDataChanged)
            dock_layout.addWidget(self.table_widget)

        # return layout

    def handleDataChanged(self, data_):
        print("Data changed:", data_)
        # only take selected columns from incoming data
        # data_ contains (column_name, data_type, rename)
        if self.incom_data is not None:
            # Extract selected columns, their new names and data types
            selected_columns = []
            rename_mapping = {}
            dtype_mapping = {}

            for column_info in data_:
                column_name, data_type, new_name = column_info
                selected_columns.append(column_name)

                # Add to rename mapping if new name exists
                if new_name:
                    rename_mapping[column_name] = new_name

                # Add to dtype mapping if data_type exists
                if data_type:
                    dtype_mapping[column_name] = data_type

            # Select only the specified columns from incom_data
            self.data = self.incom_data[selected_columns].copy()

            # Apply data type changes if any
            for col, dtype in dtype_mapping.items():
                try:
                    if dtype in ['int64', 'int32', 'float64', 'float32']:
                        self.data[col] = pd.to_numeric(
                            self.data[col], errors='coerce')
                    self.data[col] = self.data[col].astype(
                        dtype, errors='ignore')
                except Exception as e:
                    print(
                        f"Failed to convert column {col} to {dtype}: {str(e)}")

            # Apply renaming if any
            if rename_mapping:
                self.data.rename(columns=rename_mapping, inplace=True)

            get_code = self.get_code()
            print(get_code)
            print(self.data)
            # Emit the evaluate signal
            self.evaluate.emit()

    def is_same_column(self):
        if self.old_columns.keys() == self.incoming_columns:
            return True
        else:
            # getting missing columns
            missing_columns = set(self.old_columns.keys()) - set(
                self.incoming_columns)

            return False

    def get_code(self):
        if self.data is None or self.incoming_variable is None:
            return ""

        code_lines = []

        # Get selected columns
        selected_columns = [f"'{col}'" for col in self.incom_data.columns
                            if col in self.data.columns]

        # Select columns
        columns_str = ', '.join(selected_columns)
        code_lines.append(
            f"{self.variable_name} = {self.incoming_variable}[[{columns_str}]].copy()")

        # Apply data type changes
        dtype_changes = {}
        for col in self.data.columns:
            if self.data[col].dtype != self.incom_data[col].dtype:
                dtype_changes[col] = str(self.data[col].dtype)

        if dtype_changes:
            for col, dtype in dtype_changes.items():
                if dtype in ['int64', 'int32', 'float64', 'float32']:
                    code_lines.append(
                        f"{self.variable_name}['{col}'] = pd.to_numeric({self.variable_name}['{col}'], errors='coerce')")
                code_lines.append(
                    f"{self.variable_name}['{col}'] = {self.variable_name}['{col}'].astype('{dtype}', errors='ignore')")

        # Apply column renaming if names are different
        rename_dict = {}
        for old_col in self.incom_data.columns:
            if old_col not in self.data.columns:
                new_col = next((col for col in self.data.columns
                                if self.data[col].equals(self.incom_data[old_col])), None)
                if new_col:
                    rename_dict[old_col] = new_col

        if rename_dict:
            rename_str = ', '.join(
                [f"'{old}': '{new}'" for old, new in rename_dict.items()])
            code_lines.append(
                f"{self.variable_name}.rename(columns={{{rename_str}}}, inplace=True)")

        # print('\n'.join(code_lines) + '\n')

        return '\n'.join(code_lines) + '\n'

    def serialize(self):
        res = super().serialize()
        res['old_columns'] = self.table_data
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            self.old_columns = data['old_columns']
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(OP_NODE_SELECT, "PREPARATION")
class TriggerNode_Select(TriggerNode):
    icon = "Resource/icons/Preparation/Select.png"
    op_code = OP_NODE_SELECT
    op_title = "Select"
    op_type = "PREPARATION"
    content_label_objname = "trigger_node_select"
    style = {
        'brush_color': theme.brush_color('PREPARATION')
    }

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[1])
        self.eval()

    def initInnerClasses(self):
        self.content = SelectContent(self)
        self.grNode = TriggerGraphicsNode(self)
        # self.content.edit.textChanged.connect(self.onInputChanged)

    def processInputs(self, input_values):
        input_value = input_values[0]  # Assuming single input for simplicity
        print()
        print("#############")
        print("#############")
        print(input_value)
        print("#############")
        print("#############")
        print()
        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            # Custom processing logic for the Select node
            self.content.incom_data = input_value.get('data')
            self.content.incoming_variable = input_value.get('variable_name')
            # self.content.set_table_widget()
            return {
                "data": self.content.data,
                "variable_name": self.content.variable_name
            }
        else:
            self.markDirty(True)
            self.markInvalid(True)

    def get_code(self):
        print("getting code for file select: ")
        print(self.content.get_code())
        return self.content.get_code()
