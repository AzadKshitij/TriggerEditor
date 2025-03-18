from qtpy.QtWidgets import QLabel
from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap
from trigger_conf import register_node, OP_NODE_OUTPUT, OP_NODE_TEXT_OUTPUT
from trigger_node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget


class CalcTextOutputContent(QDMNodeIconContentWidget):
    def initUI(self):
        # self.lbl = QLabel("Passed Param", self)
        icon = QPixmap("src/trigger_designer/Resource/icons/out.png")
        super().initUI(icon)


@register_node(OP_NODE_TEXT_OUTPUT, "INPUT")
class CalcNode_TextOutput(TriggerNode):
    icon = "src/trigger_designer/Resource/icons/out.png"
    op_code = OP_NODE_TEXT_OUTPUT
    op_type = 'INPUT'
    op_title = "Text Output"
    content_label_objname = "calc_node_text_output"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[])

    def initInnerClasses(self):
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
