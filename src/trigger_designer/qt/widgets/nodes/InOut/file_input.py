import pandas as pd
import os

from qtpy.QtWidgets import QWidget, QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLayout
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.core.node_configuration import register_node, IONodes, NodeTypes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget

from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.utils import dumpException
from loguru import logger
from typing import Any, Optional, OrderedDict, TYPE_CHECKING, Type, TypeVar, Union, cast


if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene
    from trigger_designer.qt.node_base import TriggerNode
    from nodeeditor.node_node import Node

# from pandas import DataFrame


class FileInputContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    evaluate = Signal()

    def __init__(self, node: 'TriggerNode', parent: Optional[QWidget] = None) -> None:
        """Initialize the FileInputContent widget.

        Args:
            node (TriggerNode): The node this content belongs to
            parent (Optional[QWidget], optional): Parent widget. Defaults to None.
        """
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)
        # local Variables
        self.filePath = ""
        self.preview_rows = 10
        self.node = node

        # pass on variables
        self.data: pd.DataFrame = pd.DataFrame()
        self.variable_name = f'var_file_input_{self.id}'

    def initUI(self, _icon: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        # icon = QPixmap(
        #     "src/trigger_designer/Resource/icons/Input/File Input.png")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        self.filePathEdit = QLineEdit(self)
        self.filePathEdit.setPlaceholderText("Enter file path")
        # self.filePathEdit.connect(self.check_file_path)
        self.filePathEdit.textChanged.connect(
            self._on_filePathEdit_textChanged)
        # textChanged.connect(self.onDataChanged)
        self.registerInputWidget(self.filePathEdit)

        self.loadButton = QPushButton("Load CSV", self)
        self.loadButton.clicked.connect(self.openFileDialog)

        # Always create a new table widget when creating layout
        self.tableWidget = QTableWidget(self)

        if self.filePath:
            self.filePathEdit.setText(self.filePath)
            if self.data.empty:
                self.loadCSV(self.filePath)

        dock_layout.addWidget(self.filePathEdit)
        dock_layout.addWidget(self.loadButton)
        dock_layout.addWidget(self.tableWidget)

    def _on_filePathEdit_textChanged(self) -> None:
        self.filePath = self.filePathEdit.text()
        self.check_file_path()

    def check_file_path(self) -> bool:
        if not self.filePath:
            return False
        # self.evaluate.emit()

        # Check if the file exists
        if not os.path.exists(self.filePath):
            print(f"Error: File '{self.filePath}' does not exist.")
            self.node.grNode.setToolTip("File does not exist")
            self.node.markInvalid(True)
            return False
        else:
            print(f"File '{self.filePath}' exists.")
            self.node.grNode.setToolTip("")
            self.node.markInvalid(False)

        self.loadCSV(self.filePath)
        return True

    def get_columns(self) -> list[str]:
        if self.filePath:
            df = pd.read_csv(self.filePath)
            self.data = df.head(10)
            return df.columns.tolist()

        return []

    def openFileDialog(self) -> None:
        '''Open CSV File", "", "CSV Files (*.csv);;'''
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self.parent(),
                                                  "Open CSV File", "", "CSV Files (*.csv);;All Files (*)", options=options)
        if fileName:
            self.filePath = fileName
            self.filePathEdit.setText(fileName)
            # self.loadCSV(fileName)
            self.evaluate.emit()

    def loadCSV(self, fileName: str) -> None:

        # Create table widget only if it doesn't exist
        if not hasattr(self, 'tableWidget') or self.tableWidget is None:
            self.tableWidget = QTableWidget(self)

        try:
            self.data = pd.read_csv(fileName, nrows=self.preview_rows)
            columns = self.data.columns.tolist()

            data_list = self.data.values.tolist()

            # Set the number of rows and columns
            self.tableWidget.setRowCount(len(data_list))
            self.tableWidget.setColumnCount(len(columns))
            self.tableWidget.setHorizontalHeaderLabels(columns)

            # Fill in the rest of the data
            # for i in range(len(data_list)):
            #     for j in range(len(data_list[i])):
            #         self.tableWidget.setItem(
            #             i, j, QTableWidgetItem(str(data_list[i][j])))

            for i, row in enumerate(data_list):
                for j, value in enumerate(row):
                    item = QTableWidgetItem(str(value))
                    self.tableWidget.setItem(i, j, item)

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
            logger.error(f"Exception in loading csv file")
            logger.trace(e)

    def get_code(self) -> str:
        if not self.filePath:
            return ""

        code_lines = []
        code_lines.append(f"import pandas as pd")
        code_lines.append(
            f"{self.variable_name} = pd.read_csv('{self.filePath}')")

        return '\n'.join(code_lines) + '\n'

    def serialize(self) -> OrderedDict[Any, Any]:
        res = super().serialize()
        res["filePath"] = self.filePath
        return res

    def deserialize(self, data: dict, hashmap: dict = {}, restore_id: Optional[bool] = True) -> bool:
        res = super().deserialize(data, hashmap)

        try:
            self.filePath = data.get('filePath', "")
            return res
        except Exception as e:
            dumpException(e)
        return res


@register_node(IONodes.FILE_INPUT, NodeTypes.IO)
class TriggerNode_FileInput(TriggerNode):
    icon = "node_file_input"
    node_code = IONodes.FILE_INPUT
    node_type = NodeTypes.IO
    node_title = "File Input"
    content_label_objname = "trigger_node_file_input"
    style = {}

    def __init__(self, scene: 'Scene') -> None:
        super().__init__(scene, inputs=[], outputs=[3])
        # self.eval()
        self.markInvalid(True)

    def initInnerClasses(self) -> None:
        self.content: FileInputContent = FileInputContent(self)
        # self.content = cast('QDMNodeContentWidget', FileInputContent(self))
        self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)

    # def evalImplementation(self):
    #     param = {
    #         "data": self.content.data,
    #         "variable_name": self.content.variable_name
    #     }
    #     # variable = self.content.variable_name
    #     return param

    def processInputs(self, input_values: list[Any]) -> None:
        print("⚠️⚠️⚠️ File Input ⚠️⚠️⚠️")
        # Custom processing logic for the File Input node
        if not self.content.filePath:
            self.grNode.setToolTip("No file selected")
            self.markInvalid(True)
            return None

        self.markDirty(False)
        self.markInvalid(False)
        # self.markDescendantsInvalid(False)
        # self.markDescendantsDirty()

        # self.content.loadCSV(self.content.filePath)
        self.content.check_file_path()
        param = [{
            "data": self.content.data,
            "variable_name": self.content.variable_name
        }]

        self.evalChildren()

        return param

    def get_code(self):
        return self.content.get_code()
