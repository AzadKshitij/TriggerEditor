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
import time
from typing import Callable, List, Optional, Dict, Set, Tuple

from sqlglot import exp, parse_one
from sqlglot.errors import ParseError, TokenError
from loguru import logger
from qtpy.QtWidgets import (
    QCompleter,
    QTextEdit,
    QWidget,
    QVBoxLayout,
    QApplication,
    QMainWindow,
    QPushButton,
)
from qtpy.QtCore import Qt, QTimer, QRect, Signal, QRegularExpression, QStringListModel
from qtpy.QtGui import (
    QSyntaxHighlighter,
    QTextCharFormat,
    QColor,
    QFont,
    QPainter,
    QTextCursor,
    QTextDocument,
    QFontMetrics,
    QPalette,
    QBrush,
    QPen,
    QTextFormat,
)

from trigger_designer.core.shaping import sql_expression as _sql_expression
from trigger_designer.qt.theme_manager import get_theme_manager

#: Re-exported for callers that already import them from this module.
STRING_LITERAL_RE = _sql_expression.STRING_LITERAL_RE
translate_function_aliases = _sql_expression.translate_function_aliases

#: Fixed debounce between typing and validation.
ERROR_CHECK_DEBOUNCE_MS = 800


_FORMULA_TOKEN_RE = re.compile(
    r"--[^\n]*|/\*.*?\*/|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|\[[^\]\n]*\]",
    re.DOTALL,
)


def _formula_for_parser(text: str) -> tuple[str, list[int]]:
    """Adapt formula-only quoting for DuckDB SQLGlot; map offsets to the editor.

    The node executes the original formula after its own normalization. This
    adapter is only for diagnostics; it never changes the executed SQL.
    """
    sql = ["SELECT "]
    offsets = [-1] * len(sql[0])
    position = 0
    for match in _FORMULA_TOKEN_RE.finditer(text):
        sql.append(text[position : match.start()])
        offsets.extend(range(position, match.start()))
        token = match.group()
        start = match.start()
        if token.startswith(("[", '"')):
            # [...] is an identifier; "..." is a string in formula syntax.
            quote = '"' if token[0] == "[" else "'"
            sql.append(quote)
            offsets.append(start)
            inner = token[1:-1]
            index = 0
            while index < len(inner):
                char = inner[index]
                source = start + 1 + index
                if token[0] == '"' and char == '"' and inner[index : index + 2] == '""':
                    sql.append('"')
                    offsets.append(source)
                    index += 2
                    continue
                sql.append(char)
                offsets.append(source)
                if char == quote:
                    sql.append(char)  # Escape quote inside a delimited token.
                    offsets.append(source)
                index += 1
            sql.append(quote)
            offsets.append(match.end() - 1)
        else:
            sql.append(token)
            offsets.extend(range(start, match.end()))
        position = match.end()
    sql.append(text[position:])
    offsets.extend(range(position, len(text)))
    return "".join(sql), offsets


def mask_string_literals(text: str) -> str:
    """Replace string literals with spaces, preserving offsets and newlines."""
    return STRING_LITERAL_RE.sub(
        lambda match: "".join(" " if char != "\n" else "\n" for char in match.group()),
        text,
    )


#: Shared keyword list for highlighting + autocomplete (single source of truth).
SQL_KEYWORDS = [
    "SELECT",
    "FROM",
    "WHERE",
    "AND",
    "OR",
    "NOT",
    "IN",
    "LIKE",
    "IS",
    "NULL",
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
    "AS",
    "ASC",
    "DESC",
    "ORDER",
    "BY",
    "GROUP",
    "HAVING",
    "JOIN",
    "LEFT",
    "RIGHT",
    "INNER",
    "OUTER",
    "ON",
    "UNION",
    "ALL",
    "DISTINCT",
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "CAST",
    "CONVERT",
    "SUBSTRING",
    "UPPER",
    "LOWER",
    "TRIM",
    "LENGTH",
    "COALESCE",
    "ISNULL",
    "NULLIF",
    "BETWEEN",
    "EXISTS",
    "ANY",
    "SOME",
    "YEAR",
    "MONTH",
    "DAY",
]

#: DuckDB scalar functions surfaced in autocomplete (from FORMULA_TOOL_REFERENCE).
FUNCTION_NAMES = [
    "ABS",
    "CEIL",
    "COALESCE",
    "CONCAT",
    "CURRENT_DATE",
    "CURRENT_TIMESTAMP",
    "DATE_PART",
    "DATE_TRUNC",
    "DATEDIFF",
    "DAY",
    "EXTRACT",
    "FLOOR",
    "GREATEST",
    "IF",
    "IFF",
    "LEFT",
    "LENGTH",
    "LOWER",
    "LEAST",
    "MAX",
    "MIN",
    "MOD",
    "MONTH",
    "NULLIF",
    "POWER",
    "REGEXP_EXTRACT",
    "REGEXP_MATCHES",
    "REGEXP_REPLACE",
    "REPLACE",
    "RIGHT",
    "ROUND",
    "SPLIT_PART",
    "SQRT",
    "STRFTIME",
    "SUBSTRING",
    "SUM",
    "TODAY",
    "TRIM",
    "TRY_CAST",
    "UPPER",
    "YEAR",
    # Aliases translated to DuckDB spellings before execution (see
    # translate_function_aliases below): STRIP -> TRIM.
    "STRIP",
]

#: Minimum typed chars before the popup shows on its own (Ctrl+Space forces it).
AUTOCOMPLETE_MIN_PREFIX = 2

_WORD_PREFIX_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")


def extract_completion_prefix(block_text: str, pos_in_block: int) -> Tuple[str, bool]:
    """Return (prefix, in_brackets) for the cursor at pos_in_block.

    in_brackets is True when the cursor sits inside an unclosed '['.
    Pure helper so it can be unit-tested without Qt.
    """
    before = block_text[: max(0, min(pos_in_block, len(block_text)))]
    bracket_open = before.rfind("[")
    bracket_close = before.rfind("]")
    if bracket_open != -1 and bracket_open > bracket_close:
        return before[bracket_open + 1 :].lstrip(), True
    match = _WORD_PREFIX_RE.search(before)
    return (match.group() if match else "", False)


def match_completions(
    prefix: str, in_brackets: bool, column_names: List[str]
) -> List[str]:
    """Filter completion candidates for prefix (case-insensitive)."""
    if in_brackets and not prefix:
        return list(column_names)[:50]
    if not prefix:
        return []
    lowered = prefix.lower()
    if in_brackets:
        return [c for c in column_names if c.lower().startswith(lowered)][:50]
    out: List[str] = []
    seen = set()
    for name in FUNCTION_NAMES:
        if name.lower().startswith(lowered) and name.upper() not in seen:
            seen.add(name.upper())
            out.append(f"{name}()")
    for kw in SQL_KEYWORDS:
        if kw.lower().startswith(lowered) and kw.upper() not in seen:
            seen.add(kw.upper())
            out.append(kw)
    for col in column_names:
        label = f"[{col}]"
        if col.lower().startswith(lowered) and label not in seen:
            seen.add(label)
            out.append(label)
    return out[:50]


class SQLSyntaxHighlighter(QSyntaxHighlighter):
    """SQL syntax highlighter for the formula editor."""

    def __init__(
        self, document: QTextDocument, column_names: Optional[List[str]] = None
    ):
        super().__init__(document)
        self.column_names = column_names or []
        self.setup_highlighting_rules()

    def setup_highlighting_rules(self):
        """Set up the syntax highlighting rules from the active theme."""
        self.highlighting_rules = []

        def token(key: str, fallback: str) -> QColor:
            return get_theme_manager().color(key, fallback)

        # SQL Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(token("syntax_keyword", "#569cd6"))
        keyword_format.setFontWeight(QFont.Weight.Bold)

        sql_keywords = SQL_KEYWORDS

        for keyword in sql_keywords:
            pattern = QRegularExpression(
                rf"\b{keyword}\b",
                QRegularExpression.PatternOption.CaseInsensitiveOption,
            )
            self.highlighting_rules.append((pattern, keyword_format))

        # String literals (single quotes)
        string_format = QTextCharFormat()
        string_format.setForeground(token("syntax_string", "#ce9178"))
        string_pattern = QRegularExpression(r"'([^']|'')*'")
        # Double-quoted strings (same rule: only [...] are columns)
        double_string_pattern = QRegularExpression(r'"([^"]|"")*"')

        # Numeric literals
        number_format = QTextCharFormat()
        number_format.setForeground(token("syntax_number", "#b5cea8"))
        number_pattern = QRegularExpression(r"\b\d+\.?\d*\b")
        self.highlighting_rules.append((number_pattern, number_format))

        # Column names in square brackets (only [...] are columns)
        column_format = QTextCharFormat()
        column_format.setForeground(token("syntax_column", "#9cdcfe"))
        column_format.setFontWeight(QFont.Weight.Bold)
        column_pattern = QRegularExpression(r"\[[^\]]+\]")
        self.highlighting_rules.append((column_pattern, column_format))

        # Functions
        function_format = QTextCharFormat()
        function_format.setForeground(token("syntax_function", "#dcdca8"))
        function_pattern = QRegularExpression(r"\b\w+(?=\()")
        self.highlighting_rules.append((function_pattern, function_format))

        # Operators
        operator_format = QTextCharFormat()
        operator_format.setForeground(token("syntax_operator", "#d4d4d4"))
        operator_pattern = QRegularExpression(r"[+\-*/=<>!]+|<=|>=|<>|!=")
        self.highlighting_rules.append((operator_pattern, operator_format))

        # String literals paint last (over columns) so '[x]' inside a
        # string keeps string color; comments paint over everything.
        self.highlighting_rules.append((string_pattern, string_format))
        self.highlighting_rules.append((double_string_pattern, string_format))

        # Comments (-- style)
        comment_format = QTextCharFormat()
        comment_format.setForeground(token("syntax_comment", "#6a9955"))
        comment_format.setFontItalic(True)
        comment_pattern = QRegularExpression(r"--[^\r\n]*")
        self.highlighting_rules.append((comment_pattern, comment_format))

    def apply_theme(self) -> None:
        """Rebuild the rules after a theme change and repaint the document."""
        self.setup_highlighting_rules()
        self.rehighlight()

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
                self.setFormat(
                    match.capturedStart(), match.capturedLength(), format_obj
                )


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
    errorDetected = Signal(
        str, int, int
    )  # error_message, line, column (single error - backwards compatibility)
    allErrorsDetected = Signal(list)  # List of all error messages
    editingFinished = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Initialize components
        self.setObjectName("formulaEditor")
        self.column_names: List[str] = []
        self.errors: List[Dict] = []
        self.external_validator: Optional[Callable[[str], List[Dict]]] = None
        self._last_completion = ""
        self._last_completion_ts = 0.0
        self.error_timer = QTimer()
        self.error_timer.setSingleShot(True)
        self.error_timer.timeout.connect(self.check_for_errors)

        # Set up the editor
        self.setup_editor()
        self.setup_syntax_highlighter()
        self.setup_completer()
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
        tab_width = font_metrics.horizontalAdvance(" " * 4)
        self.setTabStopDistance(tab_width)

        # Configure editor behavior
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setAcceptRichText(False)
        # self.document().setDocumentMargin(2)

        # Colors come from base.qss (QTextEdit#formulaEditor)

    def setup_line_numbers(self):
        """Set up the line number area."""
        self.line_number_area = LineNumberArea(self)

        # Connect signals for line number updates (with safety checks)
        try:
            if hasattr(self, "blockCountChanged"):
                self.blockCountChanged.connect(self.update_line_number_area_width)
            if hasattr(self, "updateRequest"):
                self.updateRequest.connect(self.update_line_number_area)
            if hasattr(self, "cursorPositionChanged"):
                self.cursorPositionChanged.connect(self.highlight_current_line)
        except AttributeError as e:
            logger.warning(f"Could not connect line number signals: {e}")

        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def setup_syntax_highlighter(self):
        """Set up SQL syntax highlighting."""
        self.syntax_highlighter = SQLSyntaxHighlighter(
            self.document(), self.column_names
        )

    def apply_theme(self) -> None:
        """Re-read theme colours for syntax, gutter and error underlines."""
        highlighter = getattr(self, "syntax_highlighter", None)
        if highlighter is not None:
            highlighter.apply_theme()
        if hasattr(self, "errors"):
            self.update_error_highlights()
        self.highlight_current_line()
        area = getattr(self, "line_number_area", None)
        if area is not None:
            area.update()

    def setup_completer(self):
        """Set up VS Code-style autocomplete (functions, keywords, columns)."""
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setModel(QStringListModel([], self.completer))
        try:  # Qt6 substring filtering so "[col]" matches a bare prefix
            self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        except AttributeError:
            pass
        self.completer.activated[str].connect(self._insert_completion)
        # Colours come from `QListView#FormulaCompleterPopup` in base.qss.
        self.completer.popup().setObjectName("FormulaCompleterPopup")

    def _prefix_at_cursor(self) -> Tuple[str, bool]:
        cursor = self.textCursor()
        block_text = cursor.block().text()
        return extract_completion_prefix(block_text, cursor.positionInBlock())

    def _maybe_autocomplete(self, forced: bool = False) -> None:
        prefix, in_brackets = self._prefix_at_cursor()
        # Bare "[" is an explicit column request: show all columns at once.
        if not forced and len(prefix) < AUTOCOMPLETE_MIN_PREFIX and not in_brackets:
            self.completer.popup().hide()
            return
        matches = match_completions(prefix, in_brackets, self.column_names)
        if not matches:
            self.completer.popup().hide()
            return
        model = self.completer.model()
        if isinstance(model, QStringListModel):
            model.setStringList(matches)
        self.completer.setCompletionPrefix(prefix)
        popup = self.completer.popup()
        popup.setFont(self.font())
        try:
            first = self.completer.completionModel().index(0, 0)
            popup.setCurrentIndex(first)
        except (AttributeError, RuntimeError):
            pass
        # complete(rect) sizes the popup from the rect: a bare cursorRect()
        # is only a few px wide and renders as a thin sliver, so widen it
        # from the popup contents (Qt's own QTextEdit-completer example).
        rect = self.cursorRect()
        try:
            content_width = popup.sizeHintForColumn(0)
        except (AttributeError, RuntimeError):
            content_width = -1
        try:
            content_width += popup.verticalScrollBar().sizeHint().width()
        except (AttributeError, RuntimeError):
            pass
        rect.setWidth(max(content_width + 12, 200))
        self.completer.complete(rect)

    def _insert_completion(self, completion: str) -> None:
        """Replace the current prefix with the chosen completion."""
        prefix, in_brackets = self._prefix_at_cursor()
        # Guard: keyboard accept (keyPressEvent) + activated signal can fire
        # for one choice -> second call sees empty prefix at same spot.
        now = time.monotonic()
        if (
            completion == self._last_completion
            and not prefix
            and not in_brackets
            and (now - self._last_completion_ts) < 1.0
        ):
            return
        self._last_completion = completion
        self._last_completion_ts = now
        cursor = self.textCursor()
        # ponytail: O(n) cursor move, per-keystroke model rebuild if this lags
        for _ in range(len(prefix)):
            cursor.deletePreviousChar()
        if in_brackets:
            cursor.insertText(completion)
            if self.document().characterAt(cursor.position()) != "]":
                cursor.insertText("]")
        elif completion.endswith("()"):
            cursor.insertText(completion)
            cursor.movePosition(QTextCursor.MoveOperation.Left)
            self.setTextCursor(cursor)
        else:
            cursor.insertText(completion)

    def connect_signals(self):
        """Connect internal signals."""
        super().textChanged.connect(self.on_text_changed)

    def set_column_names(self, column_names: List[str]):
        """Set the available column names for syntax highlighting and validation."""
        self.column_names = column_names
        if hasattr(self, "syntax_highlighter"):
            self.syntax_highlighter.update_column_names(column_names)
        if self.toPlainText().strip():
            self.error_timer.start(ERROR_CHECK_DEBOUNCE_MS)

    def on_text_changed(self):
        """Handle text changes and trigger error checking."""
        # Do not leave a red underline from the previous expression on newly
        # typed text while the debounced validator is still pending.
        if self.errors:
            self.errors.clear()
            self.update_error_highlights()
            self.allErrorsDetected.emit([])
        self.error_timer.stop()
        self.error_timer.start(ERROR_CHECK_DEBOUNCE_MS)

    def check_for_errors(self):
        """Check the current text for SQL syntax errors."""
        text = self.toPlainText()
        self.errors.clear()

        if not text.strip():
            self.update_error_highlights()
            # Emit clear signal for empty text
            self.allErrorsDetected.emit([])
            return

        # SQLGlot supplies locations; DuckDB remains authoritative when the
        # editor has a live validator (the two parsers need not agree).
        syntax_errors = self.validate_sql_syntax(text)

        # DuckDB validates the actual generated query. SQLGlot provides source
        # positions only when DuckDB also rejects the expression as syntax.
        if self.external_validator is not None:
            try:
                external_errors = self.external_validator(text) or []
                if external_errors:
                    self.errors.extend(external_errors)
            except Exception as exc:  # noqa: BLE001 - host callbacks can fail
                self.errors.append(
                    {
                        "message": f"Validation unavailable: {type(exc).__name__}",
                        "category": "validation",
                    }
                )
        else:
            self.errors.extend(
                {**error, "category": "syntax"} for error in syntax_errors
            )

        # A malformed expression should point at its syntax first, not a
        # bracketed name inside an unfinished string. Still report genuine
        # column errors when the expression itself parsed successfully.
        if not any(error.get("category") == "syntax" for error in self.errors):
            self.errors.extend(self.validate_column_references(text))

        # Keep the primary host diagnostic first and avoid duplicate messages.
        seen = set()
        unique_errors = []
        for error in self.errors:
            if error["message"] not in seen:
                unique_errors.append(error)
                seen.add(error["message"])
        self.errors = unique_errors

        # Update visual error indicators
        self.update_error_highlights()

        # Emit all errors
        if self.errors:
            # Emit backwards compatible single error signal
            first_error = self.errors[0]
            if (
                first_error.get("line") is not None
                and first_error.get("column") is not None
            ):
                self.errorDetected.emit(
                    first_error["message"], first_error["line"], first_error["column"]
                )

            # Emit all errors signal with formatted messages
            error_messages = [
                (
                    f"Line {error['line']}, Col {error['column']}: "
                    if error.get("line") is not None and error.get("column") is not None
                    else ""
                )
                + error["message"]
                for error in self.errors
            ]
            self.allErrorsDetected.emit(error_messages)
        else:
            # Clear errors
            self.allErrorsDetected.emit([])

    @staticmethod
    def validate_sql_syntax(text: str) -> list[dict]:
        """Parse an expression in DuckDB dialect and return editor positions."""
        if not text.strip():
            return []
        sql, offsets = _formula_for_parser(text)
        try:
            parsed = parse_one(sql, read="duckdb")
        except TokenError as exc:
            # Incomplete quotes are routine while typing. TokenError's
            # start/end describe a context snippet, not the bad token, so
            # locate the first quote outside complete literals/comments.
            masked = list(text)
            for match in _FORMULA_TOKEN_RE.finditer(text):
                masked[match.start() : match.end()] = " " * len(match.group())
            quote_offset = next(
                (i for i, char in enumerate(masked) if char in ("'", '"')),
                None,
            )
            if quote_offset is None:
                index = max(7, min(exc.start or 7, len(offsets) - 1))
                quote_offset = max(0, offsets[index])
            line, column = SQLFormulaEditor._offset_to_line_col(text, quote_offset)
            return [
                {
                    "message": (
                        "Unterminated string literal"
                        if masked[quote_offset] in ("'", '"')
                        else "Invalid SQL token"
                    ),
                    "line": line,
                    "column": column,
                    "length": 1,
                }
            ]
        except ParseError as exc:
            errors = []
            for detail in exc.errors:
                description = detail.get("description") or "Invalid SQL expression"
                if description == "Expected END after CASE":
                    cases = list(
                        re.finditer(
                            r"\bCASE\b",
                            SQLFormulaEditor._mask_strings_and_comments(text),
                            re.IGNORECASE,
                        )
                    )
                    if cases:
                        case_line, case_col = SQLFormulaEditor._offset_to_line_col(
                            text, cases[-1].start()
                        )
                        errors.append(
                            {
                                "message": "CASE statement missing END keyword",
                                "line": case_line,
                                "column": case_col,
                                "length": 4,
                            }
                        )
                        continue
                line = max(1, detail.get("line") or 1)
                column = max(0, (detail.get("col") or 1) - 1)
                lines = sql.splitlines(keepends=True)
                processed_offset = sum(map(len, lines[: line - 1])) + column
                highlight = detail.get("highlight") or ""
                processed_offset -= max(0, len(highlight) - 1)
                processed_offset = max(0, min(processed_offset, len(offsets) - 1))
                original_offset = max(0, offsets[processed_offset])
                original_line, original_col = SQLFormulaEditor._offset_to_line_col(
                    text, original_offset
                )
                errors.append(
                    {
                        "message": description,
                        "line": original_line,
                        "column": original_col,
                        "length": max(
                            1, min(len(highlight), len(text) - original_offset)
                        ),
                    }
                )
            return errors
        # The SELECT wrapper lets SQL parsers treat a trailing [column] as
        # an implicit *alias* of the preceding expression. A Formula section
        # already supplies its target alias, so this is a missing operator,
        # not valid formula SQL (DuckDB otherwise blames our generated AS).
        if isinstance(parsed, exp.Select) and len(parsed.expressions) == 1:
            projection = parsed.expressions[0]
            if isinstance(projection, exp.Alias):
                for match in reversed(list(_FORMULA_TOKEN_RE.finditer(text))):
                    token = match.group()
                    if (
                        token.startswith("[")
                        and token[1:-1].strip().casefold()
                        == projection.alias.casefold()
                        and not text[match.end() :].strip()
                    ):
                        line, column = SQLFormulaEditor._offset_to_line_col(
                            text, match.start()
                        )
                        return [
                            {
                                "message": "Missing operator before column reference",
                                "line": line,
                                "column": column,
                                "length": len(token),
                            }
                        ]
                # Other explicit or implicit aliases also conflict with the
                # target column that the Formula node adds to its SELECT.
                code = SQLFormulaEditor._mask_strings_and_comments(text)
                alias = re.search(
                    rf"\b{re.escape(projection.alias)}\b(?=\s*$)",
                    code,
                    re.IGNORECASE,
                )
                if alias:
                    line, column = SQLFormulaEditor._offset_to_line_col(
                        text, alias.start()
                    )
                    return [
                        {
                            "message": "A formula must be one expression; choose its target column above",
                            "line": line,
                            "column": column,
                            "length": len(alias.group()),
                        }
                    ]
        return []

    @staticmethod
    def _mask_strings_and_comments(text: str) -> str:
        """Replace string literals/-- comments with spaces (keeps offsets)."""
        masked = mask_string_literals(text)
        return re.sub(
            r"--[^\r\n]*",
            lambda match: " " * (match.end() - match.start()),
            masked,
        )

    @staticmethod
    def _offset_to_line_col(text: str, offset: int) -> tuple:
        """Convert a character offset into a 1-based (line, column) pair."""
        offset = max(0, min(offset, len(text)))
        line_num = text.count("\n", 0, offset) + 1
        column = offset - (text.rfind("\n", 0, offset) + 1)
        return line_num, column

    def validate_column_references(self, text: str) -> List[Dict]:
        """Validate column references in square brackets."""
        errors = []
        if not self.column_names:
            return errors

        known = {name.strip().lower(): name for name in self.column_names}
        # Find all column references in square brackets (outside strings)
        column_pattern = re.compile(r"\[([^\]]+)\]")
        lines = text.split("\n")
        masked_lines = mask_string_literals(text).split("\n")

        for line_num, (line, masked_line) in enumerate(zip(lines, masked_lines), 1):
            for match in column_pattern.finditer(masked_line):
                start, end = match.start(), match.end()
                column_ref = line[start + 1 : end - 1].strip()
                if column_ref.lower() not in known:
                    errors.append(
                        {
                            "message": f"Unknown column '{column_ref}'",
                            "line": line_num,
                            "column": start,
                            "length": end - start,
                        }
                    )

        return errors

    def update_error_highlights(self):
        """Paint source spans without changing the document or undo history."""

        """Paint the error spans on the editor's extra selections.
        The underline is drawn with ``setExtraSelections`` and never by
        writing character formats into the document. A format write makes Qt
        emit ``textChanged``, and this editor's ``textChanged`` handler
        clears ``self.errors`` - so the diagnostics were wiped between
        being computed and being shown, and the error label stayed empty.
        A format write also pushes the document onto the undo stack for a
        change the user never made.

        The selections are always applied, so the underline of a fixed error
        does not linger.
        """
        selections = []
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

        # Create error format with a themed wave underline
        error_format = QTextCharFormat()
        error_format.setUnderlineColor(get_theme_manager().color("danger", "#e0686c"))
        error_format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
        error_color = get_theme_manager().color("danger", "#e0686c")

        # Apply error highlights
        lines = self.toPlainText().split("\n")
        for error in self.errors:
            line = error.get("line")
            column = error.get("column")
            if line is None or column is None or not 1 <= line <= len(lines):
                continue
            line_text = lines[line - 1]
            if not 0 <= column < len(line_text):
                continue
            length = max(0, min(error.get("length", 1), len(line_text) - column))
            if not length:
                continue
            start = sum(len(item) + 1 for item in lines[: line - 1]) + column
            selection = QTextEdit.ExtraSelection()
            selection.format.setUnderlineColor(error_color)
            selection.format.setUnderlineStyle(
                QTextCharFormat.UnderlineStyle.WaveUnderline
            )
            selection.cursor = QTextCursor(self.document())
            selection.cursor.setPosition(start)
            selection.cursor.setPosition(
                start + length, QTextCursor.MoveMode.KeepAnchor
            )
            selections.append(selection)
        self.setExtraSelections(selections)

    def line_number_area_width(self):
        """Calculate the width needed for the line number area."""
        if not hasattr(self, "line_number_area") or not self.line_number_area:
            return 0

        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1

        space = 3 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def update_line_number_area_width(self, _):
        """Update the width of the line number area."""
        if hasattr(self, "line_number_area") and self.line_number_area:
            self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        """Update the line number area when scrolling."""
        if not hasattr(self, "line_number_area") or not self.line_number_area:
            return

        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(
                0, rect.y(), self.line_number_area.width(), rect.height()
            )

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        """Handle resize events to update line number area."""
        super().resizeEvent(event)

        # Only update line number area if it exists
        if hasattr(self, "line_number_area") and self.line_number_area:
            cr = self.contentsRect()
            self.line_number_area.setGeometry(
                QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
            )

    def line_number_area_paint_event(self, event):
        """Paint the line number area."""
        if not hasattr(self, "line_number_area") or not self.line_number_area:
            return

        painter = QPainter(self.line_number_area)
        manager = get_theme_manager()
        painter.fillRect(
            event.rect(), manager.color("editor_line_number_background", "#171b1f")
        )
        number_pen = QPen(manager.color("editor_line_number_text", "#6e7781"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        height = self.fontMetrics().height()

        while block.isValid() and (top <= event.rect().bottom()):
            if block.isVisible() and (bottom >= event.rect().top()):
                number = str(block_number + 1)
                painter.setPen(number_pen)
                painter.drawText(
                    0,
                    int(top),
                    self.line_number_area.width(),
                    height,
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def highlight_current_line(self):
        """Highlight the current line."""
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()

            line_color = get_theme_manager().color("editor_current_line", "#232a31")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def keyPressEvent(self, event):
        """Handle autocomplete popup, Ctrl+Space, and auto-indentation."""
        completer = getattr(self, "completer", None)
        popup_visible = bool(completer is not None and completer.popup().isVisible())
        if popup_visible and event.key() in (
            Qt.Key.Key_Enter,
            Qt.Key.Key_Return,
            Qt.Key.Key_Tab,
        ):
            # Read the popup's highlighted row directly: currentCompletion()
            # goes stale (it keeps returning the first match after the view
            # selection moves), so Enter would insert the wrong suggestion.
            index = completer.popup().currentIndex()
            if index.isValid():
                highlighted = index.data(Qt.ItemDataRole.DisplayRole)
                completion = highlighted or completer.currentCompletion()
            else:
                completion = completer.currentCompletion()
            completer.popup().hide()
            completer.blockSignals(True)
            try:
                self._insert_completion(completion)
            finally:
                completer.blockSignals(False)
            event.accept()
            return
        if popup_visible and event.key() == Qt.Key.Key_Escape:
            completer.popup().hide()
            event.ignore()
            return
        if (
            event.key() == Qt.Key.Key_Space
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self._maybe_autocomplete(forced=True)
            return

        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Auto-indent on new line
            cursor = self.textCursor()
            current_line = cursor.block().text()
            indent = ""
            for char in current_line:
                if char in " \t":
                    indent += char
                else:
                    break

            super().keyPressEvent(event)
            self.insertPlainText(indent)
            if completer is not None:
                completer.popup().hide()
        else:
            super().keyPressEvent(event)
            if completer is not None and (
                completer.popup().isVisible()
                or event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete)
                or (
                    event.text()
                    and (event.text().isalnum() or event.text() in ("_", "[", "]"))
                )
            ):
                self._maybe_autocomplete()

    def focusOutEvent(self, event):
        """Emit a commit signal when the editor loses focus."""
        # Picking from the popup must not commit half-typed section text.
        try:
            if event.reason() == Qt.FocusReason.PopupFocusReason:
                event.ignore()
                return
        except AttributeError:
            pass
        completer = getattr(self, "completer", None)
        if completer is not None and completer.popup().isVisible():
            event.ignore()
            return
        super().focusOutEvent(event)
        self.editingFinished.emit()


class SQLFormulaWidget(QWidget):
    """
    Complete SQL formula editing widget with editor, error display, and toolbar.
    """

    # Owns its own textChanged / editingFinished signals, so the undo layer
    # must not also bind the nested editor - that would record one edit twice.
    _undo_composite = True

    textChanged = Signal()
    editingFinished = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Set up the user interface (editor only; errors surface inline)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # SQL Editor
        self.editor = SQLFormulaEditor()
        self.editor.setPlaceholderText(
            "Enter SQL formula e.g.:\nCASE WHEN [Age] > 30 THEN 'Adult' ELSE 'Young' END"
        )
        layout.addWidget(self.editor)

    def connect_signals(self):
        """Connect widget signals."""
        self.editor.textChanged.connect(self.on_text_changed)
        self.editor.editingFinished.connect(self.editingFinished.emit)

    def on_text_changed(self):
        """Handle text changes."""
        self.textChanged.emit()

    def set_text(self, text: str):
        """Set the editor text."""
        self.editor.setPlainText(text)

    def get_text(self) -> str:
        """Get the editor text."""
        return self.editor.toPlainText()

    def clear_errors(self):
        """Clear all error indicators."""
        self.editor.errors.clear()
        self.editor.update_error_highlights()

    def set_placeholder_text(self, text: str):
        """Set placeholder text in the editor."""
        self.editor.setPlaceholderText(text)

    def set_available_columns(self, column_names: List[str]):
        """Set available column names for validation and highlighting."""
        self.editor.set_column_names(column_names)

    def set_validate_callback(
        self, callback: Optional[Callable[[str], List[Dict]]]
    ) -> None:
        """Set a Callable[[text], errors] run after the heuristic checks."""
        self.editor.external_validator = callback
