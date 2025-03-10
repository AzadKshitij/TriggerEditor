import pandas as pd
import os

from qtpy.QtWidgets import QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLayout
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_conf import register_node, OP_NODE_FILE_INPUT
from trigger_node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget

from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.utils import dumpException
# from pandas import DataFrame
from themes.theme import Theme

theme = Theme()


class FileInputContent(QDMNodeIconContentWidget, TriggerChangeHandler):

    evaluate = Signal()

    def __init__(self, node, parent=None):
        super().__init__(node, parent)
        # local Variables
        self.filePath = ""
        TriggerChangeHandler.__init__(self, self.node.scene)

        # pass on variables
        self.data: pd.DataFrame = None
        self.variable_name = f'var_file_input_{self.id}'

    def initUI(self):
        icon = QPixmap("Resource/icons/Input/File Input.png")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> QLayout:
        self.filePathEdit = QLineEdit(self)
        self.filePathEdit.setPlaceholderText("Enter file path")
        # self.filePathEdit.connect(self.check_file_path)
        # self.filePathEdit.textChanged.connect(self.on_input_changed)
        self.registerInputWidget(self.filePathEdit)

        self.loadButton = QPushButton("Load CSV", self)
        self.loadButton.clicked.connect(self.openFileDialog)

        # Always create a new table widget when creating layout
        self.tableWidget = QTableWidget(self)

        if self.filePath:
            self.filePathEdit.setText(self.filePath)
            self.loadCSV(self.filePath)

        dock_layout.addWidget(self.filePathEdit)
        dock_layout.addWidget(self.loadButton)
        dock_layout.addWidget(self.tableWidget)
        # return dock_layout

    def check_file_path(self):
        file_path = self.filePathEdit.text()
        # self.evaluate.emit()

        # Check if the file exists
        if not os.path.exists(file_path):
            print(f"Error: File '{file_path}' does not exist.")
            return

        # Check if the file is a CSV file
        # if not file_path.endswith('.csv'):
        #     print(f"Error: File '{file_path}' is not a CSV file.")
        #     return

        if self.filePath:
            self.loadCSV(self.filePath)

    def get_columns(self):
        if self.filePath:
            df = pd.read_csv(self.filePath)
            self.data = df.head(10)
            return df.columns.tolist()

        return []

    def openFileDialog(self):
        '''Open CSV File", "", "CSV Files (*.csv);;'''
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self.parent(
        ), "Open CSV File", "", "CSV Files (*.csv);;All Files (*)", options=options)
        if fileName:
            self.filePath = fileName
            self.filePathEdit.setText(fileName)
            self.loadCSV(fileName)
            self.evaluate.emit()

    def loadCSV(self, fileName):
        # Create table widget only if it doesn't exist
        if not hasattr(self, 'tableWidget') or self.tableWidget is None:
            self.tableWidget = QTableWidget(self)

        try:
            df = pd.read_csv(fileName)
            self.data = df.head(10)
            columns = self.data.columns.tolist()

            data_list = self.data.values.tolist()

            # Set the number of rows and columns
            self.tableWidget.setRowCount(len(data_list))
            self.tableWidget.setColumnCount(len(data_list[0]))
            self.tableWidget.setHorizontalHeaderLabels(columns)

            # Fill in the rest of the data
            for i in range(len(data_list)):
                for j in range(len(data_list[i])):
                    self.tableWidget.setItem(
                        i, j, QTableWidgetItem(str(data_list[i][j])))

            # Table will fit the screen horizontally
            self.tableWidget.setSortingEnabled(True)
            # self.tableWidget.horizontalHeader().setStretchLastSection(True)
            # self.tableWidget.horizontalHeader().setSectionResizeMode(
            #     QHeaderView.Stretch)
            self.tableWidget.horizontalHeader().setSectionsMovable(True)
        # Display the head of the DataFrame
            # self.evaluate.emit()
            # self.csvPreview.setPlainText(df.head().to_string())
        except Exception as e:
            dumpException(e)

    def get_code(self):
        if not self.filePath:
            return ""

        code_lines = []
        code_lines.append(f"import pandas as pd")
        code_lines.append(
            f"{self.variable_name} = pd.read_csv('{self.filePath}')")

        return '\n'.join(code_lines) + '\n'

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


@register_node(OP_NODE_FILE_INPUT, 'INPUT')
class TriggerNode_FileInput(TriggerNode):
    icon = "Resource/icons/Input/File Input.png"
    op_code = OP_NODE_FILE_INPUT
    op_type = 'INPUT'
    op_title = "File Input"
    content_label_objname = "trigger_node_file_input"
    style = {
        'brush_color': theme.brush_color('INPUT')
    }

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[1])
        # self.eval()
        self.markInvalid(True)

    def initInnerClasses(self):
        self.content = FileInputContent(self)
        self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)

    # def evalImplementation(self):
    #     param = {
    #         "data": self.content.data,
    #         "variable_name": self.content.variable_name
    #     }
    #     # variable = self.content.variable_name
    #     return param

    def processInputs(self, input_values):
        print("⚠️⚠️⚠️ File Input ⚠️⚠️⚠️")
        # Custom processing logic for the File Input node
        if not self.content.filePath:
            self.grNode.setToolTip("No file selected")
            self.markInvalid(True)
            return [None]

        self.markDirty(False)
        self.markInvalid(False)
        # self.markDescendantsInvalid(False)
        # self.markDescendantsDirty()

        # self.content.loadCSV(self.content.filePath)
        # self.content.loadCSV(self.content.filePath)
        param = [{
            "data": self.content.data,
            "variable_name": self.content.variable_name
        }]

        self.evalChildren()

        return param

    def params(self):
        param = {
            "data": self.content.data,
            "variable_name": self.content.variable_name
        }
        return param

    def get_code(self):
        return self.content.get_code()
