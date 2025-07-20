from qtpy.QtWidgets import QLabel
from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap
from trigger_designer.core.node_configuration import register_node, IONodes, NodeTypes
from trigger_designer.qt.node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget


class CalcTextOutputContent(QDMNodeIconContentWidget):
    def initUI(self) -> None:
        # self.lbl = QLabel("Passed Param", self)
        icon = QPixmap("src/trigger_designer/Resource/icons/out.png")
        super().initUI(icon)


@register_node(IONodes.TEXT_OUTPUT, NodeTypes.IO)
class CalcNode_TextOutput(TriggerNode):
    icon = "node_file_output"
    node_code = IONodes.TEXT_OUTPUT
    node_type = NodeTypes.IO
    node_title = "Text Output"
    content_label_objname = "calc_node_text_output"

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[])

    def initInnerClasses(self) -> None:
        self.content = CalcTextOutputContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalImplementation(self):
        input_node = self.getInput(0)
        if not input_node:
            self.grNode.setToolTip("Input is not connected")
            self.markInvalid()
            return

        val = input_node.params()

        print("Value passed from input node:", val)

        if val is None:
            self.grNode.setToolTip("Input is NaN")
            self.markInvalid()
            return

        self.content.lbl.setText("%s" % val)
        # self.content.lbl.setText("%d" % val)
        self.markInvalid(False)
        self.markDirty(False)
        self.grNode.setToolTip("")

        return val
