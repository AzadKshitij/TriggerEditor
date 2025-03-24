from enum import Enum
from dataclasses import dataclass
from typing import Any, List, Optional


class NodeType(Enum):
    FIELD = "FIELD"          # [FieldName]
    LITERAL = "LITERAL"      # Numbers, strings
    BINARY_OP = "BINARY_OP"  # +, -, *, /, >, <, =, >=, <=, !=, AND, OR
    IF_THEN = "IF_THEN"      # IF/THEN/ELSE
    FUNCTION = "FUNCTION"    # Built-in functions like UPPER()
    BETWEEN = "BETWEEN"      # Range comparisons
    IN = "IN"                # List membership
    CASE = "CASE"           # CASE WHEN expressions
    NULL = "NULL"           # NULL value
    NONE = "NULL"           # NULL value


@dataclass
class Node:
    type: NodeType

    def accept(self, visitor):
        """Support for visitor pattern"""
        method_name = f'visit_{self.type.name.lower()}'
        visit = getattr(visitor, method_name, visitor.generic_visit)
        return visit(self)


@dataclass
class Field(Node):
    type: NodeType
    name: str

    def __init__(self, type: NodeType = NodeType.FIELD, name: str = ""):
        super().__init__(type)
        self.name = name


@dataclass
class Literal(Node):
    type: NodeType
    value: Any

    def __init__(self, type: NodeType = NodeType.LITERAL, value: Any = None):
        super().__init__(type)
        self.value = value


@dataclass
class BinaryOp(Node):
    type: NodeType
    left: Node
    operator: str
    right: Node

    def __init__(self, type: NodeType = NodeType.BINARY_OP, left: Node = None, operator: str = "", right: Node = None):
        super().__init__(type)
        self.left = left
        self.operator = operator
        self.right = right


@dataclass
class IfThen(Node):
    type: NodeType
    condition: Node
    then_expr: Node
    else_expr: Optional[Node]

    def __init__(self, type: NodeType = NodeType.IF_THEN, condition: Node = None,
                 then_expr: Node = None, else_expr: Optional[Node] = None):
        super().__init__(type)
        self.condition = condition
        self.then_expr = then_expr
        self.else_expr = else_expr


@dataclass
class Function(Node):
    type: NodeType
    name: str
    arguments: List[Node]

    def __init__(self, type: NodeType = NodeType.FUNCTION, name: str = "", arguments: List[Node] = None):
        super().__init__(type)
        self.name = name
        self.arguments = arguments or []


@dataclass
class Between(Node):
    type: NodeType
    field: Node
    start: Node
    end: Node

    def __init__(self, type: NodeType = NodeType.BETWEEN, field: Node = None,
                 start: Node = None, end: Node = None):
        super().__init__(type)
        self.field = field
        self.start = start
        self.end = end


@dataclass
class In(Node):
    type: NodeType
    field: Node
    values: List[Node]

    def __init__(self, type: NodeType = NodeType.IN, field: Node = None, values: List[Node] = None):
        super().__init__(type)
        self.field = field
        self.values = values or []


@dataclass
class Case(Node):
    type: NodeType
    conditions: List[Node]
    results: List[Node]
    else_result: Optional[Node]

    def __init__(self, type: NodeType = NodeType.CASE, conditions: List[Node] = None,
                 results: List[Node] = None, else_result: Optional[Node] = None):
        super().__init__(type)
        self.conditions = conditions or []
        self.results = results or []
        self.else_result = else_result


@dataclass
class Null(Node):
    type: NodeType = NodeType.NULL

    def __init__(self, type: NodeType = NodeType.NULL):
        super().__init__(type)
