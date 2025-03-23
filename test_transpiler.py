import duckdb
import pandas as pd
from src.trigger_designer.core.query_lang.tokenizer import Tokenizer, TokenType
from src.trigger_designer.core.query_lang.parser import Parser
from src.trigger_designer.core.query_lang.ast import Node, Field, Literal, BinaryOp, IfThen, Function, NodeType
from src.trigger_designer.core.query_lang.transpiler import DuckDBTranspiler
from src.trigger_designer.core.query_lang.validator import FormulaValidator


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
    tokens = tokenizer.tokenize()

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

    # Invalid formulas
    "[Age] BETWEEN 20 30",  # Missing AND
    "IF [Salary] > THEN 'High'",  # Missing comparison value
    "CASE WHEN [Age] > 30 'Adult' END",  # Missing THEN
    "[FirstName] + [LastName",  # Unclosed field reference


    # Special characters in fields
    "[Total.Amount] > 1000",
    "[User@Domain] = 'test@example.com'",

    # Special characters in functions
    "SUM.2([Value.1], [Value.2])",
    "AVG.3([Score.1], [Score.2], [Score.3])",

    # Special characters in literals
    "[@SpecialValue] = '#123'",
    "[Percentage] > 99.9%",

    # Complex expressions with special characters
    """
    CASE
        WHEN [User.Type] = '@Admin' THEN
            [First.Name] + '.' + [Last.Name]
        WHEN [Department.Code] IN ('#Sales', '#Marketing') THEN
            [Employee.ID] + '@' + [Division.Code]
        ELSE
            [Default.Value]
    END
    """

]


def run_test_case(formula: str, expected_valid: bool, expected_error: str = None) -> bool:
    """Run a single test case and return True if it passes"""
    is_valid, ast, error = FormulaValidator.validate(formula)

    # Check validity matches expectation
    if is_valid != expected_valid:
        print(f"❌ Test failed for formula:\n{formula}")
        print(f"Expected valid: {expected_valid}, got: {is_valid}")
        if error:
            print(f"Error: {error}")
        return False

    # For invalid formulas, check error message
    if not expected_valid and expected_error:
        if expected_error not in str(error):
            print(f"❌ Test failed for formula:\n{formula}")
            print(f"Expected error containing: {expected_error}")
            print(f"Got error: {error}")
            return False

    print(f"✓ Test passed for formula:\n{formula}")
    return True


def run_all_tests():
    """Run all formula validation tests"""
    test_cases = [
        # Valid formulas
        {
            "formula": "[Age] BETWEEN 20 AND 30",
            "valid": True
        },
        {
            "formula": "[FirstName] + ' ' + [LastName]",
            "valid": True
        },
        {
            "formula": """
            CASE
                WHEN [Age] BETWEEN 20 AND 30 AND [Salary] >= 50000 THEN 
                    'Young High Earner'
                WHEN [Department] IN ('Sales', 'Marketing') THEN 
                    'Revenue Team'
                ELSE 
                    UPPER([FirstName]) + ' ' + [LastName]
            END
            """,
            "valid": True
        },

        # Invalid formulas
        {
            "formula": "[FirstName] + [LastName",
            "valid": False,
            "expected_error": "Unclosed field reference"
        },
        {
            "formula": "IF [Salary] > THEN 'High'",
            "valid": False,
            "expected_error": "Unexpected keyword: THEN"
        },
        {
            "formula": "[Age] BETWEEN 20 30",
            "valid": False,
            "expected_error": "Expected 'AND'"
        },

        # Special character tests
        {
            "formula": "[Total.Amount] > 1000",
            "valid": True
        },
        {
            "formula": "[User@Domain] = 'test@example.com'",
            "valid": True
        },
        {
            "formula": "[Department] IN ('#Sales', '#Marketing')",
            "valid": True
        }
    ]

    total_tests = len(test_cases)
    passed_tests = 0

    print(f"Running {total_tests} tests...\n")
    print("=" * 50)

    for test_case in test_cases:
        passed = run_test_case(
            test_case["formula"],
            test_case["valid"],
            test_case.get("expected_error")
        )
        if passed:
            passed_tests += 1
        print("-" * 50)

    # Print summary
    print("\nTest Summary:")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")

    return passed_tests == total_tests


run_all_tests()


# Run Result tests for each formula
# for i, formula in enumerate(formulas, 1):
#     print(f"\nTesting Formula {i}:")
#     print(f"{'='*50}")
#     print(f"Formula:\n{formula}\n")
#     result = test_formula(formula, df)
#     print("\nResult:")
#     print(result[["FirstName", "LastName", "result"]])
#     print(f"{'='*50}\n")
