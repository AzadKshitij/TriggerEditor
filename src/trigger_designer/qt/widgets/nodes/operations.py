from qtpy.QtWidgets import QLayout, QVBoxLayout

from trigger_designer.core.node_configuration import register_node, NodeTypes, CalcNodes
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.node_base import TriggerNode, TriggerGraphicsNode

from nodeeditor.node_content_widget import QDMNodeContentWidget


class OperationContent(QDMNodeContentWidget):
    def create_layout(self) -> QLayout:
        layout = QVBoxLayout()
        return layout


@register_node(CalcNodes.ADD, NodeTypes.CALC)
class TriggerNode_Add(TriggerNode):
    icon = "src/trigger_designer/Resource/icons/add.png"
    node_code = CalcNodes.ADD
    node_title = "Add"
    node_type = NodeTypes.CALC
    content_label = "+"
    content_label_objname = "calc_node_bg"
    style = {
    }

    def initInnerClasses(self) -> None:
        self.content = OperationContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalOperation(self, input1, input2):
        print("#############")
        print("Add evalOperation")
        print("#############")
        return input1 + input2

    def execute(self, node_input) -> None:
        print("Input")
        print(node_input)


@register_node(CalcNodes.SUB, NodeTypes.CALC)
class CalcNode_Sub(TriggerNode):
    icon = "src/trigger_designer/Resource/icons/sub.png"
    node_code = CalcNodes.SUB
    node_title = "Substract"
    node_type = NodeTypes.CALC
    content_label = "-"
    content_label_objname = "calc_node_bg"
    style = {
    }

    def initInnerClasses(self) -> None:
        self.content = OperationContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalOperation(self, input1, input2):
        print("#############")
        print("Sub evalOperation")
        print("#############")
        return input1 - input2

    def execute(self, node_input) -> None:
        print("Input")
        print(node_input)


@register_node(CalcNodes.MUL, NodeTypes.CALC)
class TriggerNode_Mul(TriggerNode):
    icon = "src/trigger_designer/Resource/icons/mul.png"
    node_code = CalcNodes.MUL
    node_title = "Multiply"
    node_type = NodeTypes.CALC
    content_label = "*"
    content_label_objname = "calc_node_mul"
    style = {
    }

    def initInnerClasses(self) -> None:
        self.content = OperationContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalOperation(self, input1, input2):
        print('foo')
        return input1 * input2

    def execute(self, node_input) -> None:
        print("Input")
        print(node_input)


@register_node(CalcNodes.DIV, NodeTypes.CALC)
class TriggerNode_Div(TriggerNode):
    icon = "src/trigger_designer/Resource/icons/divide.png"
    node_code = CalcNodes.DIV
    node_title = "Divide"
    node_type = NodeTypes.CALC
    content_label = "/"
    content_label_objname = "calc_node_div"
    style = {
    }

    def initInnerClasses(self) -> None:
        self.content = OperationContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalOperation(self, input1, input2):
        return input1 / input2

    def execute(self, node_input) -> None:
        print("Input")
        print(node_input)


@register_node(CalcNodes.SQRT, NodeTypes.CALC)
class TriggerNode_Sqrt(TriggerNode):
    icon = "src/trigger_designer/Resource/icons/sqrt.png"
    node_code = CalcNodes.SQRT
    node_title = "Square Root"
    node_type = NodeTypes.CALC
    content_label = "√"
    content_label_objname = "calc_node_sqrt"
    style = {
    }

    def initInnerClasses(self) -> None:
        self.content = OperationContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def evalOperation(self, input1, input2):
        return input1 ** (1/input2)

    def execute(self, node_input) -> None:
        print("Input")
        print(node_input)


# way how to register by function call
# register_node_now(OP_NODE_ADD, CalcNode_Add)
