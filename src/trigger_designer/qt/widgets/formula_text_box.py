from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor

from ....trigger_designer.core.query_lang.validator import FormulaValidator
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

        # Create error format with red wavy underline
        self.error_format = QTextCharFormat()
        self.error_format.setUnderlineStyle(
            QTextCharFormat.UnderlineStyle.WaveUnderline)
        self.error_format.setUnderlineColor(QColor('#FF0000'))

        self.is_highlighting = False
        # Track error regions
        self.error_regions = []

    def set_error(self, start: int, length: int):
        """Add an underlined region"""
        self.has_error = True
        self.error_regions.append((start, length))
        self.rehighlight()  # Refresh the highlighting

    def clear_errors(self):
        """Clear all underlined regions"""
        self.has_error = False
        self.error_regions.clear()
        self.rehighlight()

    def _create_format(self, color):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        return fmt

    def highlightBlock(self, text):
        # Prevent recursive calls
        if self.is_highlighting:
            return

        self.is_highlighting = True

        try:
            # Only tokenize if we're not in an error state
            if not hasattr(self, 'has_error') or not self.has_error:
                # First apply syntax highlighting
                from ....trigger_designer.core.query_lang.tokenizer import Tokenizer
                tokenizer = Tokenizer(text)
                tokens = tokenizer.tokenize()

                for token in tokens:
                    if token.type in self.formats:
                        self.setFormat(
                            token.column - 1,
                            len(token.value),
                            self.formats[token.type]
                        )

            # Then apply error highlighting
            for start, length in self.error_regions:
                self.setFormat(start, length, self.error_format)
        except Exception as e:
            # If tokenization fails, don't crash
            print(f"Highlighting error: {str(e)}")
        finally:
            self.is_highlighting = False


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

        # Connect text changed signal with a delay
        self.validation_timer = QTimer(self)
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self.validate_formula)
        self.textChanged.connect(self.handle_text_changed)

        # Add flag to track error state
        self.has_error = False

    def handle_text_changed(self):
        """Handle text changes and reset error state"""
        # self.highlighter.clear_errors()  # Clear existing errors
        # Reset error state when text changes
        self.has_error = False
        # Reset and start the timer
        self.validation_timer.stop()
        self.validation_timer.start(500)  # 500ms delay

    def validate_formula(self):
        """Validate the current formula and show errors"""
        formula = self.toPlainText()

        # Skip validation if empty
        if not formula.strip():
            self.highlighter.clear_errors()
            return

        try:
            is_valid, ast, error = FormulaValidator.validate(formula)
            print(f"Valid: {is_valid}, Error: {error}")

            if not is_valid and error:
                if hasattr(error, 'column') and hasattr(error, 'length'):
                    self.highlighter.set_error(error.column - 1, error.length)
                else:
                    self.highlighter.set_error(0, len(formula))
                    # Don't highlight if we can't determine the error position
                    # self.highlighter.clear_errors()
            else:
                self.highlighter.clear_errors()

        except Exception as e:
            print(f"Validation error: {str(e)}")
            self.highlighter.clear_errors()
