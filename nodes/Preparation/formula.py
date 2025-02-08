from qtpy.QtWidgets import QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLayout
from qtpy.QtCore import Qt
from trigger_conf import OP_NODE_FORMULA, register_node, OP_NODE_FILE_INPUT
from trigger_node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.utils import dumpException
import pandas as pd
from themes.theme import Theme

theme = Theme()


class TriggerFormulaContent(QDMNodeContentWidget):
    def initUI(self, parent=None):
        self.data = []
        self.variable_name = f'file_input_{self.id}'

    def create_layout(self) -> QLayout:
        self.filePathEdit = QLineEdit(self)
        self.filePathEdit.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(self.filePathEdit)

        return layout

    def get_code(self):
        return f"print('New Node')"

    def serialize(self):
        res = super().serialize()
        res["filePath"] = self.filePath
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)

        try:
            self.filePath = data.get('filePath', "")
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@ register_node(OP_NODE_FORMULA, 'PREPARATION')
class TriggerNode_Formula(TriggerNode):
    icon = "Resource/icons/001-input-(Custom).png"
    op_code = OP_NODE_FORMULA
    op_type = 'PREPARATION'
    op_title = "Formula"
    content_label_objname = "trigger_node_formula"
    style = {
        'brush_color': theme.brush_color('PREPARATION')
    }

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        # self.eval()

    def initInnerClasses(self):
        self.content = TriggerFormulaContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalImplementation(self):
        u_value = 0
        print("Columns from input file:", u_value)
        # variable = self.content.variable_name
        return u_value

    def params(self):
        param = {
            "data": self.content.data,
            "variable_name": self.content.variable_name
        }
        return param

    def get_code(self):
        print("getting code for file input: ")
        print(self.content.get_code())
        return self.content.get_code()
