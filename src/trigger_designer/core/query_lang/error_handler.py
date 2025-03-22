from dataclasses import dataclass
from typing import List, Optional
from .tokenizer import Token


@dataclass
class FormulaError:
    message: str
    line: int
    column: int
    length: int  # length of the problematic token/expression
    context: str  # the line of code where error occurred
    pointer: str  # string with ^ pointing to the error

    def __str__(self) -> str:
        return (
            f"Error at line {self.line}, column {self.column}:\n"
            f"{self.context}\n"
            f"{self.pointer}\n"
            f"{self.message}"
        )


class ErrorListener:
    def __init__(self, formula: str):
        self.formula = formula
        self.lines = formula.split('\n')
        self.errors: List[FormulaError] = []

    def add_error(self, token: Token, message: str):
        """Add an error with detailed context information"""
        if token is None:
            # Handle errors without token context
            self.errors.append(FormulaError(
                message=message,
                line=1,
                column=1,
                length=1,
                context=self.lines[0] if self.lines else "",
                pointer="^"
            ))
            return

        # Get the line of code where error occurred
        line_idx = token.line - 1
        if 0 <= line_idx < len(self.lines):
            context = self.lines[line_idx]
        else:
            context = ""

        # Create pointer string
        pointer = " " * (token.column - 1) + "^" * len(token.value)

        self.errors.append(FormulaError(
            message=message,
            line=token.line,
            column=token.column,
            length=len(token.value),
            context=context,
            pointer=pointer
        ))

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def get_error_message(self) -> str:
        return "\n\n".join(str(error) for error in self.errors)
