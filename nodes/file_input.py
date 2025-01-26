from qtpy.QtWidgets import QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLayout
from qtpy.QtCore import Qt
from trigger_conf import register_node, OP_NODE_INPUT, OP_NODE_FILE_INPUT
from trigger_node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.utils import dumpException
import pandas as pd


class TriggerFileInputContent(QDMNodeContentWidget):
    def initUI(self, parent=None):
        self.filePath = ""
        self.create_layout()

    def create_layout(self) -> QLayout:
        self.filePathEdit = QLineEdit(self)
        self.filePathEdit.setReadOnly(True)
        self.loadButton = QPushButton("Load CSV", self)
        self.tableWidget = QTableWidget(self)
        # self.loadButton.setObjectName(self.node.content_label_objname)

        layout = QVBoxLayout()
        layout.addWidget(self.filePathEdit)
        layout.addWidget(self.loadButton)
        layout.addWidget(self.tableWidget)
        # layout.addChildLayout(QVBoxLayout())
        # self.setLayout(self.layout)

        return layout

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
            data = df.head(10)

            data_list = data.values.tolist()

            # Set the number of rows and columns
            self.tableWidget.setRowCount(len(data_list))
            self.tableWidget.setColumnCount(len(data_list[0]))

            self.tableWidget.setHorizontalHeaderLabels(data.columns.tolist())

            # Fill in the rest of the data
            for i in range(len(data_list)):
                for j in range(len(data_list[i])):
                    self.tableWidget.setItem(
                        i, j, QTableWidgetItem(str(data_list[i][j])))

            # Table will fit the screen horizontally
            self.tableWidget.horizontalHeader().setStretchLastSection(True)
            self.tableWidget.horizontalHeader().setSectionResizeMode(
                QHeaderView.Stretch)
        # Display the head of the DataFrame
            # self.csvPreview.setPlainText(df.head().to_string())
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


@ register_node(OP_NODE_FILE_INPUT)
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
