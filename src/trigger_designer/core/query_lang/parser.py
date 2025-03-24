from typing import List, Optional
from .tokenizer import Token, TokenType
from .ast import (
    Node, Field, Literal, BinaryOp, IfThen, Function,
    Between, In, Case, Null, NodeType
)
from .error_handler import ErrorListener
# from trigger_designer.core.query_lang.tokenizer import Token, TokenType
# from trigger_designer.core.query_lang.ast import (
#     Node, Field, Literal, BinaryOp, IfThen, Function,
#     Between, In, Case, Null, NodeType
# )
# from .error_handler import ErrorListener


class ParserError(Exception):
    def __init__(self, token: Token, message: str):
        self.token = token
        self.message = message
        super().__init__(
            f"Error at line {token.line}, column {token.column}: {message}")


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.current = 0

    def parse(self) -> Optional[Node]:
        """Parse the entire expression"""
        if not self.tokens:
            # self.error_listener.add_error(None, "No tokens to parse")
            return None

        try:
            node = self.expression()

            # Skip any remaining whitespace tokens
            while self.current < len(self.tokens) and self.peek().type == TokenType.WHITESPACE:
                self.advance()

            # Check for unexpected tokens
            if self.current < len(self.tokens) - 1:  # -1 for EOF token
                # self.error_listener.add_error(
                #     self.peek(),
                #     "Unexpected tokens after expression"
                # )
                return None
            return node
        except ParserError as e:
            # self.error_listener.add_error(e.token, e.message)
            return None

    def expression(self) -> Node:
        """Parse expression with precedence climbing"""
        return self.logical_or()

    # def string_or_expression(self) -> Node:
    #     """Parse a string literal or expression"""
    #     token = self.peek()

    #     # Handle string literals first
    #     if self.match(TokenType.STRING):
    #         value = token.value
    #         self.advance()
    #         return Literal(NodeType.LITERAL, value)

    #     # Handle numbers
    #     if self.match(TokenType.NUMBER):
    #         value = float(token.value)
    #         self.advance()
    #         return Literal(NodeType.LITERAL, value)

    #     # Handle other expressions
    #     return self.expression()

    def logical_or(self) -> Node:
        """Parse OR expressions"""
        left = self.logical_and()

        while self.match(TokenType.KEYWORD) and self.peek().value.upper() == "OR":
            self.advance()  # consume OR
            right = self.logical_and()
            left = BinaryOp(NodeType.BINARY_OP, left, "OR", right)

        return left

    def logical_and(self) -> Node:
        """Parse AND expressions"""
        left = self.equality()

        while self.match(TokenType.KEYWORD) and self.peek().value.upper() == "AND":
            # Check if this AND is part of a BETWEEN expression
            is_between_and = False
            if self.current > 0:
                prev_token = self.tokens[self.current - 1]
                if prev_token.type == TokenType.NUMBER:
                    # Look back further to check for BETWEEN keyword
                    for i in range(self.current - 2, -1, -1):
                        if self.tokens[i].type == TokenType.KEYWORD and self.tokens[i].value.upper() == "BETWEEN":
                            is_between_and = True
                            break
                        # Skip only numbers and operators while looking back
                        elif self.tokens[i].type not in {TokenType.NUMBER, TokenType.OPERATOR}:
                            break

            if is_between_and:
                break

            self.advance()  # consume AND
            right = self.equality()
            left = BinaryOp(NodeType.BINARY_OP, left, "AND", right)

        return left

    def equality(self) -> Node:
        """Parse equality expressions"""
        left = self.comparison()

        while self.match(TokenType.OPERATOR) and self.peek().value in ["=", "!="]:
            operator = self.advance().value
            right = self.comparison()
            left = BinaryOp(NodeType.BINARY_OP, left, operator, right)

        return left

    def comparison(self) -> Node:
        """Parse comparison expressions"""
        left = self.term()

        while self.match(TokenType.OPERATOR) and self.peek().value in [">", ">=", "<", "<="]:
            operator = self.advance().value
            right = self.term()
            left = BinaryOp(NodeType.BINARY_OP, left, operator, right)

        return left

    def term(self) -> Node:
        """Parse addition and subtraction"""
        left = self.factor()

        while self.match(TokenType.OPERATOR) and self.peek().value in ["+", "-"]:
            operator = self.advance().value
            right = self.factor()
            left = BinaryOp(NodeType.BINARY_OP, left, operator, right)

        return left

    def factor(self) -> Node:
        """Parse multiplication and division"""
        left = self.primary()

        while self.match(TokenType.OPERATOR) and self.peek().value in ["*", "/"]:
            operator = self.advance().value
            right = self.primary()
            left = BinaryOp(NodeType.BINARY_OP, left, operator, right)

        return left

    def primary(self) -> Node:
        """Parse primary expressions"""
        token = self.peek()

        # Special character handling
        if self.match(TokenType.SPECIAL):
            return Literal(NodeType.LITERAL, self.advance().value)

        if self.match(TokenType.NUMBER):
            return Literal(NodeType.LITERAL, float(self.advance().value))

        if self.match(TokenType.STRING):
            return Literal(NodeType.LITERAL, self.advance().value)

        if self.match(TokenType.FIELD):
            field = Field(name=self.advance().value)

            # Check for BETWEEN expression
            if self.match(TokenType.KEYWORD) and self.peek().value.upper() == "BETWEEN":
                return self.between_expression(field)

            # Check for IN expression
            if self.match(TokenType.KEYWORD) and self.peek().value.upper() == "IN":
                return self.in_expression(field)

            return field

        if self.match(TokenType.KEYWORD):
            keyword = token.value.upper()
            if keyword == "CASE":
                return self.case_statement()
            elif keyword == "NULL":
                self.advance()
                return Null()
            elif keyword == "IF":
                return self.if_statement()
            else:
                raise ParserError(token, f"Unexpected keyword: {keyword}")

        if self.match(TokenType.IDENTIFIER):
            return self.function_call()

        if self.match(TokenType.LPAREN):
            self.advance()  # consume (
            expr = self.expression()
            self.consume(TokenType.RPAREN, "Expected ')'")
            return expr

        raise ParserError(token, f"Unexpected token: {token.value}")

    def between_expression(self, field: Field) -> Between:
        """Parse BETWEEN expression: [Field] BETWEEN start AND end"""
        self.advance()  # consume BETWEEN
        start = self.expression()

        # Check for AND keyword
        if not (self.match(TokenType.KEYWORD) and self.peek().value.upper() == "AND"):
            raise ParserError(
                self.peek(), "Expected 'AND' in BETWEEN expression")

        self.advance()  # consume AND
        end = self.term()  # Use term() instead of expression() to limit the scope

        return Between(NodeType.BETWEEN, field, start, end)

    def in_expression(self, field: Field) -> In:
        """Parse IN expression: [Field] IN (value1, value2, ...)"""
        self.advance()  # consume IN

        # Handle opening parenthesis
        if not self.match(TokenType.LPAREN):
            raise ParserError(self.peek(), "Expected '(' after IN")
        self.advance()  # consume '('

        values = []

        # Handle empty list case
        if self.match(TokenType.RPAREN):
            self.advance()  # consume ')'
            return In(NodeType.IN, field, values)

        # Parse first value
        values.append(self.parse_in_value())

        # Parse remaining values
        while self.match(TokenType.COMMA):
            self.advance()  # consume comma
            values.append(self.parse_in_value())

        # Handle closing parenthesis
        if not self.match(TokenType.RPAREN):
            raise ParserError(self.peek(), "Expected ')' after IN list")
        self.advance()  # consume ')'

        return In(NodeType.IN, field, values)

    def parse_in_value(self) -> Node:
        """Parse a value in an IN list (string literal or expression)"""
        if self.match(TokenType.STRING):
            token = self.peek()
            self.advance()  # consume string token
            return Literal(NodeType.LITERAL, token.value)
        return self.expression()

    def if_statement(self) -> Node:
        """Parse IF/THEN/ELSE statements"""
        self.advance()  # consume IF
        condition = self.expression()

        self.consume(TokenType.KEYWORD, "Expected 'THEN'", value="THEN")
        then_expr = self.expression()

        else_expr = None
        if self.match(TokenType.KEYWORD) and self.peek().value.upper() == "ELSE":
            self.advance()  # consume ELSE
            else_expr = self.expression()

        return IfThen(NodeType.IF_THEN, condition, then_expr, else_expr)

    def function_call(self) -> Node:
        """Parse function calls"""
        name = self.advance().value
        self.consume(TokenType.LPAREN, "Expected '(' after function name")

        arguments = []
        if not self.match(TokenType.RPAREN):
            arguments.append(self.expression())
            while self.match(TokenType.COMMA):
                self.advance()  # consume comma
                arguments.append(self.expression())

        self.consume(TokenType.RPAREN, "Expected ')' after arguments")
        return Function(NodeType.FUNCTION, name, arguments)

    def case_statement(self) -> Case:
        """Parse CASE statement"""
        self.advance()  # consume CASE

        conditions = []
        results = []

        while self.match(TokenType.KEYWORD) and self.peek().value.upper() == "WHEN":
            self.advance()  # consume WHEN
            condition = self.expression()

            if not (self.match(TokenType.KEYWORD) and self.peek().value.upper() == "THEN"):
                raise ParserError(
                    self.peek(), "Expected 'THEN' after WHEN condition")

            self.advance()  # consume THEN
            result = self.expression()

            conditions.append(condition)
            results.append(result)

        else_result = None
        if self.match(TokenType.KEYWORD) and self.peek().value.upper() == "ELSE":
            self.advance()  # consume ELSE
            else_result = self.expression()

        self.consume(TokenType.KEYWORD,
                     "Expected 'END' to close CASE statement", "END")
        return Case(NodeType.CASE, conditions, results, else_result)

    def peek(self) -> Token:
        """Look at current token without consuming it"""
        return self.tokens[self.current]

    def advance(self) -> Token:
        """Consume current token and return it"""
        token = self.peek()
        self.current += 1
        return token

    def match(self, type: TokenType) -> bool:
        """Check if current token matches expected type"""
        if self.current >= len(self.tokens):
            return False
        return self.peek().type == type

    def consume(self, type: TokenType, error: str, value: str = None) -> Optional[Token]:
        """Consume token of expected type or raise error"""
        if self.match(type):
            if value is None or self.peek().value.upper() == value.upper():
                return self.advance()
        raise ParserError(self.peek(), error)
