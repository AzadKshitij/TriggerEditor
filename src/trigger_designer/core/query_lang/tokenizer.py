from enum import Enum
from dataclasses import dataclass
from typing import Optional


class TokenType(Enum):
    FIELD = "FIELD"           # [Name]
    NUMBER = "NUMBER"         # 123, 45.67
    STRING = "STRING"         # 'text'
    OPERATOR = "OPERATOR"     # +, -, *, /, =, <, >, <=, >=, !=, AND, OR
    KEYWORD = "KEYWORD"       # IF, THEN, ELSE, BETWEEN, IN, CASE, WHEN, END, NULL
    IDENTIFIER = "IDENTIFIER"  # Function names
    LPAREN = "LPAREN"        # (
    RPAREN = "RPAREN"        # )
    COMMA = "COMMA"          # ,
    EOF = "EOF"


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int


class Tokenizer:
    # Enhanced keyword set
    KEYWORDS = {
        "IF", "THEN", "ELSE",
        "BETWEEN", "AND", "OR", "IN",
        "CASE", "WHEN", "END",
        "NULL"
    }

    # Valid operators
    OPERATORS = {
        # Arithmetic
        "+": "+", "-": "-", "*": "*", "/": "/",

        # Comparison
        "=": "=", "<": "<", ">": ">",
        "<=": "<=", ">=": ">=", "!=": "!=",

        # Logical
        "AND": "AND", "OR": "OR"
    }

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1

    def advance(self):
        """Advance the position tracker."""
        if self.pos < len(self.text):
            if self.text[self.pos] == "\n":
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.pos += 1

    def next_token(self) -> Token:
        """Main function to retrieve the next token."""
        while self.pos < len(self.text):
            char = self.text[self.pos]

            # Skip whitespace
            if char.isspace():
                self.advance()
                continue

            # Field names [Name]
            if char == "[":
                return self.read_field()

            # Numbers
            if char.isdigit():
                return self.read_number()

            # Strings
            if char in "'\"":
                return self.read_string()

            # Operators
            if char in "+-*/=<>":
                return self.read_operator()

            # Keywords and identifiers
            if char.isalpha():
                return self.read_identifier()

            # Parentheses
            if char == "(":
                self.advance()
                return Token(TokenType.LPAREN, "(", self.line, self.column)
            if char == ")":
                self.advance()
                return Token(TokenType.RPAREN, ")", self.line, self.column)

            # Unknown character
            self.advance()

        return Token(TokenType.EOF, "", self.line, self.column)

    def read_field(self) -> Token:
        """Read a field like [Name]"""
        start_pos = self.pos
        self.advance()  # Skip '['
        field_name = ""

        while self.pos < len(self.text) and self.text[self.pos] != "]":
            field_name += self.text[self.pos]
            self.advance()

        if self.pos < len(self.text) and self.text[self.pos] == "]":
            self.advance()  # Skip closing ']'
            return Token(TokenType.FIELD, field_name, self.line, self.column)

        raise SyntaxError(
            f"Unclosed field name starting at line {self.line}, column {self.column}")

    def read_number(self) -> Token:
        """Read a number token (integer or float)."""
        start_pos = self.pos
        num_str = ""

        while self.pos < len(self.text) and (self.text[self.pos].isdigit() or self.text[self.pos] == "."):
            num_str += self.text[self.pos]
            self.advance()

        if num_str.count(".") > 1:
            raise SyntaxError(
                f"Invalid number at line {self.line}, column {self.column}")

        return Token(TokenType.NUMBER, num_str, self.line, self.column)

    def read_string(self) -> Token:
        """Read a string token."""
        start_pos = self.pos
        quote_type = self.text[self.pos]  # Either ' or "
        self.advance()  # Skip opening quote
        str_value = ""

        while self.pos < len(self.text) and self.text[self.pos] != quote_type:
            if self.text[self.pos] == "\\" and self.pos + 1 < len(self.text):
                # Handle escaped quotes
                str_value += self.text[self.pos + 1]
                self.pos += 2
            else:
                str_value += self.text[self.pos]
                self.advance()

        if self.pos < len(self.text) and self.text[self.pos] == quote_type:
            self.advance()  # Skip closing quote
            return Token(TokenType.STRING, str_value, self.line, self.column)

        raise SyntaxError(
            f"Unclosed string at line {self.line}, column {self.column}")

    def read_operator(self) -> Token:
        """Read an operator (+, -, *, /, ==, <=, >=, !=)."""
        start_pos = self.pos
        op = self.text[self.pos]
        self.advance()

        # Check for two-character operators (==, <=, >=, !=)
        if self.pos < len(self.text) and self.text[self.pos] in "=<>":
            op += self.text[self.pos]
            self.advance()

        return Token(TokenType.OPERATOR, op, self.line, self.column)

    def read_identifier(self) -> Token:
        """Read an identifier (keywords or function names)."""
        start_pos = self.pos
        identifier = ""

        while self.pos < len(self.text) and self.text[self.pos].isalnum():
            identifier += self.text[self.pos]
            self.advance()

        # Check if it's a keyword
        if identifier.upper() in self.KEYWORDS:
            return Token(TokenType.KEYWORD, identifier.upper(), self.line, self.column)

        return Token(TokenType.IDENTIFIER, identifier, self.line, self.column)
