from qtpy.QtWidgets import QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLayout
from qtpy.QtCore import Qt
from trigger_conf import register_node, OP_NODE_FILE_INPUT
from trigger_node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.utils import dumpException
import pandas as pd
from themes.theme import Theme

theme = Theme()


class TriggerFileInputContent(QDMNodeContentWidget):
    def initUI(self, parent=None):
        self.filePath = ""
        self.data = []

    def create_layout(self) -> QLayout:
        self.filePathEdit = QLineEdit(self)
        self.filePathEdit.setReadOnly(True)
        self.loadButton = QPushButton("Load CSV", self)
        self.tableWidget = QTableWidget(self)
        self.loadButton.clicked.connect(self.openFileDialog)
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
            self.data = [
                {
                    'column_name': col,
                    'dtype': df[col].dtype.name
                }
                for col in df.columns
            ]
            return df.columns.tolist()

        return []
        # self.data = df.dtypes.apply(
        #     lambda x: {'column_name': x.name, 'dtype': x}).to_list()

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
            data = df.head(10)
            columns = data.columns.tolist()

            data_list = data.values.tolist()

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

    def serialize(self):
        res = super().serialize()
        res["filePath"] = self.filePath
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)

        try:
            self.filePath = data.get('filePath', "")
            self.columns = self.get_columns()
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@ register_node(OP_NODE_FILE_INPUT, 'INPUT')
class TriggerNode_FileInput(TriggerNode):
    icon = "icons/file_input (Custom).png"
    op_code = OP_NODE_FILE_INPUT
    op_title = "File Input"
    content_label_objname = "trigger_node_file_input"
    style = {
        'brush_color': theme.brush_color('INPUT')
    }
    # brush_color = "#ff0066"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])
        # self.eval()

    def initInnerClasses(self):
        self.content = TriggerFileInputContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalImplementation(self):
        u_value = 0
        print("Columns from input file:", u_value)
        return u_value

    def params(self):
        param = {
            "columns": self.content.get_columns(),
            "data": self.content.data
        }
        return param
