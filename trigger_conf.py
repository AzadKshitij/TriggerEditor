LISTBOX_MIMETYPE = "application/x-item"

OP_NODE_INPUT = 1
OP_NODE_OUTPUT = 2
OP_NODE_ADD = 3
OP_NODE_SUB = 4
OP_NODE_MUL = 5
OP_NODE_DIV = 6
OP_NODE_SQRT = 7
OP_NODE_FILE_INPUT = 8
OP_NODE_SELECT = 9
OP_NODE_TEXT_OUTPUT = 10


CALC_NODES = {
}

INPUT_NODES = {}

PREPARATION_NODES = {}


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
        
        case _:
            return "You have another type of pet."



def get_class_from_opcode(op_code, node_type):
    current_node_type = check_node_type(node_type)
    if op_code not in current_node_type:
        raise OpCodeNotRegistered("OpCode '%d' is not registered" % op_code)
    return current_node_type[op_code]


# import all nodes and register them
from nodes import *