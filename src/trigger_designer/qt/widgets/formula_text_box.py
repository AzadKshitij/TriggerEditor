from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
from ....trigger_designer.core.query_lang.parser import Parser
from ....trigger_designer.core.query_lang.tokenizer import Token, TokenType


class FormulaHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Define highlighting formats based on token types
        self.formats = {
            # Light blue for fields
            TokenType.FIELD: self._create_format('#9CDCFE'),
            # Light green for numbers
            TokenType.NUMBER: self._create_format('#B5CEA8'),
            # White for operators
            TokenType.OPERATOR: self._create_format('#D4D4D4'),
            # Yellow for functions
            TokenType.IDENTIFIER: self._create_format('#DCDCAA'),
            # Orange for strings
            TokenType.STRING: self._create_format('#CE9178'),
            # Purple for keywords
            TokenType.KEYWORD: self._create_format('#C586C0'),
            # White for parentheses
            TokenType.LPAREN: self._create_format('#D4D4D4'),
            # White for parentheses
            TokenType.RPAREN: self._create_format('#D4D4D4'),
            # White for commas
            TokenType.COMMA: self._create_format('#D4D4D4'),
        }

    def _create_format(self, color):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        return fmt

    def highlightBlock(self, text):
        from ....trigger_designer.core.query_lang.tokenizer import Tokenizer

        # Create tokenizer and get tokens
        tokenizer = Tokenizer(text)
        tokens = tokenizer.tokenize()

        # Track position in text
        pos = 0
        for token in tokens:
            if token.type in self.formats:
                # Find the token's value in the text starting from current position
                token_text = token.value
                start = text.find(token_text, pos)
                if start >= 0:
                    length = len(token_text)
                    self.setFormat(start, length, self.formats[token.type])
                    pos = start + length


class FormulaTextBox(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Set up the text box appearance
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
        """)

        # Create and attach the syntax highlighter
        self.highlighter = FormulaHighlighter(self.document())
