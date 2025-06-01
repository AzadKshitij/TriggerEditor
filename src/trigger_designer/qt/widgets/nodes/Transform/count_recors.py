from typing import Optional
import pandas as pd
from qtpy.QtWidgets import QWidget, QVBoxLayout, QLabel
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Signal, Qt
from trigger_designer.core.node_configuration import register_node, TransformNodes, NodeTypes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget


class CountRecordsContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """Simple record counter for DataFrame.
    Counts total number of rows in the input DataFrame.
    """

    evaluate = Signal()

    def __init__(self, node: 'TriggerNode', parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        self.node = node

        # Data tracking
        self.incoming_variable: str = ''
        self.incom_data: Optional[pd.DataFrame] = None
        self.data: Optional[pd.DataFrame] = None
        self.variable_name = f'var_count_{self.id}'

        # Count result
        self.total_records = 0

    @property
    def node(self) -> 'TriggerNode':
        return self._node

    @node.setter
    def node(self, value: 'TriggerNode') -> None:
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f'{self.node.icon}')
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is not None:
            main_layout = QVBoxLayout()
            main_layout.setSpacing(2)
            main_layout.setContentsMargins(5, 5, 5, 5)

            # Display count
            count_label = QLabel(f"Total Records: {self.total_records:,}")
            count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(count_label)

            dock_layout.addLayout(main_layout)
        else:
            no_data_label = QLabel('No incoming data available')
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet('color: gray;')
            dock_layout.addWidget(no_data_label)

    def process_data(self) -> None:
        """Count total records in DataFrame"""
        if self.incom_data is not None:
            self.total_records = len(self.incom_data)
            self.data = pd.DataFrame({'Count': [self.total_records]})

    def get_code(self) -> str:
        """Generate code for counting records"""
        if self.data is None or self.incoming_variable is None:
            return ""
        return f"{self.variable_name} = pd.DataFrame({{'Count': [len({self.incoming_variable})]}})\n"


@register_node(TransformNodes.COUNT_RECORDS, NodeTypes.TRANSFORM)
class TriggerNode_CountRecords(TriggerNode):
    icon = "node_count"
    node_code = TransformNodes.COUNT_RECORDS
    node_title = "Count Records"
    node_type = NodeTypes.TRANSFORM
    content_label_objname = "trigger_node_count_records"

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[1])
        self.eval()

    def initInnerClasses(self) -> None:
        self.content: CountRecordsContent = CountRecordsContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values):
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)

            self.content.incom_data = input_value.get('data')
            self.content.incoming_variable = input_value.get('variable_name')

            self.content.process_data()
            self.evalChildren()
            self.param = [{
                'data': self.content.data,
                'variable_name': self.content.variable_name
            }]

            return self.param
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip('Input is not connected')
            return None
