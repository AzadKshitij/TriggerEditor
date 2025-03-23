from dataclasses import dataclass
from typing import Dict, List, Optional
from .tokenizer import Token


@dataclass
class FormulaError:
    message: str
    line: int
    column: int
    length: int  # length of the problematic token/expression
    context: str  # the line of code where error occurred
    pointer: str  # string with ^ pointing to the error
    suggestion: Optional[str] = None  # hint to fix the error

    def __str__(self) -> str:
        # Format error message with context and pointer
        error_parts = [
            f"Error at line {self.line}, column {self.column}:",
            self.context,  # Show original context without trimming
            " " * (self.column - 1) + "^" *
            max(1, self.length),  # Ensure at least one ^
            self.message
        ]

        if self.suggestion:
            error_parts.append(f"Suggestion: {self.suggestion}")

        return "\n".join(error_parts)


class ErrorListener:
    # Common error messages and suggestions
    ERROR_MESSAGES: Dict[str, Dict[str, str]] = {
        'unclosed_field': {
            'code': 'E001',
            'message': "Unclosed field reference - Missing closing bracket ']'",
            'suggestion': "Add closing bracket ']' to complete the field reference"
        },
        'unclosed_string': {
            'code': 'E002',
            'message': "Unclosed string literal - Missing closing quote",
            'suggestion': "Add closing quote to complete the string"
        },
        'unclosed_paren': {
            'code': 'E003',
            'message': "Unclosed parenthesis - Missing closing ')'",
            'suggestion': "Add closing parenthesis ')' to complete the expression"
        },
        'invalid_char': {
            'code': 'E004',
            'message': "Invalid character in expression",
            'suggestion': "Remove or replace the invalid character"
        },
        'syntax_error': {
            'code': 'E005',
            'message': "Syntax error in expression",
            'suggestion': "Check the syntax near this location"
        }
    }

    def __init__(self, formula: str):
        self.formula = formula
        # Strip empty lines and normalize line endings
        self.lines = [line.rstrip('\r\n')
                      for line in formula.split('\n') if line.strip()]
        self.errors: List[FormulaError] = []

    def add_syntax_error(self, token: Token, error_type: str):
        """Add a common syntax error with predefined message and suggestion"""
        error_info = self.ERROR_MESSAGES.get(
            error_type, self.ERROR_MESSAGES['syntax_error'])

        self.add_error(
            token=token,
            message=error_info['message'],
            suggestion=error_info['suggestion'],
        )

    def add_error(self, token: Token, message: str,
                  suggestion: Optional[str] = None):
        """Add an error with detailed context information"""
        if token is None:
            context = self.lines[0] if self.lines else self.formula
            self.errors.append(FormulaError(
                message=message,
                line=1,
                column=1,
                length=1,
                context=context,
                pointer="^",
                suggestion=suggestion,
            ))
            return

        line_idx = token.line - 1
        if 0 <= line_idx < len(self.lines):
            context = self.lines[line_idx]

            # Keep original column position without adjusting for whitespace
            self.errors.append(FormulaError(
                message=message,
                line=token.line,
                column=token.column,
                length=len(token.value),
                context=context,
                pointer=" " * (token.column - 1) + "^" * len(token.value),
                suggestion=suggestion,
            ))

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def get_error_message(self) -> str:
        """Format all errors with proper indentation"""
        if not self.errors:
            return ""

        # Sort errors by line number and column
        sorted_errors = sorted(self.errors, key=lambda e: (e.line, e.column))
        return "\n\n".join(str(error) for error in sorted_errors)
