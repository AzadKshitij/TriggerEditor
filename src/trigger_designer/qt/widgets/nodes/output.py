from qtpy.QtWidgets import QLabel, QLayout, QVBoxLayout
from qtpy.QtCore import Qt
from trigger_designer.core.node_configuration import NodeTypes, register_node, CalcNodes
from trigger_designer.qt.node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget


class CalcOutputContent(QDMNodeContentWidget):
    def initUI(self) -> None:
        self.lbl = QLabel("42", self)
        self.lbl.setAlignment(Qt.AlignLeft)
        self.lbl.setObjectName(self.node.content_label_objname)

    def create_layout(self) -> QLayout:
        layout = QVBoxLayout()
        return layout


@register_node(CalcNodes.OUTPUT, NodeTypes.CALC)
class CalcNode_Output(TriggerNode):
    icon = "src/trigger_designer/Resource/icons/out.png"
    node_code = CalcNodes.OUTPUT
    node_title = "Output"
    node_typepe = NodeTypes.CALC
    content_label_objname = "calc_node_output"

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[])

    def initInnerClasses(self) -> None:
        self.content = CalcOutputContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalImplementation(self):
        print("#############")
        print("Output evalImplementation")
        print("#############")
        input_node = self.getInput(0)
        if not input_node:
            self.grNode.setToolTip("Input is not connected")
            self.markInvalid()
            return

        val = input_node.eval()

        if val is None:
            self.grNode.setToolTip("Input is NaN")
            self.markInvalid()
            return

        self.content.lbl.setText("%d" % val)
        self.markInvalid(False)
        self.markDirty(False)
        self.grNode.setToolTip("")

        return val

    def execute(self, node_input) -> None:
        print("Input")
        print(node_input)
