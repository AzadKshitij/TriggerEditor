from qtpy.QtWidgets import QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit
from qtpy.QtCore import Qt
from trigger_conf import register_node, OP_NODE_INPUT, OP_NODE_FILE_INPUT
from trigger_node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.utils import dumpException
import pandas as pd


class TriggerFileInputContent(QDMNodeContentWidget):
    def initUI(self, parent=None):
        self.filePathEdit = QLineEdit(self)
        self.filePathEdit.setReadOnly(True)
        self.loadButton = QPushButton("Load CSV", self)
        # self.loadButton.clicked.connect(self.openFileDialog)
        self.loadButton.setObjectName(self.node.content_label_objname)

        self.csvPreview = QTextEdit(self)
        self.csvPreview.setReadOnly(True)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.filePathEdit)
        self.layout.addWidget(self.loadButton)
        self.layout.addWidget(self.csvPreview)
        # self.setLayout(layout)

        self.filePath = ""

    def openFileDialog(self):
        '''Open CSV File", "", "CSV Files (*.csv);;'''
        options = QFileDialog.Options()
        # options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self.parent(
        ), "Open CSV File", "", "CSV Files (*.csv);;All Files (*)", options=options)

        if fileName:
            self.filePath = fileName
            self.filePathEdit.setText(fileName)
            self.loadCSV(fileName)

    def loadCSV(self, fileName):
        try:
            df = pd.read_csv(fileName)
            # Display the head of the DataFrame
            self.csvPreview.setPlainText(df.head().to_string())
        except Exception as e:
            dumpException(e)

    def serialize(self):
        res = super().serialize()
        res['filePath'] = self.filePath
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            self.filePath = data.get('filePath', "")
            self.filePathEdit.setText(self.filePath)
            if self.filePath:
                self.loadCSV(self.filePath)
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(OP_NODE_FILE_INPUT)
class TriggerNode_FileInput(TriggerNode):
    icon = "icons/in.png"
    op_code = OP_NODE_FILE_INPUT
    op_title = "InputFile"
    content_label_objname = "trigger_node_file_input"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        # self.eval()

    def initInnerClasses(self):
        self.content = TriggerFileInputContent(self)
        self.grNode = TriggerGraphicsNode(self)
        self.content.loadButton.clicked.connect(self.content.openFileDialog)
        # self.content.edit.textChanged.connect(self.onInputChanged)

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
