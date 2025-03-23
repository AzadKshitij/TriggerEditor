from enum import Enum
from dataclasses import dataclass
from typing import List, Optional


class TokenType(Enum):
    FIELD = "FIELD"            # [Name]
    NUMBER = "NUMBER"          # 123, 45.67
    STRING = "STRING"          # 'text'
    OPERATOR = "OPERATOR"      # +, -, *, /, =, <, >, <=, >=, !=, AND, OR
    KEYWORD = "KEYWORD"        # IF, THEN, ELSE, BETWEEN, IN, CASE, WHEN, END, NULL
    IDENTIFIER = "IDENTIFIER"  # Function names
    LPAREN = "LPAREN"          # (
    RPAREN = "RPAREN"          # )
    COMMA = "COMMA"            # ,
    WHITESPACE = "WHITESPACE"  # Space, tab, newline
    DOT = "DOT"                # .
    SPECIAL = "SPECIAL"        # Special characters like @, #, $, etc.
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
        "+",
        "-",
        "*",
        "/",

        # Comparison
        "=",
        "<",
        ">",
        "<=",
        ">=",
        "!=",

        # Logical
        "AND",
        "OR"
    }

    # Valid special characters
    SPECIAL_CHARS = {
        '@',
        '#',
        '$',
        '%',
        '&',
        '.',
        ';',
        ':'
    }

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.current_char = self.text[0] if text else None

    def advance(self):
        """Advance the position tracker and update current_char."""
        self.pos += 1
        if self.pos >= len(self.text):
            self.current_char = None
        else:
            self.current_char = self.text[self.pos]
            if self.current_char == '\n':
                self.line += 1
                self.column = 1
            else:
                self.column += 1

    def peek(self) -> Optional[str]:
        """Look at the next character without consuming it."""
        peek_pos = self.pos + 1
        return self.text[peek_pos] if peek_pos < len(self.text) else None

    def skip_whitespace(self):
        """Skip whitespace characters."""
        while self.current_char and self.current_char.isspace():
            self.advance()

    def read_field(self) -> Token:
        """Read a field reference like [FieldName]"""
        start_col = self.column
        self.advance()  # Skip '['
        field_name = ""

        while self.current_char and self.current_char != ']':
            if self.current_char.isalnum() or self.current_char in self.SPECIAL_CHARS:
                field_name += self.current_char
                self.advance()
            else:
                raise SyntaxError(
                    f"Invalid character '{self.current_char}' in field name at line {self.line}, column {self.column}")

        if not self.current_char:
            # Use the improved error handling
            raise SyntaxError(
                f"Unclosed field reference at line {self.line}, column {start_col}")

        self.advance()  # Skip closing ']'
        return Token(TokenType.FIELD, field_name, self.line, start_col)

    def read_number(self) -> Token:
        """Read a number (integer or decimal)."""
        start_col = self.column
        num_str = ""
        dot_count = 0

        while self.current_char and (self.current_char.isdigit() or self.current_char == '.'):
            if self.current_char == '.':
                dot_count += 1
                if dot_count > 1:
                    raise SyntaxError(
                        f"Invalid number format at line {self.line}, column {self.column}")
            num_str += self.current_char
            self.advance()

        return Token(TokenType.NUMBER, num_str, self.line, start_col)

    def read_string(self) -> Token:
        """Read a string literal."""
        start_col = self.column
        quote = self.current_char
        self.advance()  # Skip opening quote
        value = ""

        while self.current_char and self.current_char != quote:
            if self.current_char == '\\':
                self.advance()
                if not self.current_char:
                    raise SyntaxError(
                        f"Unexpected end of string at line {self.line}, column {self.column}")
                value += self.current_char
            else:
                value += self.current_char
            self.advance()

        if not self.current_char:
            raise SyntaxError(
                f"Unclosed string at line {self.line}, column {start_col}")

        self.advance()  # Skip closing quote
        return Token(TokenType.STRING, value, self.line, start_col)

    def read_identifier(self) -> Token:
        """Read an identifier or keyword."""
        start_col = self.column
        identifier = ""

        while self.current_char and (self.current_char.isalnum() or self.current_char == '_'):
            identifier += self.current_char
            self.advance()

        upper_id = identifier.upper()
        if upper_id in self.KEYWORDS:
            return Token(TokenType.KEYWORD, upper_id, self.line, start_col)
        return Token(TokenType.IDENTIFIER, identifier, self.line, start_col)

    def read_operator(self) -> Token:
        """Read an operator."""
        start_col = self.column
        op = self.current_char
        self.advance()

        # Check for two-character operators
        if self.current_char in "=<>":
            op += self.current_char
            self.advance()

        return Token(TokenType.OPERATOR, op, self.line, start_col)

    def next_token(self) -> Token:
        """Get the next token from the input."""
        while self.current_char:
            if self.current_char.isspace():
                self.skip_whitespace()
                continue

            if self.current_char == '[':
                return self.read_field()

            if self.current_char.isdigit():
                return self.read_number()

            if self.current_char in '"\'':
                return self.read_string()

            if self.current_char.isalpha():
                return self.read_identifier()

            if self.current_char in "+-*/=<>!":
                return self.read_operator()

            # if self.current_char in self.SPECIAL_CHARS:
            #     return self.read_special()

            if self.current_char == '(':
                self.advance()
                return Token(TokenType.LPAREN, '(', self.line, self.column - 1)

            if self.current_char == ')':
                self.advance()
                return Token(TokenType.RPAREN, ')', self.line, self.column - 1)

            if self.current_char == ',':
                self.advance()
                return Token(TokenType.COMMA, ',', self.line, self.column - 1)

            raise SyntaxError(
                f"Invalid character '{self.current_char}' at line {self.line}, column {self.column}")

        return Token(TokenType.EOF, '', self.line, self.column)

    def tokenize(self) -> List[Token]:
        tokens = []
        while self.current_char:
            token = self.next_token()
            tokens.append(token)
            if token.type == TokenType.EOF:
                break
        return tokens

    def read_special(self) -> Token:
        """Read a special character."""
        start_col = self.column
        special = self.current_char
        self.advance()

        # Handle special character sequences (e.g., @@ or ##)
        while (self.current_char and self.current_char in self.SPECIAL_CHARS
               and self.current_char == special):
            special += self.current_char
            self.advance()

        return Token(TokenType.SPECIAL, special, self.line, start_col)

    def __iter__(self):
        """Make Tokenizer iterable"""
        return self

    def __next__(self) -> Token:
        """Get next token for iteration"""
        token = self.next_token()
        if token.type == TokenType.EOF:
            raise StopIteration
        return token

    def read_literal(self) -> Token:
        """Read a literal value including special characters"""
        start_col = self.column
        value = ""

        # Handle numbers with special suffixes (e.g., 99.9%)
        if self.current_char.isdigit():
            while self.current_char and (self.current_char.isdigit() or self.current_char == '.'):
                value += self.current_char
                self.advance()

            # Handle special suffix
            if self.current_char in self.SPECIAL_CHARS:
                value += self.current_char
                self.advance()

            return Token(TokenType.NUMBER, value, self.line, start_col)

        # Handle special character literals
        if self.current_char in self.SPECIAL_CHARS:
            while self.current_char and (self.current_char in self.SPECIAL_CHARS):
                value += self.current_char
                self.advance()
            return Token(TokenType.SPECIAL, value, self.line, start_col)

        return Token(TokenType.LITERAL, value, self.line, start_col)
