from qtpy.QtWidgets import QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLayout
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt
from trigger_conf import register_node, OP_NODE_FILE_INPUT
from trigger_node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget

from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.utils import dumpException
import pandas as pd
# from pandas import DataFrame
from themes.theme import Theme

theme = Theme()


class TriggerFileInputContent(QDMNodeIconContentWidget):

    def __init__(self, node, parent=None):
        super().__init__(node, parent)
        # local Variables
        self.filePath = ""

        # pass on variables
        self.data: pd.DataFrame = None
        self.variable_name = f'var_file_input_{self.id}'

    def initUI(self):
        icon = QPixmap("Resource/icons/Input/File Input.svg")
        super().initUI(icon)

    def create_layout(self) -> QLayout:
        self.filePathEdit = QLineEdit(self)
        self.filePathEdit.setReadOnly(True)

        self.loadButton = QPushButton("Load CSV", self)
        self.loadButton.clicked.connect(self.openFileDialog)

        self.tableWidget = QTableWidget(self)

        if self.filePath:
            self.filePathEdit.setText(self.filePath)
            self.loadCSV(self.filePath)

        layout = QVBoxLayout()
        layout.addWidget(self.filePathEdit)
        layout.addWidget(self.loadButton)
        layout.addWidget(self.tableWidget)

        return layout

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

    def loadCSV(self, fileName):
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
            # self.csvPreview.setPlainText(df.head().to_string())
        except Exception as e:
            dumpException(e)

    def get_code(self):
        return f"""import pandas as pd\n{self.variable_name} = pd.read_csv('{self.filePath}')\n"""

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
    # icon = "Resource/icons/Input/File Output_check.png"
    icon = "Resource/icons/Input/File Input.svg"
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

    def initInnerClasses(self):
        self.content = TriggerFileInputContent(self)
        self.grNode = TriggerGraphicsNode(self)

    # def evalImplementation(self):
    #     param = {
    #         "data": self.content.data,
    #         "variable_name": self.content.variable_name
    #     }
    #     # variable = self.content.variable_name
    #     return param

    def processInputs(self, input_values):
        print("#############")
        print("File Input process Inputs")
        print("#############")
        # Custom processing logic for the File Input node
        if not self.content.filePath:
            self.grNode.setToolTip("No file selected")
            self.markInvalid()
            return None

        self.content.loadCSV(self.content.filePath)

        # self.content.loadCSV(self.content.filePath)
        param = {
            "data": self.content.data,
            "variable_name": self.content.variable_name
        }
        return param

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
