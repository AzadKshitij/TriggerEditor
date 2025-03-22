import duckdb
import pandas as pd
from src.trigger_designer.core.query_lang.tokenizer import Tokenizer, TokenType
from src.trigger_designer.core.query_lang.parser import Parser
from src.trigger_designer.core.query_lang.ast import Node, Field, Literal, BinaryOp, IfThen, Function, NodeType
from src.trigger_designer.core.query_lang.transpiler import DuckDBTranspiler


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

formula1 = """
IF [Age] BETWEEN 25 AND 35 THEN
    UPPER([FirstName]) + ' ' + [LastName]
ELSE
    CASE
        WHEN [Salary] >= 50000 THEN 'High'
        WHEN [Salary] >= 30000 THEN 'Medium'
        ELSE 'Low'
    END
"""
formula2 = """
CASE
    WHEN [Age] BETWEEN 20 AND 30 AND [Salary] >= 50000 THEN 'Young High Earner'
    WHEN [Department] IN ('Sales', 'Marketing') THEN 'Revenue Team'
    ELSE 'Other'
END
"""
formula3 = """
CASE
    WHEN [Age] BETWEEN 20 AND 30 AND [Salary] >= 50000 THEN 'Young High Earner'
    WHEN [Department] IN ('Sales', 'Marketing') THEN 'Revenue Team'
    ELSE UPPER([FirstName]) + ' ' + [LastName]
END
"""

formula4 = """IF [Age] > 30 THEN 
                    UPPER([FirstName]) + ' ' + [LastName]
                 ELSE 
                    [FirstName] + ' ' + LOWER([LastName])"""


def test_formula(formula: str, data: pd.DataFrame) -> pd.DataFrame:
    """Test a formula against the data"""
    tokenizer = Tokenizer(formula)
    tokens = []
    while True:
        token = tokenizer.next_token()
        tokens.append(token)
        if token.type == TokenType.EOF:
            break

    parser = Parser(tokens)
    ast = parser.parse()
    transpiler = DuckDBTranspiler()
    sql = transpiler.transpile(ast)

    print(f"Generated SQL:\n{sql}\n")

    con = duckdb.connect()
    result = con.execute(f"""
        SELECT 
            *,
            {sql} as result
        FROM df
    """)
    return result.fetchdf()


# Test data
data = {
    "FirstName": ["John", "Jane", "Emily", "Michael", "Chris"],
    "LastName": ["Doe", "Smith", "Johnson", "Brown", "Davis"],
    "Age": [28, 34, 40, 30, 25],
    "Salary": [55000, 62000, 75000, 58000, 48000],
    "Department": ["Sales", "Marketing", "IT", "Sales", "Marketing"]
}
df = pd.DataFrame(data)

# Test different formulas
formulas = [
    # Simple BETWEEN
    "[Age] BETWEEN 20 AND 30",

    # BETWEEN with AND
    "[Age] BETWEEN 20 AND 30 AND [Salary] >= 50000",

    # Simple concatenation
    "[FirstName] + ' ' + [LastName]",

    # IF THEN ELSE
    """
    IF [Age] > 30 THEN 
        UPPER([FirstName]) + ' ' + [LastName]
    ELSE 
        [FirstName] + ' ' + LOWER([LastName])
    """,

    # CASE statement
    """
    CASE
        WHEN [Age] BETWEEN 20 AND 30 AND [Salary] >= 50000 THEN 
            'Young High Earner'
        WHEN [Department] IN ('Sales', 'Marketing') THEN 
            'Revenue Team'
        ELSE 
            UPPER([FirstName]) + ' ' + [LastName]
    END
    """,

    # Check for types
    """
    IF [Age] BETWEEN 25 AND 35 THEN
        UPPER([FirstName]) + ' ' + [LastName]
    ELSE
        CASE
            WHEN [Salary] >= 50000 THEN 'High'
            WHEN [Salary] >= 30000 THEN 'Medium'
            ELSE 'Low'
        END
    """,

]


# Run tests
for i, formula in enumerate(formulas, 1):
    print(f"\nTesting Formula {i}:")
    print(f"{'='*50}")
    print(f"Formula:\n{formula}\n")
    result = test_formula(formula, df)
    print("\nResult:")
    print(result[["FirstName", "LastName", "result"]])
    print(f"{'='*50}\n")
