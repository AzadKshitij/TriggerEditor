from ast import Try
from sys import exception
from typing import Tuple, Optional
from .tokenizer import Tokenizer, TokenType
from .parser import Parser
from .ast import Node


class FormulaValidator:
    @staticmethod
    def validate(formula: str) -> Tuple[bool, Optional[Node], Optional[str]]:
        """
        Validate a formula and return (is_valid, ast, error_message)
        """
        try:
            # Tokenize
            tokenizer = Tokenizer(formula)
            tokens = []
            while True:
                token = tokenizer.next_token()
                tokens.append(token)
                if token.type == TokenType.EOF:
                    break

            # Parse
            try:
                parser = Parser(tokens)
                ast = parser.parse()
            except Exception as e:
                return False, None, f"{e}"

            # if parser.error_listener.has_errors():
            #     return False, None, parser.error_listener.get_error_message()

            return True, ast, None

        except Exception as e:
            return False, None, str(e)
