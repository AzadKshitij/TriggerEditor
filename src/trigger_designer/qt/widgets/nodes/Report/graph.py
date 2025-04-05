from ast import List
from qtpy.QtWidgets import (QWidget, QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget,
                            QTableWidgetItem, QHeaderView, QLayout, QComboBox, QLineEdit, QLabel, QHBoxLayout)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_designer.core.node_configuration import register_node, NodeTypes, ReportNodes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.node_node import Node
from nodeeditor.node_scene import Scene
from nodeeditor.utils import dumpException
import pandas as pd
from typing import Any, Optional, OrderedDict, Type, cast


class GraphContent(QDMNodeIconContentWidget, TriggerChangeHandler):

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node: 'Node', parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, node.scene)
        # local variables

        # incoming variables
        self.incoming_variable: str = ''
        self.incom_data: Optional[pd.DataFrame] = None

        # pass on variables
        self.data: list = []
        self.variable_name = f'var_graph_{self.id}'

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        icon = QPixmap('Resource/icons/Preparation/Select.png')
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        self.filePathEdit = QLineEdit(self)
        self.filePathEdit.setReadOnly(True)

        dock_layout.addWidget(self.filePathEdit)

        # return layout

    def get_code(self) -> str:
        return f"print('New Node')"

    def serialize(self) -> OrderedDict[Any, Any]:
        res = super().serialize()
        res["filePath"] = self.filePath
        return res

    def deserialize(self, data: dict, hashmap: dict = {}, restore_id: Optional[bool] = True) -> bool:
        res = super().deserialize(data, hashmap)

        try:
            self.filePath = data.get('filePath', "")
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(ReportNodes.GRAPH, NodeTypes.REPORT)
class TriggerNode_Graph(TriggerNode):
    icon = "icons/001-input (Custom).png"
    node_code = ReportNodes.GRAPH
    node_type = NodeTypes.REPORT
    node_title = "Graph"
    content_label_objname = "trigger_node_node_title"
    style = {}

    def __init__(self, scene: 'Scene') -> None:
        super().__init__(scene, inputs=[1], outputs=[3])
        # self.eval()

    def initInnerClasses(self) -> None:
        self.content = GraphContent(self)
        self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)

    def processInputs(self, input_values: list[Any]) -> Optional[Any]:
        # Only one input for simplicity
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]
        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            # Custom processing logic for the Select node
            self.content.incom_data = input_value.get('data')
            self.content.incoming_variable = input_value.get('variable_name')
            self.evalChildren()
            return [{
                'data': self.content.data,
                'variable_name': self.content.variable_name
            }]
        # variable = self.content.variable_name
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip('Input is not connected')
            return [None]

    def get_code(self):
        return self.content.get_code()
