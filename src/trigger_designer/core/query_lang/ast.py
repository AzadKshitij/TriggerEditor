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
    name: str
    type: NodeType = NodeType.FIELD


@dataclass
class Literal(Node):
    value: Any
    type: NodeType = NodeType.LITERAL


@dataclass
class BinaryOp(Node):
    left: Node
    operator: str
    right: Node
    type: NodeType = NodeType.BINARY_OP


@dataclass
class IfThen(Node):
    condition: Node
    then_expr: Node
    else_expr: Optional[Node] = None
    type: NodeType = NodeType.IF_THEN


@dataclass
class Function(Node):
    name: str
    arguments: List[Node]
    type: NodeType = NodeType.FUNCTION


@dataclass
class Between(Node):
    field: Node
    start: Node
    end: Node
    type: NodeType = NodeType.BETWEEN


@dataclass
class In(Node):
    field: Node
    values: List[Node]
    type: NodeType = NodeType.IN


@dataclass
class Case(Node):
    conditions: List[Node]
    results: List[Node]
    else_result: Optional[Node] = None
    type: NodeType = NodeType.CASE


@dataclass
class Null(Node):
    type: NodeType = NodeType.NULL
