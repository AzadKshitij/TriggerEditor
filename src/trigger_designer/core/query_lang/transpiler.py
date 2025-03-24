from typing import List, Union
import duckdb
import pandas as pd
from .tokenizer import Tokenizer, TokenType
from .parser import Parser
from .ast import (
    Node, Field, Literal, BinaryOp, IfThen, Function,
    Between, In, Case, Null, NodeType
)
# from src.trigger_designer.core.query_lang.tokenizer import Tokenizer, TokenType
# from src.trigger_designer.core.query_lang.parser import Parser
# from src.trigger_designer.core.query_lang.ast import Node, Field, Literal, BinaryOp, IfThen, Function, NodeType


class DuckDBTranspiler:

    # Map of our formula operators to DuckDB SQL operators
    OPERATOR_MAP = {
        "+": "+",
        "-": "-",
        "*": "*",
        "/": "/",
        "=": "=",
        ">": ">",
        "<": "<",
        ">=": ">=",
        "<=": "<=",
        "!=": "!=",
        "AND": "AND",
        "OR": "OR"
    }

    # Set of functions that need special handling
    STRING_FUNCTIONS = {"CONCAT", "UPPER", "LOWER", "TRIM", "SUBSTRING"}
    NUMERIC_FUNCTIONS = {"ABS", "ROUND", "FLOOR", "CEILING"}
    DATE_FUNCTIONS = {"YEAR", "MONTH", "DAY", "DATEADD", "DATEDIFF"}

    def transpile(self, node: Node) -> str:
        """Translates the AST into a DuckDB SQL query."""
        if isinstance(node, Field):
            return self.transpile_field(node)
        elif isinstance(node, Literal):
            return self.transpile_literal(node)
        elif isinstance(node, BinaryOp):
            return self.transpile_binary_op(node)
        elif isinstance(node, IfThen):
            return self.transpile_if_then(node)
        elif isinstance(node, Function):
            return self.transpile_function(node)
        elif isinstance(node, Between):
            return self.transpile_between(node)
        elif isinstance(node, In):
            return self.transpile_in(node)
        elif isinstance(node, Case):
            return self.transpile_case(node)
        elif isinstance(node, Null):
            return "NULL"
        else:
            raise ValueError(f"Unsupported AST Node: {node}")

    def transpile_field(self, node: Field) -> str:
        """Handles field references like [FirstName] -> "FirstName" """
        # Use double quotes for field names to handle case sensitivity
        return f'"{node.name}"'

    def transpile_literal(self, node: Literal) -> str:
        """Handles literals like numbers and strings."""
        if node.value is None:
            return "NULL"
        elif isinstance(node.value, str):
            # Escape single quotes in strings
            escaped = node.value.replace("'", "''")
            return f"'{escaped}'"
        elif isinstance(node.value, bool):
            return str(node.value).upper()
        return str(node.value)

    def transpile_binary_op(self, node: BinaryOp) -> str:
        """Handles binary operations."""
        left = self.transpile(node.left)
        right = self.transpile(node.right)
        operator = self.OPERATOR_MAP.get(node.operator.upper(), node.operator)

        # Handle string concatenation
        if operator == "+":
            if self._might_be_string(node.left) or self._might_be_string(node.right):
                return f"CONCAT({left}, {right})"

        return f"({left} {operator} {right})"

    def transpile_between(self, node: Between) -> str:
        """Handles BETWEEN expressions."""
        field = self.transpile(node.field)
        start = self.transpile(node.start)
        end = self.transpile(node.end)
        return f"{field} BETWEEN {start} AND {end}"

    def transpile_in(self, node: In) -> str:
        """Handles IN expressions."""
        field = self.transpile(node.field)
        values = [self.transpile(value) for value in node.values]
        return f"{field} IN ({', '.join(values)})"

    def transpile_case(self, node: Case) -> str:
        """Handles CASE expressions."""
        parts = ["CASE"]

        for condition, result in zip(node.conditions, node.results):
            when_clause = self.transpile(condition)
            then_clause = self.transpile(result)
            parts.append(f"WHEN {when_clause} THEN {then_clause}")

        if node.else_result:
            parts.append(f"ELSE {self.transpile(node.else_result)}")

        parts.append("END")
        return " ".join(parts)

    def transpile_function(self, node: Function) -> str:
        """Handles function calls."""
        func_name = node.name.upper()
        args = [self.transpile(arg) for arg in node.arguments]

        # Handle special function cases
        if func_name in self.STRING_FUNCTIONS:
            return self._handle_string_function(func_name, args)
        elif func_name in self.NUMERIC_FUNCTIONS:
            return self._handle_numeric_function(func_name, args)
        elif func_name in self.DATE_FUNCTIONS:
            return self._handle_date_function(func_name, args)

        return f"{func_name}({', '.join(args)})"

    def transpile_if_then(self, node: IfThen) -> str:
        """Handles IF-THEN-ELSE expressions."""
        condition = self.transpile(node.condition)
        then_expr = self.transpile(node.then_expr)
        else_expr = self.transpile(
            node.else_expr) if node.else_expr else "NULL"
        return f"CASE WHEN {condition} THEN {then_expr} ELSE {else_expr} END"

    def transpile_function(self, node: Function) -> str:
        """Handles function calls like UPPER(FirstName)."""
        args = ", ".join(self.transpile(arg) for arg in node.arguments)
        return f"{node.name.upper()}({args})"

    def _might_be_string(self, node: Node) -> bool:
        """Helper to determine if a node might produce a string value."""
        if isinstance(node, Literal):
            return isinstance(node.value, str)
        elif isinstance(node, Function):
            return node.name.upper() in self.STRING_FUNCTIONS
        return True  # Assume it might be a string if we're not sure

    def _handle_string_function(self, func_name: str, args: List[str]) -> str:
        """Handle special cases for string functions."""
        if func_name == "CONCAT":
            return " || ".join(args)
        return f"{func_name}({', '.join(args)})"

    def _handle_numeric_function(self, func_name: str, args: List[str]) -> str:
        """Handle special cases for numeric functions."""
        return f"{func_name}({', '.join(args)})"

    def _handle_date_function(self, func_name: str, args: List[str]) -> str:
        """Handle special cases for date functions."""
        return f"{func_name}({', '.join(args)})"
