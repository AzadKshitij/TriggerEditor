from qtpy.QtWidgets import QLayout, QVBoxLayout

from trigger_conf import register_node, OP_NODE_ADD, OP_NODE_SUB, OP_NODE_MUL, OP_NODE_DIV, OP_NODE_SQRT
from trigger_node_base import TriggerNode
from trigger_node_base import TriggerNode, TriggerGraphicsNode

from nodeeditor.node_content_widget import QDMNodeContentWidget


class OperationContent(QDMNodeContentWidget):
    def create_layout(self) -> QLayout:
        layout = QVBoxLayout()
        return layout


@register_node(OP_NODE_ADD, "CALC")
class TriggerNode_Add(TriggerNode):
    icon = "src/trigger_designer/Resource/icons/add.png"
    op_code = OP_NODE_ADD
    op_title = "Add"
    op_type = "CALC"
    content_label = "+"
    content_label_objname = "calc_node_bg"
    style = {
    }

    def initInnerClasses(self):
        self.content = OperationContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalOperation(self, input1, input2):
        print("#############")
        print("Add evalOperation")
        print("#############")
        return input1 + input2

    def execute(self, node_input):
        print("Input")
        print(node_input)


@register_node(OP_NODE_SUB, "CALC")
class CalcNode_Sub(TriggerNode):
    icon = "src/trigger_designer/Resource/icons/sub.png"
    op_code = OP_NODE_SUB
    op_title = "Substract"
    op_type = "CALC"
    content_label = "-"
    content_label_objname = "calc_node_bg"
    style = {
    }

    def initInnerClasses(self):
        self.content = OperationContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalOperation(self, input1, input2):
        print("#############")
        print("Sub evalOperation")
        print("#############")
        return input1 - input2

    def execute(self, node_input):
        print("Input")
        print(node_input)


@register_node(OP_NODE_MUL, "CALC")
class TriggerNode_Mul(TriggerNode):
    icon = "src/trigger_designer/Resource/icons/mul.png"
    op_code = OP_NODE_MUL
    op_title = "Multiply"
    op_type = "CALC"
    content_label = "*"
    content_label_objname = "calc_node_mul"
    style = {
    }

    def initInnerClasses(self):
        self.content = OperationContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalOperation(self, input1, input2):
        print('foo')
        return input1 * input2

    def execute(self, node_input):
        print("Input")
        print(node_input)


@register_node(OP_NODE_DIV, "CALC")
class TriggerNode_Div(TriggerNode):
    icon = "src/trigger_designer/Resource/icons/divide.png"
    op_code = OP_NODE_DIV
    op_title = "Divide"
    op_type = "CALC"
    content_label = "/"
    content_label_objname = "calc_node_div"
    style = {
    }

    def initInnerClasses(self):
        self.content = OperationContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalOperation(self, input1, input2):
        return input1 / input2

    def execute(self, node_input):
        print("Input")
        print(node_input)


@register_node(OP_NODE_SQRT, "CALC")
class TriggerNode_Sqrt(TriggerNode):
    icon = "src/trigger_designer/Resource/icons/sqrt.png"
    op_code = OP_NODE_SQRT
    op_title = "Square Root"
    op_type = "CALC"
    content_label = "√"
    content_label_objname = "calc_node_sqrt"
    style = {
    }

    def initInnerClasses(self):
        self.content = OperationContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalOperation(self, input1, input2):
        return input1 ** (1/input2)

    def execute(self, node_input):
        print("Input")
        print(node_input)


# way how to register by function call
# register_node_now(OP_NODE_ADD, CalcNode_Add)
