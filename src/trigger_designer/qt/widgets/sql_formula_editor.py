"""
SQL Formula Editor Widget with Syntax Highlighting and Error Detection

This module provides a custom QTextEdit widget with:
- SQL syntax highlighting
- Real-time error detection with red underlines
- Auto-completion for SQL keywords and column names
- Line numbering
- Bracket matching
"""

import re
from typing import List, Optional, Dict, Set
from qtpy.QtWidgets import (
    QTextEdit, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QFrame, QApplication, QMainWindow, QPushButton
)
from qtpy.QtCore import Qt, QTimer, QRect, Signal, QRegularExpression
from qtpy.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont, 
    QPainter, QTextCursor, QTextDocument, QFontMetrics,
    QPalette, QBrush, QPen, QTextFormat
)


class SQLSyntaxHighlighter(QSyntaxHighlighter):
    """SQL syntax highlighter for the formula editor."""
    
    def __init__(self, document: QTextDocument, column_names: Optional[List[str]] = None):
        super().__init__(document)
        self.column_names = column_names or []
        self.setup_highlighting_rules()
    
    def setup_highlighting_rules(self):
        """Set up the syntax highlighting rules."""
        self.highlighting_rules = []
        
        # SQL Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor(86, 156, 214))  # Blue
        keyword_format.setFontWeight(QFont.Weight.Bold)
        
        sql_keywords = [
            'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'IS', 'NULL',
            'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'AS', 'ASC', 'DESC', 'ORDER', 'BY',
            'GROUP', 'HAVING', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON',
            'UNION', 'ALL', 'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
            'CAST', 'CONVERT', 'SUBSTRING', 'UPPER', 'LOWER', 'TRIM', 'LENGTH',
            'COALESCE', 'ISNULL', 'NULLIF', 'BETWEEN', 'EXISTS', 'ANY', 'SOME'
        ]
        
        for keyword in sql_keywords:
            pattern = QRegularExpression(rf'\b{keyword}\b', QRegularExpression.PatternOption.CaseInsensitiveOption)
            self.highlighting_rules.append((pattern, keyword_format))
        
        # String literals (single quotes)
        string_format = QTextCharFormat()
        string_format.setForeground(QColor(206, 145, 120))  # Orange
        string_pattern = QRegularExpression(r"'([^'\\]|\\.)*'")
        self.highlighting_rules.append((string_pattern, string_format))
        
        # Numeric literals
        number_format = QTextCharFormat()
        number_format.setForeground(QColor(181, 206, 168))  # Light green
        number_pattern = QRegularExpression(r'\b\d+\.?\d*\b')
        self.highlighting_rules.append((number_pattern, number_format))
        
        # Column names in square brackets
        column_format = QTextCharFormat()
        column_format.setForeground(QColor(156, 220, 254))  # Light blue
        column_format.setFontWeight(QFont.Weight.Bold)
        column_pattern = QRegularExpression(r'\[[^\]]+\]')
        self.highlighting_rules.append((column_pattern, column_format))
        
        # Functions
        function_format = QTextCharFormat()
        function_format.setForeground(QColor(220, 220, 170))  # Yellow
        function_pattern = QRegularExpression(r'\b\w+(?=\()')
        self.highlighting_rules.append((function_pattern, function_format))
        
        # Operators
        operator_format = QTextCharFormat()
        operator_format.setForeground(QColor(212, 212, 212))  # Light gray
        operator_pattern = QRegularExpression(r'[+\-*/=<>!]+|<=|>=|<>|!=')
        self.highlighting_rules.append((operator_pattern, operator_format))
        
        # Comments (-- style)
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor(106, 153, 85))  # Green
        comment_format.setFontItalic(True)
        comment_pattern = QRegularExpression(r'--[^\r\n]*')
        self.highlighting_rules.append((comment_pattern, comment_pattern))
    
    def update_column_names(self, column_names: List[str]):
        """Update the list of available column names for highlighting."""
        self.column_names = column_names
        self.rehighlight()
    
    def highlightBlock(self, text: str):
        """Apply syntax highlighting to a block of text."""
        for pattern, format_obj in self.highlighting_rules:
            expression = pattern
            match_iterator = expression.globalMatch(text)
            
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format_obj)


class LineNumberArea(QWidget):
    """Widget to display line numbers for the SQL editor."""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.sql_editor = editor
    
    def sizeHint(self):
        return self.sql_editor.line_number_area_width()
    
    def paintEvent(self, event):
        self.sql_editor.line_number_area_paint_event(event)


class SQLFormulaEditor(QTextEdit):
    """
    Custom QTextEdit widget for SQL formula editing with syntax highlighting and error detection.
    
    Features:
    - SQL syntax highlighting
    - Line numbers
    - Error detection with red underlines
    - Bracket matching
    - Auto-indentation
    """
    
    # Signals
    errorDetected = Signal(str, int, int)  # error_message, line, column (single error - backwards compatibility)
    allErrorsDetected = Signal(list)       # List of all error messages
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Initialize components
        self.column_names: List[str] = []
        self.errors: List[Dict] = []
        self.error_timer = QTimer()
        self.error_timer.setSingleShot(True)
        self.error_timer.timeout.connect(self.check_for_errors)
        
        # Set up the editor
        self.setup_editor()
        self.setup_syntax_highlighter()
        self.connect_signals()
        # Note: Line numbers disabled for compatibility
        # self.setup_line_numbers()
    
    def setup_editor(self):
        """Configure the editor properties."""
        # Set font
        font = QFont("Consolas", 11)
        if not font.exactMatch():
            font = QFont("Courier New", 11)
        font.setFixedPitch(True)
        self.setFont(font)
        
        # Set tab width
        font_metrics = QFontMetrics(font)
        tab_width = font_metrics.horizontalAdvance(' ' * 4)
        self.setTabStopDistance(tab_width)
        
        # Configure editor behavior
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setAcceptRichText(False)
        
        # Set colors for dark theme
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                selection-background-color: #264f78;
                selection-color: #ffffff;
            }
        """)
    
    def setup_line_numbers(self):
        """Set up the line number area."""
        self.line_number_area = LineNumberArea(self)
        
        # Connect signals for line number updates (with safety checks)
        try:
            if hasattr(self, 'blockCountChanged'):
                self.blockCountChanged.connect(self.update_line_number_area_width)
            if hasattr(self, 'updateRequest'):
                self.updateRequest.connect(self.update_line_number_area)
            if hasattr(self, 'cursorPositionChanged'):
                self.cursorPositionChanged.connect(self.highlight_current_line)
        except AttributeError as e:
            print(f"Warning: Could not connect line number signals: {e}")
        
        self.update_line_number_area_width(0)
        self.highlight_current_line()
    
    def setup_syntax_highlighter(self):
        """Set up SQL syntax highlighting."""
        self.syntax_highlighter = SQLSyntaxHighlighter(self.document(), self.column_names)
    
    def connect_signals(self):
        """Connect internal signals."""
        super().textChanged.connect(self.on_text_changed)
    
    def set_column_names(self, column_names: List[str]):
        """Set the available column names for syntax highlighting and validation."""
        self.column_names = column_names
        if hasattr(self, 'syntax_highlighter'):
            self.syntax_highlighter.update_column_names(column_names)
    
    def on_text_changed(self):
        """Handle text changes and trigger error checking."""
        self.error_timer.stop()
        self.error_timer.start(500)  # Check for errors 500ms after typing stops
    
    def check_for_errors(self):
        """Check the current text for SQL syntax errors."""
        text = self.toPlainText()
        self.errors.clear()
        
        if not text.strip():
            self.update_error_highlights()
            # Emit clear signal for empty text
            self.allErrorsDetected.emit([])
            return
        
        # Basic SQL validation
        errors = self.validate_sql_syntax(text)
        self.errors.extend(errors)
        
        # Validate column references
        column_errors = self.validate_column_references(text)
        self.errors.extend(column_errors)
        
        # Update visual error indicators
        self.update_error_highlights()
        
        # Emit all errors
        if self.errors:
            # Emit backwards compatible single error signal
            first_error = self.errors[0]
            self.errorDetected.emit(
                first_error['message'],
                first_error['line'],
                first_error['column']
            )
            
            # Emit all errors signal with formatted messages
            error_messages = [
                f"Line {error['line']}, Col {error['column']}: {error['message']}"
                for error in self.errors
            ]
            self.allErrorsDetected.emit(error_messages)
        else:
            # Clear errors
            self.allErrorsDetected.emit([])
    
    def validate_sql_syntax(self, text: str) -> List[Dict]:
        """Basic SQL syntax validation."""
        errors = []
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            # Check for unmatched quotes
            single_quotes = line.count("'") - line.count("\\'")
            if single_quotes % 2 != 0:
                errors.append({
                    'message': 'Unmatched single quote',
                    'line': line_num,
                    'column': line.rfind("'"),
                    'length': 1
                })
            
            # Check for unmatched parentheses
            paren_count = line.count('(') - line.count(')')
            if paren_count != 0:
                if paren_count > 0:
                    # Find last unmatched opening parenthesis
                    pos = line.rfind('(')
                    if pos != -1:
                        errors.append({
                            'message': 'Unmatched opening parenthesis',
                            'line': line_num,
                            'column': pos,
                            'length': 1
                        })
                else:
                    # Find last unmatched closing parenthesis
                    pos = line.rfind(')')
                    if pos != -1:
                        errors.append({
                            'message': 'Unmatched closing parenthesis',
                            'line': line_num,
                            'column': pos,
                            'length': 1
                        })
        
        # Check for incomplete CASE statements
        case_pattern = re.compile(r'\bCASE\b.*?\bWHEN\b.*?\bTHEN\b.*?(?:\bELSE\b.*?)?(?!\bEND\b)', re.IGNORECASE | re.DOTALL)
        if case_pattern.search(text) and not re.search(r'\bEND\b', text, re.IGNORECASE):
            lines = text.split('\n')
            for line_num, line in enumerate(lines, 1):
                if re.search(r'\bCASE\b', line, re.IGNORECASE):
                    errors.append({
                        'message': 'CASE statement missing END keyword',
                        'line': line_num,
                        'column': 0,
                        'length': len(line)
                    })
                    break
        
        return errors
    
    def validate_column_references(self, text: str) -> List[Dict]:
        """Validate column references in square brackets."""
        errors = []
        if not self.column_names:
            return errors
        
        # Find all column references in square brackets
        column_pattern = re.compile(r'\[([^\]]+)\]')
        lines = text.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for match in column_pattern.finditer(line):
                column_ref = match.group(1)
                if column_ref not in self.column_names:
                    errors.append({
                        'message': f"Unknown column '{column_ref}'",
                        'line': line_num,
                        'column': match.start(),
                        'length': match.end() - match.start()
                    })
        
        return errors
    
    def update_error_highlights(self):
        """Update the visual error highlights in the editor."""
        # First, clear all existing error formatting
        cursor = QTextCursor(self.document())
        cursor.select(QTextCursor.SelectionType.Document)
        
        # Create a clean format to clear existing error formatting
        clean_format = QTextCharFormat()
        clean_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.NoUnderline)
        cursor.mergeCharFormat(clean_format)
        
        # If there are no errors, we're done (everything is cleared)
        if not self.errors:
            return
        
        # Create error format with red underline
        error_format = QTextCharFormat()
        error_format.setUnderlineColor(QColor(255, 0, 0))
        error_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
        
        # Apply error highlights
        for error in self.errors:
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            
            # Move to the error line
            for _ in range(error['line'] - 1):
                cursor.movePosition(QTextCursor.MoveOperation.Down)
            
            # Move to the error column
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, error['column'])
            
            # Select the error text
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, error.get('length', 1))
            
            # Apply error format
            cursor.mergeCharFormat(error_format)
    
    def line_number_area_width(self):
        """Calculate the width needed for the line number area."""
        if not hasattr(self, 'line_number_area') or not self.line_number_area:
            return 0
            
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space
    
    def update_line_number_area_width(self, _):
        """Update the width of the line number area."""
        if hasattr(self, 'line_number_area') and self.line_number_area:
            self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def update_line_number_area(self, rect, dy):
        """Update the line number area when scrolling."""
        if not hasattr(self, 'line_number_area') or not self.line_number_area:
            return
            
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)
    
    def resizeEvent(self, event):
        """Handle resize events to update line number area."""
        super().resizeEvent(event)
        
        # Only update line number area if it exists
        if hasattr(self, 'line_number_area') and self.line_number_area:
            cr = self.contentsRect()
            self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))
    
    def line_number_area_paint_event(self, event):
        """Paint the line number area."""
        if not hasattr(self, 'line_number_area') or not self.line_number_area:
            return
            
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(40, 40, 40))
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        height = self.fontMetrics().height()
        
        while block.isValid() and (top <= event.rect().bottom()):
            if block.isVisible() and (bottom >= event.rect().top()):
                number = str(block_number + 1)
                painter.setPen(QColor(128, 128, 128))
                painter.drawText(0, int(top), self.line_number_area.width(), height, Qt.AlignmentFlag.AlignRight, number)
            
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1
    
    def highlight_current_line(self):
        """Highlight the current line."""
        extra_selections = []
        
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            
            line_color = QColor(68, 68, 68).lighter(160)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        
        self.setExtraSelections(extra_selections)
    
    def keyPressEvent(self, event):
        """Handle key press events for auto-indentation and other features."""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Auto-indent on new line
            cursor = self.textCursor()
            current_line = cursor.block().text()
            indent = ''
            for char in current_line:
                if char in ' \t':
                    indent += char
                else:
                    break
            
            super().keyPressEvent(event)
            self.insertPlainText(indent)
        else:
            super().keyPressEvent(event)


class SQLFormulaWidget(QWidget):
    """
    Complete SQL formula editing widget with editor, error display, and toolbar.
    """
    
    textChanged = Signal()
    formulaChanged = Signal(str)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Error display bar - dynamic sizing
        self.error_frame = QFrame()
        self.error_frame.setStyleSheet("""
            QFrame {
                background-color: #3c1e1e;
                border: 1px solid #8b0000;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        self.error_frame.hide()
        
        error_layout = QVBoxLayout(self.error_frame)
        error_layout.setContentsMargins(8, 5, 8, 5)
        
        self.error_label = QLabel()
        self.error_label.setStyleSheet("""
            QLabel {
                color: #ff6b6b; 
                font-weight: bold;
                font-size: 12px;
            }
        """)
        self.error_label.setWordWrap(True)  # Allow text wrapping for long messages
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        error_layout.addWidget(self.error_label)
        
        layout.addWidget(self.error_frame)
        
        # SQL Editor
        self.editor = SQLFormulaEditor()
        self.editor.setPlaceholderText(
            "Enter SQL formula e.g.:\nCASE WHEN [Age] > 30 THEN 'Adult' ELSE 'Young' END"
        )
        layout.addWidget(self.editor)
    
    def connect_signals(self):
        """Connect widget signals."""
        self.editor.textChanged.connect(self.on_text_changed)
        self.editor.errorDetected.connect(self.on_error_detected)  # Keep for backwards compatibility
        self.editor.allErrorsDetected.connect(self.on_all_errors_detected)  # Use for better error display
    
    def on_text_changed(self):
        """Handle text changes."""
        self.textChanged.emit()
        self.formulaChanged.emit(self.get_text())
        
        # Hide error bar if text is empty
        if not self.editor.toPlainText().strip():
            self.error_frame.hide()
    
    def on_error_detected(self, message: str, line: int, column: int):
        """Handle error detection with dynamic sizing."""
        formatted_message = f"Line {line}, Col {column}: {message}"
        self.error_label.setText(formatted_message)
        
        # Adjust the error frame height based on content
        self.error_label.adjustSize()
        
        # Calculate required height for the text
        label_height = self.error_label.sizeHint().height()
        frame_padding = 10  # Top and bottom padding
        min_height = 25     # Minimum height for single line
        max_height = 100    # Maximum height to prevent excessive growth
        
        required_height = max(min_height, min(max_height, label_height + frame_padding))
        self.error_frame.setFixedHeight(required_height)
        
        self.error_frame.show()
    
    def on_all_errors_detected(self, error_messages: List[str]):
        """Handle multiple error detection with dynamic sizing."""
        self.show_errors(error_messages)
    
    def show_errors(self, errors: List[str]):
        """Display multiple error messages."""
        if not errors:
            self.error_frame.hide()
            return
        
        if len(errors) == 1:
            self.error_label.setText(errors[0])
        else:
            # Format multiple errors with bullet points
            error_text = "Multiple issues found:\n" + "\n".join(f"• {error}" for error in errors)
            self.error_label.setText(error_text)
        
        # Adjust the error frame height based on content
        self.error_label.adjustSize()
        
        # Calculate required height for the text
        label_height = self.error_label.sizeHint().height()
        frame_padding = 10  # Top and bottom padding
        min_height = 25     # Minimum height for single line
        max_height = 150    # Increased maximum height for multiple errors
        
        required_height = max(min_height, min(max_height, label_height + frame_padding))
        self.error_frame.setFixedHeight(required_height)
        
        self.error_frame.show()
    
    def set_text(self, text: str):
        """Set the editor text."""
        self.editor.setPlainText(text)
    
    def get_text(self) -> str:
        """Get the editor text."""
        return self.editor.toPlainText()
    
    def set_column_names(self, column_names: List[str]):
        """Set available column names for validation and highlighting."""
        self.editor.set_column_names(column_names)
    
    def clear_errors(self):
        """Clear all error indicators."""
        self.editor.errors.clear()
        self.editor.update_error_highlights()
        self.error_frame.hide()
    
    def setPlaceholderText(self, text: str):
        """Set placeholder text in the editor."""
        self.editor.setPlaceholderText(text)
    
    def set_placeholder_text(self, text: str):
        """Set placeholder text in the editor (alternative method name)."""
        self.setPlaceholderText(text)
    
    def set_available_columns(self, column_names: List[str]):
        """Set available column names (alternative method name for set_column_names)."""
        self.set_column_names(column_names)
