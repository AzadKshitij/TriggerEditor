from typing import Callable, Dict, TYPE_CHECKING, Union
from enum import IntEnum, StrEnum, auto

__all__ = [
    "NodeTypes",
    "CalcNodes",
    "IONodes",
    "PreparationNodes",
    "JoinNodes",
    "TransformNodes",
    "register_node",
    "get_class_from_opcode",
]

if TYPE_CHECKING:
    from trigger_designer.qt.node_base import TriggerNode


class NodeTypes(StrEnum):
    IO = "input"
    CALC = "calc"
    PREPARATION = "preparation"
    JOIN = "join"
    TRANSFORM = "transform"
    REPORT = "report"
    # Add more node types as needed


class CalcNodes(IntEnum):
    INPUT = auto()
    OUTPUT = auto()
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    SQRT = auto()


class IONodes(IntEnum):
    BROWSER = auto()
    DIRECTORY = auto()
    TEXT_INPUT = auto()
    FILE_INPUT = auto()
    FILE_OUTPUT = auto()
    TEXT_OUTPUT = auto()


class PreparationNodes(IntEnum):
    CLEANSING = auto()
    FILTER = auto()
    FORMULA = auto()
    SELECT = auto()
    SORT = auto()
    UNIQUE = auto()


class JoinNodes(IntEnum):
    APPEND = auto()
    JOIN = auto()
    UNION = auto()


class TransformNodes(IntEnum):
    ARRANGE = auto()
    COUNT_RECORDS = auto()


class ReportNodes(IntEnum):
    TABLE = auto()
    PLOT = auto()
    GRAPH = auto()


# Node registries
NODE_REGISTRIES: Dict[NodeTypes,  Dict[int, 'TriggerNode']] = {
    NodeTypes.CALC: {},
    NodeTypes.IO: {},
    NodeTypes.PREPARATION: {},
    NodeTypes.JOIN: {},
    NodeTypes.TRANSFORM: {},
    NodeTypes.REPORT: {},
}

LISTBOX_MIMETYPE = "application/x-item"


class ConfException(Exception):
    """Base exception for configuration errors"""


class InvalidNodeRegistration(ConfException):
    """Raised when attempting to register a node with a duplicate node_code"""


class OpCodeNotRegistered(ConfException):
    """Raised when attempting to get an unregistered node_code"""


# def register_node_now(node_code: IntEnum, class_reference: 'TriggerNode', node_type: NodeTypes) -> None:

#     current_node_type: Dict[int, 'TriggerNode'] = check_node_type(node_type)

#     if node_code in current_node_type:
#         raise InvalidNodeRegistration("Duplicate node registration of '%s'. There is already %s" % (
#             node_code, current_node_type[node_code]
#         ))
#     current_node_type[node_code] = class_reference


def register_node_now(node_code: int, class_reference: 'TriggerNode', node_type: NodeTypes) -> None:
    if node_type not in NodeTypes:
        raise InvalidNodeRegistration(f"Invalid node type: {node_type}")

    registry = NODE_REGISTRIES[NodeTypes(node_type)]
    if node_code in registry:
        raise InvalidNodeRegistration(
            f"Duplicate node registration of '{node_code}'. There is already {registry[node_code]}"
        )
    registry[node_code] = class_reference


def register_node(node_code: int, node_type: NodeTypes) -> Callable:
    def decorator(original_class: 'TriggerNode') -> 'TriggerNode':
        register_node_now(node_code, original_class, node_type)
        return original_class
    return decorator


# def check_node_type(node_type: str) -> Dict:
#     match node_type:
#         case NodeTypes.INPUT:
#             return INPUT_NODES
#         case NodeTypes.CALC:
#             return CALC_NODES
#         case NodeTypes.PREPARATION:
#             return PREPARATION_NODES
#         case NodeTypes.JOIN:
#             return JOIN_NODES
#         case NodeTypes.TRANSFORM:
#             return TRANSFORM_NODES

#         case _:
#             return {}


def get_class_from_opcode(node_code: int, node_type: Union[NodeTypes, str]) -> 'TriggerNode':
    """Get node class from opcode and type.

    Args:
        node_code (int): The node's operation code
        node_type (Union[NodeTypes, str]): Node type enum or string value

    Returns:
        TriggerNode: The node class

    Raises:
        OpCodeNotRegistered: If node_type or node_code is invalid
    """
    try:
        # Convert string to enum if needed
        node_type_enum = NodeTypes(node_type) if isinstance(
            node_type, str) else node_type
    except ValueError:
        raise OpCodeNotRegistered(f"Invalid node type: {node_type}")

    registry = NODE_REGISTRIES[node_type_enum]
    if node_code not in registry:
        raise OpCodeNotRegistered(f"OpCode '{node_code}' is not registered")

    return registry[node_code]


# import all nodes and register them
from trigger_designer.qt.widgets.nodes import *  # noqa: E402
