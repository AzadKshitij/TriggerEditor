from qtpy.QtWidgets import (QLineEdit, QLayout, QVBoxLayout, QListWidget,
                            QListWidgetItem, QTableWidget, QTableWidgetItem, QCheckBox, QComboBox, QHeaderView, QPushButton)
from qtpy.QtCore import Qt, QSaveFile
from trigger_conf import register_node, OP_NODE_INPUT,  OP_NODE_SELECT
from trigger_node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.utils import dumpException

from widgets.select_table_widget import TableWidget

import pandas as pd
from themes.theme import Theme

theme = Theme()


class SelectContent(QDMNodeContentWidget):
    """_summary_

    Args:
        QDMNodeContentWidget (_type_): _description_

    Variables:
        columns (dict): {column_name: [is_selected, column_type, rename]}
        incoming_columns (list): [column_name]

    Extra: 

    """

    def initUI(self):
        # local Variables
        self.old_data: dict = []
        self.table_data: list = []

        # incoming variables
        self.incoming_variable: str = ''
        self.incom_data: pd.DataFrame = None

        # pass on variables
        self.data: pd.DataFrame = None
        self.variable_name: str = f'var_select_{self.id}'

    def create_layout(self) -> QLayout:
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

        layout = QVBoxLayout()
        layout.addWidget(self.table_widget)

        return layout

    def is_same_column(self):
        if self.old_columns.keys() == self.incoming_columns:
            return True
        else:
            # getting missing columns
            missing_columns = set(self.old_columns.keys()) - set(
                self.incoming_columns)

            return False

    def set_table_widget(self):
        self.table_widget.clear()
        # if self.is_same_column():

        row_count = len(self.incoming_columns) if self.incoming_columns else len(
            self.old_columns)
        data_types = ['int', 'float', 'str', 'bool']
        print("Row count:", row_count)

        for i in range(row_count):
            print("inserting row:", i)
            self.table_widget.insertRow(i)
            column_name = self.incoming_columns[i] if self.incoming_columns else self.old_columns.get(
                i, "")

            print("Inserting checkbox")
            # # Checkbox for isSelected
            checkbox = QCheckBox()
            self.table_widget.setCellWidget(i, 0, checkbox)

            print("Inserting column name:", self.incoming_columns[i])
            # Editable line edit for column_name
            column_name_item = QTableWidgetItem(column_name)
            self.table_widget.setItem(i, 1, column_name_item)

            print("Inserting data type")
            # Dropdown for data_type
            combo_box = QComboBox()
            combo_box.addItems(data_types)
            # default_type = self.data.get(column_name, ["", "str"])[1]
            # combo_box.setCurrentText(default_type)
            self.table_widget.setCellWidget(i, 2, combo_box)

            print("Inserting rename")
            # Line edit for rename
            rename_item = QTableWidgetItem("")
            self.table_widget.setItem(i, 3, rename_item)

        self.table_widget.setColumnCount(4)
        # self.table_widget.setRowCount(len(self.incoming_columns))
        self.table_widget.setHorizontalHeaderLabels(
            ["Status", "Column Name", "Data Type", "Rename"])
        self.table_widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)

    def get_code(self):
        return f"print({self.incoming_variable}.head(10))\n"

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
    icon = "Resource/icons/in.png"
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
        print("#############")
        print("Select process Inputs")
        print("#############")
        # Custom processing logic for the Select node
        input_value = input_values[0]  # Assuming single input for simplicity
        self.content.incom_data = input_value.get('data')
        self.content.incoming_variable = input_value.get('variable_name')
        # self.content.set_table_widget()
        return {
            "data": self.content.incom_data,
            "variable_name": self.content.variable_name
        }

    # def evalImplementation(self):
    #     print("#############")
    #     print("Select evalImplementation")
    #     print("#############")
    #     input_node = self.getInput(0)
    #     print(input_node)

    #     if not input_node:
    #         self.grNode.setToolTip("Input is not connected")
    #         self.markInvalid()
    #         return

    #     # val = input_node.params()
    #     val = input_node.eval()

    #     if val is None:
    #         self.grNode.setToolTip("Input is NaN")
    #         self.markInvalid()
    #         return

    #     # self.content.lbl.setText("%s" % val)
    #     self.content.incom_data = val.get('data')
    #     self.content.incoming_variable = val.get('variable_name')
    #     self.markInvalid(False)
    #     self.markDirty(False)
    #     self.grNode.setToolTip("")

    #     print("Value passed from input node:", val)

    def get_code(self):
        print("getting code for file select: ")
        print(self.content.get_code())
        return self.content.get_code()

    # def evalImplementation(self):

    #     u_value = self.content.edit.text()
    #     s_value = int(u_value)
    #     self.value = s_value
    #     self.markDirty(False)
    #     self.markInvalid(False)

    #     self.markDescendantsInvalid(False)
    #     self.markDescendantsDirty()

    #     self.grNode.setToolTip("")

    #     self.evalChildren()

    #     return self.value
