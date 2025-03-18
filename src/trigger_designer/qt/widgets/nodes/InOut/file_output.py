from qtpy.QtWidgets import QWidget, QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLayout, QSpacerItem, QSizePolicy
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_conf import OP_NODE_FILE_OUTPUT, register_node, OP_NODE_FILE_INPUT
from trigger_node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget

from nodeeditor.utils import dumpException
import pandas as pd


class FileOutputContent(QDMNodeIconContentWidget, TriggerChangeHandler):

    evaluate = Signal()

    def __init__(self, node, parent=None):
        super().__init__(node, parent)
        # local Variables
        self.filePath = ""
        TriggerChangeHandler.__init__(self, self.node.scene)

        # incoming variables
        self.incoming_variable = ""
        self.data: pd.DataFrame = None

    def initUI(self):
        icon = QPixmap(
            "src/trigger_designer/Resource/icons/Input/File Output.png")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> QLayout:
        self.filePathEdit = QLineEdit(self)
        self.filePathEdit.setPlaceholderText("Enter file path")
        # self.filePathEdit.setReadOnly(True)
        self.loadButton = QPushButton("Save CSV", self)
        self.loadButton.clicked.connect(self.openFileDialog)
        self.registerInputWidget(self.filePathEdit)

        if self.filePath:
            self.filePathEdit.setText(self.filePath)

        # layout.setContentsMargins(0, 0, 0, 0)
        # layout.setSpacing(2)
        dock_layout.addWidget(self.filePathEdit)
        dock_layout.addWidget(self.loadButton)
        dock_layout.setContentsMargins(0, 0, 0, 0)
        dock_layout.addSpacerItem(QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        # layout.addStretch(0)
        # layout.addSpacerItem(QSpacerItem(
        #     20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # return dock_layout

    def openFileDialog(self):
        filePath, _ = QFileDialog.getSaveFileName(
            self.parent(
            ), "Save CSV File", "", "CSV Files (*.csv);;All Files (*)")

        if filePath:
            self.filePath = filePath
            self.filePathEdit.setText(filePath)

    def get_code(self):

        if self.incoming_variable is None:
            return ""

        code_lines = []

        # Get file extension
        file_ext = self.filePath.lower().split(
            '.')[-1] if '.' in self.filePath else 'csv'

        print("🐍 File: InOut/file_output.py | Line: 66 | get_code ~ file_ext", file_ext)

        # Generate appropriate export code based on file extension
        if file_ext == 'csv':
            code_lines.append(
                f"{self.incoming_variable}.to_csv('{self.filePath}', index=False)")
        elif file_ext == 'xlsx' or file_ext == 'xls':
            code_lines.append(
                f"{self.incoming_variable}.to_excel('{self.filePath}', index=False)")
        elif file_ext == 'json':
            code_lines.append(
                f"{self.incoming_variable}.to_json('{self.filePath}', orient='records')")
        elif file_ext == 'parquet':
            code_lines.append(
                f"{self.incoming_variable}.to_parquet('{self.filePath}', index=False)")
        else:
            # Default to CSV if extension is not recognized
            code_lines.append(
                f"{self.incoming_variable}.to_csv('{self.filePath}', index=False)")

        return '\n'.join(code_lines) + '\n'

    def serialize(self):
        res = super().serialize()
        res["filePath"] = self.filePath
        return res

    def deserialize(self, data, hashmap={}):
        print("🐍 File: InOut/file_output.py | Line: 99 | serialize ~ deserialize", data)
        res = super().deserialize(data, hashmap)

        try:
            print(
                "🐍 File: InOut/file_output.py | Line: 104 | deserialize ~ filePath", self.filePath)
            # self.filePath = data.get('filePath', "")
            self.filePath = data['filePath']
            return True & res
        except Exception as e:

            dumpException(e)
        return res


@register_node(OP_NODE_FILE_OUTPUT, "INPUT")
class TriggerNode_FileOutput(TriggerNode):
    # icon = ":/output_icon"
    icon = "src/trigger_designer/Resource/icons/Input/File Output.png"
    op_code = OP_NODE_FILE_OUTPUT
    op_title = "File Output"
    op_type = "INPUT"
    content_label_objname = "trigger_node_file_output"
    style = {}

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[])
        # self.eval()

    def initInnerClasses(self):
        self.content = FileOutputContent(self)
        self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)

    def processInputs(self, input_values):
        # Only one input for simplicity
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if not input_value:
            self.grNode.setToolTip("Input is not connected")
            self.markInvalid(True)
            return None

        self.markDirty(False)
        self.markInvalid(False)

        self.content.incoming_variable = input_value.get('variable_name')
        self.grNode.setToolTip("")

        print(f"Value Received in {self.__class__.__name__}:", input_value)

        return input_value

    def get_code(self):
        # print("getting code for file output: ", self.content.get_code())
        return self.content.get_code()
    # def params(self):
        # param = {
        #     "columns": self.content.get_columns(),
        #     "data": self.content.data
        # }
        # return param
