from qtpy.QtWidgets import QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLayout
from qtpy.QtCore import Qt
from trigger_conf import OP_NODE_FILE_OUTPUT, register_node, OP_NODE_FILE_INPUT
from trigger_node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.utils import dumpException
import pandas as pd
from themes.theme import Theme

theme = Theme()


class TriggerFileOutputContent(QDMNodeContentWidget):
    def initUI(self):
        self.filePath = ""
        self.input_variable_name = ""

    def create_layout(self) -> QLayout:
        self.filePathEdit = QLineEdit(self)
        self.filePathEdit.setReadOnly(True)
        self.loadButton = QPushButton("Save CSV", self)
        self.loadButton.clicked.connect(self.openFileDialog)

        layout = QVBoxLayout()
        layout.addWidget(self.filePathEdit)
        layout.addWidget(self.loadButton)

        return layout

    def openFileDialog(self):
        # options = QFileDialog.Options()
        filePath, _ = QFileDialog.getSaveFileName(
            self.parent(
            ), "Save CSV File", "", "CSV Files (*.csv);;All Files (*)")

        if filePath:
            self.filePath = filePath
            self.filePathEdit.setText(filePath)

    def get_code(self):
        return f"""import pandas as pd\n{self.input_variable_name}.to_csv('{self.filePath}')"""

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


@register_node(OP_NODE_FILE_OUTPUT, "INPUT")
class TriggerNode_FileOutput(TriggerNode):
    # icon = ":/output_icon"
    icon = "Resource/icons/Input/File Output.png"
    op_code = OP_NODE_FILE_OUTPUT
    op_title = "File Output"
    op_type = "INPUT"
    content_label_objname = "trigger_node_file_output"
    style = {
        'brush_color': theme.brush_color('INPUT')
    }

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[])
        # self.eval()

    def initInnerClasses(self):
        self.content = TriggerFileOutputContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalImplementation(self):
        # u_value = 0
        # print("Columns from input file:", u_value)
        # return u_value

        input_node = self.getInput(0)
        if not input_node:
            self.grNode.setToolTip("Input is not connected")
            self.markInvalid()
            return
        val = input_node.params()

        if val is None:
            self.grNode.setToolTip("Input is NaN")
            self.markInvalid()
            return

        self.content.input_variable_name = val.get('variable_name')
        self.markInvalid(False)
        self.markDirty(False)
        self.grNode.setToolTip("")

        print("Value passed from input node:", val)

    # def params(self):
        # param = {
        #     "columns": self.content.get_columns(),
        #     "data": self.content.data
        # }
        # return param
