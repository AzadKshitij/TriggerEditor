import importlib
from typing import Callable, Dict, TYPE_CHECKING, Union
from enum import IntEnum, StrEnum, auto

__all__ = [
    "NodeTypes",
    "IONodes",
    "PreparationNodes",
    "JoinNodes",
    "TransformNodes",
    "ReportNodes",
    "register_node",
    "register_lazy_node",
    "get_class_from_opcode",
    "get_class_from_op",
    "migrate_v1_data",
]

if TYPE_CHECKING:
    from trigger_designer.qt.node_base import TriggerNode


class NodeTypes(StrEnum):
    IO = "input"
    PREPARATION = "preparation"
    JOIN = "join"
    TRANSFORM = "transform"
    REPORT = "report"


class IONodes(IntEnum):
    BROWSER = auto()
    TEXT_INPUT = auto()
    FILE_INPUT = auto()
    FILE_OUTPUT = auto()


class PreparationNodes(IntEnum):
    CLEANSING = auto()
    FILTER = auto()
    FORMULA = auto()
    GROUPBY = auto()
    SELECT = auto()
    SORT = auto()
    UNIQUE = auto()
    SPLIT = auto()
    DYNAMIC_ROW_BUILDER = auto()


class JoinNodes(IntEnum):
    APPEND = auto()
    JOIN = auto()
    UNION = auto()


class TransformNodes(IntEnum):
    ARRANGE = auto()
    COUNT_RECORDS = auto()
    RUNNING_TOTAL = auto()
    TRANSPOSE = auto()


class ReportNodes(IntEnum):

    GRAPH = auto()


# Node registries
NODE_REGISTRIES: Dict[NodeTypes, Dict[int, "TriggerNode"]] = {
    NodeTypes.IO: {},
    NodeTypes.PREPARATION: {},
    NodeTypes.JOIN: {},
    NodeTypes.TRANSFORM: {},
    NodeTypes.REPORT: {},
}

# Opcode enums keyed by family. Used to resolve stable op ids
# ("<family>.<NAME>", e.g. "preparation.sort") without touching ints.
_OPCODE_ENUMS = {
    NodeTypes.IO: IONodes,
    NodeTypes.PREPARATION: PreparationNodes,
    NodeTypes.JOIN: JoinNodes,
    NodeTypes.TRANSFORM: TransformNodes,
    NodeTypes.REPORT: ReportNodes,
}

# Frozen v1 numbering (pre-stable-op). Maps (family, int code) as stored
# in schema v1 files to stable op ids. NEVER edit: new codes only ever
# get new op ids, old numbers are never reused.
# Covers deleted codes too (calc/*, browser, ...) so they load as a
# visible placeholder instead of silently becoming the wrong node.
V1_OPCODE_TO_OP: Dict[tuple, str] = {
    ("input", 1): "input.browser",
    ("input", 2): "input.directory",
    ("input", 3): "input.text_input",
    ("input", 4): "input.file_input",
    ("input", 5): "input.file_output",
    ("input", 6): "input.text_output",
    ("preparation", 1): "preparation.cleansing",
    ("preparation", 2): "preparation.filter",
    ("preparation", 3): "preparation.formula",
    ("preparation", 4): "preparation.groupby",
    ("preparation", 5): "preparation.select",
    ("preparation", 6): "preparation.sort",
    ("preparation", 7): "preparation.unique",
    ("preparation", 8): "preparation.split",
    ("preparation", 9): "preparation.dynamic_row_builder",
    ("join", 1): "join.append",
    ("join", 2): "join.join",
    ("join", 3): "join.union",
    ("transform", 1): "transform.arrange",
    ("transform", 2): "transform.count_records",
    ("transform", 3): "transform.running_total",
    ("transform", 4): "transform.transpose",
    ("report", 1): "report.table",
    ("report", 2): "report.plot",
    ("report", 3): "report.graph",
}

LISTBOX_MIMETYPE = "application/x-item"


class ConfException(Exception):
    """Base exception for configuration errors"""


class InvalidNodeRegistration(ConfException):
    """Raised when attempting to register a node with a duplicate node_code"""


class OpCodeNotRegistered(ConfException):
    """Raised when attempting to get an unregistered node_code"""


class LazyNodeReference:
    def __init__(
        self,
        *,
        node_code: int,
        node_type: NodeTypes,
        module_path: str,
        node_title: str,
        icon: str,
    ) -> None:
        self.node_code = node_code
        self.node_type = node_type
        self.module_path = module_path
        self.node_title = node_title
        self.icon = icon

    def load(self):
        registry = NODE_REGISTRIES[self.node_type]
        current = registry.get(self.node_code)
        if current is not None and not isinstance(current, LazyNodeReference):
            return current

        importlib.import_module(self.module_path)
        loaded = registry.get(self.node_code)
        if loaded is None or isinstance(loaded, LazyNodeReference):
            raise OpCodeNotRegistered(
                f"Lazy node import failed for '{self.module_path}' ({self.node_type}:{self.node_code})"
            )
        return loaded

    def __call__(self, *args, **kwargs):
        return self.load()(*args, **kwargs)


# def register_node_now(node_code: IntEnum, class_reference: 'TriggerNode', node_type: NodeTypes) -> None:

#     current_node_type: Dict[int, 'TriggerNode'] = check_node_type(node_type)

#     if node_code in current_node_type:
#         raise InvalidNodeRegistration("Duplicate node registration of '%s'. There is already %s" % (
#             node_code, current_node_type[node_code]
#         ))
#     current_node_type[node_code] = class_reference


def register_node_now(
    node_code: int, class_reference: "TriggerNode", node_type: NodeTypes
) -> None:
    if node_type not in NodeTypes:
        raise InvalidNodeRegistration(f"Invalid node type: {node_type}")

    registry = NODE_REGISTRIES[NodeTypes(node_type)]
    if node_code in registry:
        if isinstance(registry[node_code], LazyNodeReference):
            registry[node_code] = class_reference
            return
        raise InvalidNodeRegistration(
            f"Duplicate node registration of '{node_code}'. There is already {registry[node_code]}"
        )
    registry[node_code] = class_reference


def register_lazy_node(
    node_code: int,
    node_type: NodeTypes,
    *,
    module_path: str,
    node_title: str,
    icon: str,
) -> None:
    if node_type not in NodeTypes:
        raise InvalidNodeRegistration(f"Invalid node type: {node_type}")

    registry = NODE_REGISTRIES[NodeTypes(node_type)]
    if node_code in registry:
        raise InvalidNodeRegistration(
            f"Duplicate node registration of '{node_code}'. There is already {registry[node_code]}"
        )

    registry[node_code] = LazyNodeReference(
        node_code=node_code,
        node_type=NodeTypes(node_type),
        module_path=module_path,
        node_title=node_title,
        icon=icon,
    )


def register_node(node_code: int, node_type: NodeTypes) -> Callable:
    def decorator(original_class: "TriggerNode") -> "TriggerNode":
        register_node_now(node_code, original_class, node_type)
        return original_class

    return decorator


def get_class_from_opcode(
    node_code: int, node_type: Union[NodeTypes, str]
) -> "TriggerNode":
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
        node_type_enum = (
            NodeTypes(node_type) if isinstance(node_type, str) else node_type
        )
    except ValueError:
        raise OpCodeNotRegistered(f"Invalid node type: {node_type}")

    registry = NODE_REGISTRIES[node_type_enum]
    if node_code not in registry:
        raise OpCodeNotRegistered(f"OpCode '{node_code}' is not registered")

    if isinstance(registry[node_code], LazyNodeReference):
        registry[node_code] = registry[node_code].load()

    return registry[node_code]


def get_class_from_op(op: str) -> "TriggerNode":
    """Resolve a stable op id ("<family>.<NAME>") to its node class.

    Op ids derive from enum member *names*, so inserting, removing, or
    reordering members never changes them. Add new members freely;
    never rename existing ones (old files reference them).

    Raises:
        OpCodeNotRegistered: If the family/name is unknown or unregistered.
    """
    family, sep, name = op.partition(".")
    if not sep or not name:
        raise OpCodeNotRegistered(f"Invalid op id: {op!r}")
    try:
        node_type_enum = NodeTypes(family)
    except ValueError:
        raise OpCodeNotRegistered(f"Invalid op family: {family!r}")
    try:
        node_code = _OPCODE_ENUMS[node_type_enum][name.upper()]
    except KeyError:
        raise OpCodeNotRegistered(f"Op name '{name}' is not registered")
    return get_class_from_opcode(node_code, node_type_enum)


def migrate_v1_data(data: dict) -> Union[str, None]:
    """Map a v1 node dict to its stable op id. None if unmappable.

    Accepts current-style {"node_code": int, "node_type": str} and
    oldest-style {"op_code": int, "op_type": UPPERCASE} keys.
    """
    if "node_code" in data:
        family, code = data.get("node_type"), data.get("node_code")
    elif "op_code" in data:
        family, code = str(data.get("op_type", "")
                           ).lower(), data.get("op_code")
    else:
        return None
    try:
        return V1_OPCODE_TO_OP.get((family, int(code)))
    except (TypeError, ValueError):
        return None


# import all nodes and register them
from trigger_designer.qt.widgets.nodes import *  # noqa: E402
