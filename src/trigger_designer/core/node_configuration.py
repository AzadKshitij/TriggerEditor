LISTBOX_MIMETYPE = "application/x-item"

# Calc
OP_NODE_INPUT = 1
OP_NODE_OUTPUT = 2
OP_NODE_ADD = 3
OP_NODE_SUB = 4
OP_NODE_MUL = 5
OP_NODE_DIV = 6
OP_NODE_SQRT = 7

# InOut
OP_NODE_BROWSER = 1
OP_NODE_DIRECTORY = 2
OP_NODE_TEXT_INPUT = 3
OP_NODE_FILE_INPUT = 4
OP_NODE_FILE_OUTPUT = 5
OP_NODE_TEXT_OUTPUT = 6


# Preparation
OP_NODE_CLEANSING = 1
OP_NODE_FILTER = 2
OP_NODE_FORMULA = 3
OP_NODE_SELECT = 4
OP_NODE_SORT = 5
OP_NODE_UNIQUE = 6

# Join
OP_NODE_APPEND = 1
OP_NODE_JOIN = 2
OP_NODE_UNION = 3

# Transform
OP_NODE_ARRANGE = 1
OP_NODE_COUNTRECORDS = 2


CALC_NODES: dict = {}
INPUT_NODES: dict = {}
PREPARATION_NODES: dict = {}
JOIN_NODES: dict = {}
TRANSFORM_NODES: dict = {}


class ConfException(Exception):
    pass


class InvalidNodeRegistration(ConfException):
    pass


class OpCodeNotRegistered(ConfException):
    pass


def register_node_now(op_code, class_reference, node_type):

    current_node_type = check_node_type(node_type)

    if op_code in current_node_type:
        raise InvalidNodeRegistration("Duplicate node registration of '%s'. There is already %s" % (
            op_code, current_node_type[op_code]
        ))
    current_node_type[op_code] = class_reference


def register_node(op_code, node_type):
    def decorator(original_class):
        register_node_now(op_code, original_class, node_type)
        return original_class
    return decorator


def check_node_type(node_type):
    match node_type:
        case "INPUT":
            return INPUT_NODES
        case "CALC":
            return CALC_NODES
        case "PREPARATION":
            return PREPARATION_NODES
        case "JOIN":
            return JOIN_NODES
        case "TRANSFORM":
            return TRANSFORM_NODES

        case _:
            return "You have another type of pet."


def get_class_from_opcode(op_code, node_type):
    current_node_type = check_node_type(node_type)
    if op_code not in current_node_type:
        raise OpCodeNotRegistered("OpCode '%d' is not registered" % op_code)
    return current_node_type[op_code]


# import all nodes and register them
from trigger_designer.qt.widgets.nodes import *  # noqa: E402
