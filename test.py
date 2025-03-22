import duckdb
import pandas as pd
from src.trigger_designer.core.query_lang.tokenizer import Tokenizer, TokenType
from src.trigger_designer.core.query_lang.parser import Parser
from src.trigger_designer.core.query_lang.ast import Node, Field, Literal, BinaryOp, IfThen, Function, NodeType


class DuckDBTranspiler:
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
        else:
            raise ValueError(f"Unsupported AST Node: {node}")

    def transpile_field(self, node: Field) -> str:
        """Handles field references like [FirstName] -> FirstName."""
        return node.name

    def transpile_literal(self, node: Literal) -> str:
        """Handles literals like numbers and strings."""
        if isinstance(node.value, str):
            # Ensure strings are wrapped in single quotes
            return f"'{node.value}'"
        return str(node.value)  # Numbers can be used directly

    def transpile_binary_op(self, node: BinaryOp) -> str:
        """Handles binary operations like +, -, *, /, =, >, <."""
        left = self.transpile(node.left)
        right = self.transpile(node.right)

        # Check for string concatenation and use "||"
        if node.operator == "+":
            return f"CAST({left} AS VARCHAR) || CAST({right} AS VARCHAR)"

        # Default binary operations
        return f"({left} {node.operator} {right})"

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


# class DuckDBTranspiler:
#     def transpile(self, node):
#         if isinstance(node, Field):
#             # DuckDB uses double quotes for identifiers
#             return f'"{node.name}"'

#         if isinstance(node, Literal):
#             return f"'{node.value}'" if isinstance(node.value, str) else str(node.value)

#         if isinstance(node, Node):
#             if node.operator == "+" and isinstance(node.left, Field) and isinstance(node.right, Literal):
#                 return f"{node.left.name} || '{node.right.value}'"

#         if isinstance(node, BinaryOp):
#             left = self.transpile(node.left)
#             right = self.transpile(node.right)
#             if node.operator == "+" and isinstance(node.left, Field) and isinstance(node.right, Literal):
#                 return f"{node.left.name} || '{node.right.value}'"
#             return f"({left} {node.operator} {right})"

#         if isinstance(node, IfThen):
#             condition = self.transpile(node.condition)
#             then_expr = self.transpile(node.then_expr)
#             else_expr = self.transpile(
#                 node.else_expr) if node.else_expr else "NULL"
#             return f"CASE WHEN {condition} THEN {then_expr} ELSE {else_expr} END"

#         if isinstance(node, Function):
#             args = ", ".join(self.transpile(arg) for arg in node.arguments)
#             return f"{node.name.upper()}({args})"

#         raise ValueError(f"Unknown node type: {type(node)}")
tokenizer = Tokenizer("""IF [Age] > 30 THEN 
                    UPPER([FirstName]) + ' ' + [LastName]
                 ELSE 
                    [FirstName] + ' ' + LOWER([LastName])"""
                      )

tokens = []
while True:
    token = tokenizer.next_token()
    tokens.append(token)
    if token.type == TokenType.EOF:
        break

for token in tokens:
    print(token)

parser = Parser(tokens)
ast = parser.parse()

transpiler = DuckDBTranspiler()
sql = transpiler.transpile(ast)
print("🐍 File: TriggerEditor/test.py | Line: 119 | undefined ~ sql", sql)


data = {
    "id": [1, 2, 3, 4, 5, 6, 7, 8],
    "FirstName": ["John", "Jane", "Emily", "Michael", "Chris", "Anna", "James", "Sophia"],
    "LastName": ["Doe", "Smith", "Johnson", "Brown", "Davis", "Wilson", "Moore", "Taylor"],
    "Age": [28, 34, 40, 30, 25, 29, 37, 32],
    "gender": ["Male", "Female", "Female", "Male", "Male", "Female", "Male", "Female"],
    "city": ["New York", "Los Angeles", "Chicago", "Houston", "San Francisco", "Seattle", "Boston", "Denver"],
    "salary": [55000, 62000, 75000, 58000, 48000, 52000, 69000, 60000]
}

df = pd.DataFrame(data)

con = duckdb.connect()
emp = con.execute("SELECT * FROM df")

print(emp.fetchdf())

res = con.execute(f"""
                  SELECT 
                      *,
                      {sql}
                  FROM df
                  """)

print(res.fetchdf())
