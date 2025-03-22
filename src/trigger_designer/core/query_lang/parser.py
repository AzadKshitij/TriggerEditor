from typing import List
from .tokenizer import Token, TokenType
from .ast import Node, Field, Literal, BinaryOp, IfThen, Function, NodeType


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

    def parse(self) -> Node:
        """Parse the entire expression"""
        return self.expression()

    def expression(self) -> Node:
        """Parse expression with precedence climbing"""
        return self.logical_or()

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
        """Parse primary expressions (literals, fields, functions, etc)"""
        token = self.peek()

        if self.match(TokenType.NUMBER):
            return Literal(NodeType.LITERAL, float(self.advance().value))

        if self.match(TokenType.STRING):
            return Literal(NodeType.LITERAL, self.advance().value)

        if self.match(TokenType.FIELD):
            return Field(NodeType.FIELD, self.advance().value)

        if self.match(TokenType.KEYWORD) and token.value.upper() == "IF":
            return self.if_statement()

        if self.match(TokenType.IDENTIFIER):
            return self.function_call()

        if self.match(TokenType.LPAREN):
            self.advance()  # consume (
            expr = self.expression()
            self.consume(TokenType.RPAREN, "Expected ')'")
            return expr

        raise ParserError(token, f"Unexpected token: {token.value}")

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
            while self.match(TokenType.OPERATOR) and self.peek().value == ",":
                self.advance()  # consume comma
                arguments.append(self.expression())

        self.consume(TokenType.RPAREN, "Expected ')' after arguments")
        return Function(NodeType.FUNCTION, name, arguments)

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

    def consume(self, type: TokenType, error: str, value: str = None) -> Token:
        """Consume token of expected type or raise error"""
        if self.match(type):
            if value is None or self.peek().value.upper() == value.upper():
                return self.advance()
        raise ParserError(self.peek(), error)
