from trigger_conf import register_node, OP_NODE_ADD, OP_NODE_SUB, OP_NODE_MUL, OP_NODE_DIV, OP_NODE_SQRT
from trigger_node_base import TriggerNode


@register_node(OP_NODE_ADD)
class TriggerNode_Add(TriggerNode):
    icon = "icons/add.png"
    op_code = OP_NODE_ADD
    op_title = "Add"
    content_label = "+"
    content_label_objname = "calc_node_bg"

    def evalOperation(self, input1, input2):
        return input1 + input2


@register_node(OP_NODE_SUB)
class CalcNode_Sub(TriggerNode):
    icon = "icons/sub.png"
    op_code = OP_NODE_SUB
    op_title = "Substract"
    content_label = "-"
    content_label_objname = "calc_node_bg"

    def evalOperation(self, input1, input2):
        return input1 - input2


@register_node(OP_NODE_MUL)
class TriggerNode_Mul(TriggerNode):
    icon = "icons/mul.png"
    op_code = OP_NODE_MUL
    op_title = "Multiply"
    content_label = "*"
    content_label_objname = "calc_node_mul"

    def evalOperation(self, input1, input2):
        print('foo')
        return input1 * input2


@register_node(OP_NODE_DIV)
class TriggerNode_Div(TriggerNode):
    icon = "icons/divide.png"
    op_code = OP_NODE_DIV
    op_title = "Divide"
    content_label = "/"
    content_label_objname = "calc_node_div"

    def evalOperation(self, input1, input2):
        return input1 / input2


@register_node(OP_NODE_SQRT)
class TriggerNode_Sqrt(TriggerNode):
    icon = "icons/sqrt.png"
    op_code = OP_NODE_SQRT
    op_title = "Square Root"
    content_label = "√"
    content_label_objname = "calc_node_sqrt"

    def evalOperation(self, input1, input2):
        return input1 ** (1/input2)


# way how to register by function call
# register_node_now(OP_NODE_ADD, CalcNode_Add)
