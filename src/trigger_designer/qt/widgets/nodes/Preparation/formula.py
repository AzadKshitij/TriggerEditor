from functools import partial
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import duckdb
import polars as pl
from qtpy.QtCore import Qt, QTimer, Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from trigger_designer.qt.widgets.common import EmptyStateLabel
from nodeeditor.utils_no_qt import dumpException
from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerGraphicsNode,
    TriggerNode,
)
from trigger_designer.qt.widgets.sql_formula_editor import (
    ERROR_CHECK_DEBOUNCE_MS,
    SQLFormulaWidget,
    STRING_LITERAL_RE,
)

if TYPE_CHECKING:
    from nodeeditor.node_node import Node
    from nodeeditor.node_scene import Scene


MAX_FORMULA_SECTIONS = 5
EMPTY_TARGET_OPTION = "Select target column"
NEW_COLUMN_OPTION = "+ add column"
FORMULA_PLACEHOLDER = (
    "Enter formula e.g.:\nCASE WHEN [Age] > 30 THEN 'Adult' ELSE 'Young' END"
)
MIN_EDITOR_HEIGHT = 60
MAX_EDITOR_HEIGHT = 600
DEFAULT_EDITOR_HEIGHT = 120
AUTO_DTYPE_OPTION = "Auto"
DTYPE_OPTIONS = [
    AUTO_DTYPE_OPTION,
    "String",
    "Integer",
    "Float",
    "Boolean",
    "Date",
    "Datetime",
    "Time",
    "Categorical",
]
DTYPE_TO_DUCKDB = {
    "String": "VARCHAR",
    "Integer": "BIGINT",
    "Float": "DOUBLE",
    "Boolean": "BOOLEAN",
    "Date": "DATE",
    "Datetime": "TIMESTAMP",
    "Time": "TIME",
    "Categorical": "VARCHAR",
}


class _ResizeGrip(QFrame):
    """Drag handle adjusting one section editor's fixed height."""

    def __init__(
        self, content: "FormulaContent", section_index: int, editor: QWidget
    ) -> None:
        super().__init__()
        self._content = content
        self._section_index = section_index
        self._editor = editor
        self.setObjectName("formulaResizeGrip")
        self.setFixedHeight(6)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setStyleSheet(
            "QFrame#formulaResizeGrip { background-color: #3c3c3c;"
            " border-radius: 3px; }"
        )
        self._press_y: Optional[int] = None
        self._press_height = DEFAULT_EDITOR_HEIGHT
        self._old_state: Optional[Dict[str, List[Dict[str, Any]]]] = None

    def mousePressEvent(self, event) -> None:
        self._press_y = event.globalPosition().toPoint().y()
        self._press_height = self._editor.height()
        self._old_state = self._content._current_state()

    def mouseMoveEvent(self, event) -> None:
        if self._press_y is None:
            return
        delta = event.globalPosition().toPoint().y() - self._press_y
        height = min(
            MAX_EDITOR_HEIGHT, max(MIN_EDITOR_HEIGHT, self._press_height + delta)
        )
        self._editor.setFixedHeight(height)

    def mouseReleaseEvent(self, event) -> None:
        if self._press_y is None:
            return
        self._press_y = None
        try:
            sections = self._content.formula_sections
            if 0 <= self._section_index < len(sections):
                sections[self._section_index]["editor_height"] = self._editor.height()
                if self._old_state is not None:
                    self._content.store_history(self._old_state)
        except RuntimeError:
            pass
        self._old_state = None


class FormulaContent(
    QDMNodeIconContentWidget, TriggerChangeHandler, SerializableContentMixin
):
    """Content widget for the formula node with support for multiple formulas."""

    evaluate = Signal()
    serialized_state_schema = {
        "formula_sections": {
            "default": [
                {
                    "target_column": "",
                    "formula_text": "",
                    "editor_height": 120,
                    "target_dtype": "",
                }
            ]
        }
    }

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        self.history = self.node.scene.history
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        self.formula_sections: List[Dict[str, Any]] = [self._default_section()]
        self.section_widgets: List[Dict[str, Any]] = []
        self.sections_layout: Optional[QVBoxLayout] = None
        self.add_section_button: Optional[QPushButton] = None
        self.section_count_label: Optional[QLabel] = None

        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame | pl.LazyFrame] = None

        self.data: Optional[pl.DataFrame | pl.LazyFrame] = None
        self.variable_name = f"var_formula_{self.id}"
        self.last_error: str = ""
        self.section_errors: Dict[int, str] = {}

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        """Initialize the user interface for the formula content widget."""
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        """Create the layout for the formula content widget."""
        if self.incom_data is None:
            dock_layout.addWidget(EmptyStateLabel())
            return

        self.formula_sections = self._normalize_sections(self.formula_sections)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        self.sections_layout = QVBoxLayout()
        self.sections_layout.setSpacing(10)

        controls_layout = QHBoxLayout()
        self.add_section_button = QPushButton("+ Add formula")
        self.add_section_button.clicked.connect(self.add_formula_section)
        self.section_count_label = QLabel("")
        self.section_count_label.setStyleSheet("color: gray;")

        controls_layout.addWidget(self.add_section_button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.section_count_label)

        main_layout.addLayout(self.sections_layout)
        main_layout.addLayout(controls_layout)
        main_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidget(container)
        dock_layout.addWidget(scroll_area, 1)

        self._rebuild_section_widgets()

    def _default_section(self) -> Dict[str, Any]:
        return {
            "target_column": "",
            "formula_text": "",
            "editor_height": 120,
            "target_dtype": "",
        }

    def _normalize_sections(
        self, sections: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        normalized_sections: List[Dict[str, Any]] = []

        for section in sections or []:
            try:
                editor_height = int(section.get("editor_height", 120))
            except (TypeError, ValueError):
                editor_height = 120
            target_dtype = str(section.get("target_dtype") or "")
            if target_dtype not in DTYPE_OPTIONS[1:]:
                target_dtype = ""
            normalized_sections.append(
                {
                    "target_column": str(section.get("target_column") or ""),
                    "formula_text": str(section.get("formula_text") or ""),
                    "editor_height": min(600, max(60, editor_height)),
                    "target_dtype": target_dtype,
                }
            )

        if not normalized_sections:
            normalized_sections.append(self._default_section())

        return normalized_sections[:MAX_FORMULA_SECTIONS]

    def _sync_sections_from_widgets(self) -> None:
        for index, widgets in enumerate(self.section_widgets):
            try:
                self.formula_sections[index]["formula_text"] = (
                    widgets["formula_input"].get_text() or ""
                )
            except (AttributeError, RuntimeError, IndexError):
                continue

    def _current_state(self) -> Dict[str, List[Dict[str, Any]]]:
        self._sync_sections_from_widgets()
        return {
            "formula_sections": [section.copy() for section in self.formula_sections]
        }

    def _configured_sections(self) -> List[Tuple[int, Dict[str, Any]]]:
        self._sync_sections_from_widgets()
        return [
            (index, section.copy())
            for index, section in enumerate(self.formula_sections)
            if section["target_column"].strip() and section["formula_text"].strip()
        ]

    @staticmethod
    def polars_dtype_to_label(dtype: Any) -> str:
        """Map a polars dtype to a dropdown label ("" when unmapped)."""
        match = re.match(r"[A-Za-z0-9]+", str(dtype))
        key = match.group() if match else ""
        mapping = {
            "String": "String",
            "Utf8": "String",
            "Int8": "Integer",
            "Int16": "Integer",
            "Int32": "Integer",
            "Int64": "Integer",
            "UInt8": "Integer",
            "UInt16": "Integer",
            "UInt32": "Integer",
            "UInt64": "Integer",
            "Float32": "Float",
            "Float64": "Float",
            "Boolean": "Boolean",
            "Date": "Date",
            "Datetime": "Datetime",
            "Time": "Time",
            "Categorical": "Categorical",
            "Enum": "Categorical",
        }
        return mapping.get(key, "")

    def _dtype_state_for_section(self, section_index: int) -> tuple:
        """Return (current label, enabled) for a section's dtype dropdown.

        Existing input columns show their actual type, disabled. New targets
        stay editable so a cast can be picked before the first run.
        """
        section = self.formula_sections[section_index]
        target = section["target_column"].strip()
        if self.incom_data is not None and target:
            try:
                schema = (
                    self.incom_data.collect_schema()
                    if isinstance(self.incom_data, pl.LazyFrame)
                    else self.incom_data.schema
                )
                for column_name, dtype in schema.items():
                    if column_name == target:
                        return self.polars_dtype_to_label(dtype), False
            except Exception:
                pass
        return section.get("target_dtype") or AUTO_DTYPE_OPTION, True

    def _set_section_dtype(self, section_index: int, target_dtype: str) -> None:
        old_state = {
            "formula_sections": [section.copy() for section in self.formula_sections]
        }
        normalized = target_dtype.strip()
        if normalized not in DTYPE_OPTIONS[1:]:
            normalized = ""

        if self.formula_sections[section_index].get("target_dtype", "") == normalized:
            return

        self.formula_sections[section_index]["target_dtype"] = normalized
        self.update_data()
        self.store_history(old_state)

    def _available_columns_before_section(self, section_index: int) -> List[str]:
        available_columns: List[str] = []
        if self.incom_data is not None:
            available_columns.extend(list(self.incom_data.columns))

        for section in self.formula_sections[:section_index]:
            target_column = section["target_column"].strip()
            if target_column and target_column not in available_columns:
                available_columns.append(target_column)

        return available_columns

    def _target_items_for_section(self, section_index: int) -> List[str]:
        available_columns = self._available_columns_before_section(section_index)
        current_target = self.formula_sections[section_index]["target_column"].strip()

        items = [EMPTY_TARGET_OPTION, NEW_COLUMN_OPTION]
        if current_target and current_target not in available_columns:
            items.append(current_target)
        items.extend(available_columns)
        return items

    def _set_target_selector_value(
        self, selector: QComboBox, target_column: str
    ) -> None:
        selected_text = target_column or EMPTY_TARGET_OPTION
        index = selector.findText(selected_text)
        selector.setCurrentIndex(index if index >= 0 else 0)

    def _clear_layout(self, layout: Optional[QVBoxLayout]) -> None:
        if layout is None:
            return

        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)
            del item

    def _refresh_input_tracking(self) -> None:
        # Formula manages its own commit/history explicitly (debounce timer,
        # focus-out, selector handlers). Auto-tracking is left disabled: it
        # would store a history entry (and serialize the scene) per keystroke
        # while never recomputing with the new text.
        self.clearInputWidgets()

    def _rebuild_section_widgets(self) -> None:
        if self.sections_layout is None:
            return

        self._clear_layout(self.sections_layout)
        self.section_widgets = []

        for index, section in enumerate(self.formula_sections):
            card = QFrame()
            card.setObjectName("formulaSectionCard")
            card.setStyleSheet(
                """
                QFrame#formulaSectionCard {
                    background-color: #252526;
                    border: 1px solid #3c3c3c;
                    border-radius: 6px;
                }
                """
            )

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)

            header_layout = QHBoxLayout()
            title_label = QLabel(f"Formula {index + 1}")
            remove_button = QPushButton("-")
            remove_button.setFixedWidth(28)
            remove_button.clicked.connect(partial(self.remove_formula_section, index))
            header_layout.addWidget(title_label)
            header_layout.addStretch()
            header_layout.addWidget(remove_button)

            target_row = QHBoxLayout()
            target_selector = QComboBox()
            target_selector.addItems(self._target_items_for_section(index))
            self._set_target_selector_value(target_selector, section["target_column"])
            target_selector.activated.connect(
                partial(self.handle_column_activation, index)
            )
            dtype_selector = QComboBox()
            dtype_selector.addItems(DTYPE_OPTIONS)
            dtype_label, dtype_enabled = self._dtype_state_for_section(index)
            dtype_selector.setCurrentText(dtype_label or AUTO_DTYPE_OPTION)
            dtype_selector.setEnabled(dtype_enabled)
            dtype_selector.setToolTip("Data type for the target column")
            dtype_selector.activated.connect(
                partial(self.handle_dtype_activation, index)
            )
            target_row.addWidget(target_selector, 1)
            target_row.addWidget(dtype_selector, 1)

            formula_input = SQLFormulaWidget()
            formula_input.set_placeholder_text(FORMULA_PLACEHOLDER)
            formula_input.setFixedHeight(section.get("editor_height", 120))
            formula_input.set_available_columns(
                self._available_columns_before_section(index)
            )
            if section["formula_text"]:
                formula_input.set_text(section["formula_text"])
            formula_input.set_validate_callback(
                partial(self.validate_section_text, index)
            )
            debounce_timer = QTimer(card)
            debounce_timer.setSingleShot(True)
            debounce_timer.setInterval(ERROR_CHECK_DEBOUNCE_MS)
            debounce_timer.timeout.connect(partial(self._debounced_commit, index))
            formula_input.textChanged.connect(debounce_timer.start)
            formula_input.editingFinished.connect(debounce_timer.stop)
            formula_input.editingFinished.connect(
                partial(self.commit_formula_text, index)
            )

            error_label = QLabel()
            error_label.setObjectName("formulaSectionError")
            error_label.setWordWrap(True)
            error_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
            error_label.hide()

            card_layout.addLayout(header_layout)
            card_layout.addLayout(target_row)
            card_layout.addWidget(formula_input)
            card_layout.addWidget(_ResizeGrip(self, index, formula_input))
            card_layout.addWidget(error_label)

            self.sections_layout.addWidget(card)
            self.section_widgets.append(
                {
                    "card": card,
                    "title_label": title_label,
                    "remove_button": remove_button,
                    "target_selector": target_selector,
                    "dtype_selector": dtype_selector,
                    "formula_input": formula_input,
                    "error_label": error_label,
                }
            )

        self._refresh_section_controls()
        self._refresh_section_dependencies()
        self._refresh_section_errors()
        self._refresh_input_tracking()

    def _refresh_section_errors(self) -> None:
        """Show per-section error messages on their cards."""
        for index, widgets in enumerate(self.section_widgets):
            label = widgets.get("error_label")
            if label is None:
                continue
            try:
                message = self.section_errors.get(index, "")
                label.setText(message)
                label.setVisible(bool(message))
            except RuntimeError:
                continue

    def _refresh_section_controls(self) -> None:
        section_count = len(self.formula_sections)

        if self.add_section_button is not None:
            self.add_section_button.setEnabled(section_count < MAX_FORMULA_SECTIONS)

        if self.section_count_label is not None:
            self.section_count_label.setText(
                f"{section_count}/{MAX_FORMULA_SECTIONS} sections"
            )

        for index, widgets in enumerate(self.section_widgets):
            widgets["title_label"].setText(f"Formula {index + 1}")
            widgets["remove_button"].setEnabled(section_count > 1)

    def refresh_dependencies_for_new_data(self) -> None:
        """Refresh selectors when the input schema changed (no widget rebuild).

        The config dock no longer rebuilds on every eval, so without this the
        target/dtype dropdowns would go stale when new columns arrive. Only
        combo items are touched: editors keep focus and scroll is preserved.
        """
        if self.incom_data is None or not self.section_widgets:
            return
        try:
            columns = list(self.incom_data.columns)
        except Exception:
            return
        if columns != getattr(self, "_dep_columns", None):
            self._dep_columns = columns
            try:
                self._refresh_section_dependencies()
            except RuntimeError:
                pass

    def _refresh_section_dependencies(self) -> None:
        for index, widgets in enumerate(self.section_widgets):
            selector = widgets["target_selector"]
            current_target = self.formula_sections[index]["target_column"]

            selector.blockSignals(True)
            selector.clear()
            selector.addItems(self._target_items_for_section(index))
            self._set_target_selector_value(selector, current_target)
            selector.blockSignals(False)

            dtype_selector = widgets.get("dtype_selector")
            if dtype_selector is not None:
                dtype_label, dtype_enabled = self._dtype_state_for_section(index)
                dtype_selector.blockSignals(True)
                dtype_selector.setCurrentText(dtype_label or AUTO_DTYPE_OPTION)
                dtype_selector.setEnabled(dtype_enabled)
                dtype_selector.blockSignals(False)

            try:
                widgets["formula_input"].set_available_columns(
                    self._available_columns_before_section(index)
                )
            except (AttributeError, RuntimeError):
                continue

    def add_formula_section(self) -> None:
        """Add a new formula section up to the configured limit."""
        if self.history.is_restoring_history:
            return

        if len(self.formula_sections) >= MAX_FORMULA_SECTIONS:
            return

        old_state = self._current_state()
        self.formula_sections.append(self._default_section())
        self._rebuild_section_widgets()
        self.update_data()
        self.store_history(old_state)

    def remove_formula_section(self, section_index: int) -> None:
        """Remove a formula section while preserving at least one section."""
        if self.history.is_restoring_history:
            return

        if len(self.formula_sections) <= 1:
            return

        old_state = self._current_state()
        self.formula_sections.pop(section_index)
        self._rebuild_section_widgets()
        self.update_data()
        self.store_history(old_state)

    def handle_column_activation(self, section_index: int, index: int) -> None:
        """Handle target-column selection for a formula section."""
        if self.history.is_restoring_history:
            return

        try:
            selector: QComboBox = self.section_widgets[section_index]["target_selector"]
            selected_text = selector.itemText(index)
        except (IndexError, KeyError, RuntimeError):
            return

        if selected_text == NEW_COLUMN_OPTION:
            self._prompt_new_column(section_index)
            return

        if selected_text == EMPTY_TARGET_OPTION:
            self._set_section_target(section_index, "")
            return

        self._set_section_target(section_index, selected_text)

    def _known_target_names(self, exclude_section: Optional[int] = None) -> set:
        """Lowercased input + section target names for duplicate detection."""
        known = set()
        if self.incom_data is not None:
            known.update(col.strip().lower() for col in self.incom_data.columns)
        for index, section in enumerate(self.formula_sections):
            if index == exclude_section:
                continue
            target = section["target_column"].strip()
            if target:
                known.add(target.lower())
        return known

    @staticmethod
    def _new_column_error(name: str, known: set) -> Optional[str]:
        """Validate a new column name. Returns an error message or None."""
        if not name:
            return "Column name cannot be empty."
        if name.lower() in known:
            return f"Column '{name}' already exists."
        return None

    def _prompt_new_column(
        self,
        section_index: int,
        parent=None,
    ) -> None:
        """App-level dialog loop for adding a target column."""
        existing_target = self.formula_sections[section_index]["target_column"]
        known = self._known_target_names(exclude_section=section_index)
        parent = parent
        text = existing_target
        while True:
            new_column, accepted = QInputDialog.getText(
                parent,
                "Add Column",
                "Column name:",
                text=text,
            )
            if not accepted:
                self._refresh_section_dependencies()
                return
            name = new_column.strip()
            error = self._new_column_error(name, known)
            if error is None:
                self._set_section_target(section_index, name)
                return
            text = name
            QMessageBox.warning(parent, "Add Column", error)

    def _set_section_target(self, section_index: int, target_column: str) -> None:
        old_state = self._current_state()
        normalized_target = target_column.strip()

        if self.formula_sections[section_index]["target_column"] == normalized_target:
            self._refresh_section_dependencies()
            return

        self.formula_sections[section_index]["target_column"] = normalized_target
        self._refresh_section_dependencies()
        self.update_data()
        self.store_history(old_state)

    def handle_dtype_activation(self, section_index: int, index: int) -> None:
        """Handle target dtype selection for a formula section."""
        if self.history.is_restoring_history:
            return

        try:
            selector: QComboBox = self.section_widgets[section_index]["dtype_selector"]
            selected_text = selector.itemText(index)
        except (IndexError, KeyError, RuntimeError):
            return

        self._set_section_dtype(section_index, selected_text)

    def _debounced_commit(self, section_index: int) -> None:
        """Apply a section's text after the debounce pause (history every pause)."""
        if self.history.is_restoring_history:
            return
        try:
            self.commit_formula_text(section_index)
        except RuntimeError:
            pass

    def commit_formula_text(self, section_index: int) -> None:
        """Commit a section's formula text after editing finishes."""
        if self.history.is_restoring_history:
            return

        try:
            current_formula = (
                self.section_widgets[section_index]["formula_input"].get_text() or ""
            )
        except (IndexError, KeyError, RuntimeError):
            return

        # Compare before any widget->state sync so real edits are detected.
        if self.formula_sections[section_index]["formula_text"] == current_formula:
            return

        old_state = {
            "formula_sections": [section.copy() for section in self.formula_sections]
        }
        self.formula_sections[section_index]["formula_text"] = current_formula
        self.update_data()
        self.store_history(old_state)

    def _quote_identifier(self, identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    def _apply_outside_string_literals(self, formula: str, transform: Any) -> str:
        parts: List[str] = []
        current_pos = 0
        string_literals = list(STRING_LITERAL_RE.finditer(formula))

        for match in string_literals:
            before_string = formula[current_pos : match.start()]
            parts.append(transform(before_string))
            parts.append(match.group())
            current_pos = match.end()

        remaining = formula[current_pos:]
        parts.append(transform(remaining))
        return "".join(parts)

    def _replace_column_names(self, formula: str, column_name: str) -> str:
        """Replace bracketed column names while preserving string literals.

        Matches case-insensitively with optional padding inside the brackets
        (mirroring editor validation) and rewrites to the canonical casing.
        """
        pattern = rf"\[\s*{re.escape(column_name)}\s*\]"
        replacement = self._quote_identifier(column_name)

        return self._apply_outside_string_literals(
            formula,
            lambda segment: re.sub(pattern, replacement, segment, flags=re.IGNORECASE),
        )

    @staticmethod
    def _normalize_double_quoted(match: re.Match) -> str:
        inner = match.group()[1:-1].replace('""', '"').replace("'", "''")
        return f"'{inner}'"

    def _normalize_string_literals(self, formula: str) -> str:
        """Rewrite "..." as '...' (only [...] are columns).

        Single-quoted strings and bracketed column refs pass through.
        """
        token_pattern = re.compile(r"'([^']|'')*'|\"([^\"]|\"\")*\"|\[[^\]]*\]")
        parts: List[str] = []
        current_pos = 0
        for match in token_pattern.finditer(formula):
            parts.append(formula[current_pos : match.start()])
            token = match.group()
            if token.startswith('"'):
                token = self._normalize_double_quoted(match)
            parts.append(token)
            current_pos = match.end()
        parts.append(formula[current_pos:])
        return "".join(parts)

    def _prepare_formula_for_sql(
        self, formula_text: str, available_columns: List[str]
    ) -> str:
        sql_formula = self._normalize_string_literals(formula_text)
        for column_name in available_columns:
            sql_formula = self._replace_column_names(sql_formula, column_name)
        return sql_formula

    @staticmethod
    def _shorten_error(message: str) -> str:
        """Reduce a DuckDB error to its first useful sentence."""
        text = (message or "").strip().replace("\r\n", "\n")
        match = re.search(r'Referenced column "[^"]+" not found', text)
        if match:
            return match.group()
        first_line = text.split("\n", 1)[0].strip()
        for prefix in ("Binder Error:", "Catalog Error:", "Parser Error:"):
            if first_line.startswith(prefix):
                first_line = first_line[len(prefix) :].strip()
        return first_line[:160]

    def _section_query(
        self,
        section: Dict[str, Any],
        available_columns: List[str],
        relation_name: str,
    ) -> Tuple[str, List[str]]:
        """Build the SELECT query for one section (shared by run/codegen).

        A picked dtype casts new target columns only; overwrites keep the
        expression result untouched. CAST failures surface as section errors.
        """
        target_column = section["target_column"]
        sql_formula = self._prepare_formula_for_sql(
            section["formula_text"], available_columns
        )
        if target_column in available_columns:
            query = (
                f"SELECT * EXCLUDE {self._quote_identifier(target_column)}, "
                f"{sql_formula} AS {self._quote_identifier(target_column)} "
                f"FROM {relation_name}"
            )
        else:
            db_type = DTYPE_TO_DUCKDB.get(section.get("target_dtype") or "")
            if db_type:
                sql_formula = f"CAST({sql_formula} AS {db_type})"
            query = (
                f"SELECT *, {sql_formula} AS {self._quote_identifier(target_column)} "
                f"FROM {relation_name}"
            )
            available_columns = available_columns + [target_column]
        return query, available_columns

    def _run_sections(
        self,
        current_df: pl.DataFrame,
        configured: List[Tuple[int, Dict[str, Any]]],
        explain_index: Optional[int] = None,
    ) -> Tuple[pl.DataFrame, List[str], Dict[int, str]]:
        """Apply configured (index, section) pairs in order.

        With explain_index set, that section is EXPLAINed instead of run
        (prior sections still run so later sections validate in context).
        Returns (frame, available columns, {index: error message}).
        """
        available_columns = list(current_df.columns)
        errors: Dict[int, str] = {}
        with duckdb.connect(":memory:") as duck:
            for index, section in configured:
                relation_name = f"df_step_{index}"
                query, available_columns = self._section_query(
                    section, available_columns, relation_name
                )
                duck.register(relation_name, current_df)
                try:
                    if index == explain_index:
                        duck.execute(f"EXPLAIN {query}").fetchall()
                    else:
                        current_df = duck.execute(query).pl()
                except Exception as exc:
                    errors[index] = self._shorten_error(str(exc))
                    break
        return current_df, available_columns, errors

    def validate_section_text(
        self, section_index: int, formula_text: str, sample_n: int = 200
    ) -> List[Dict[str, Any]]:
        """Dry-run one section's text via EXPLAIN on a sample. Editor errors out."""
        if self.incom_data is None:
            return []
        if not 0 <= section_index < len(self.formula_sections):
            return []
        sections = [section.copy() for section in self.formula_sections]
        sections[section_index] = {
            **sections[section_index],
            "formula_text": formula_text,
        }
        configured = [
            (index, section)
            for index, section in enumerate(sections)
            if section["target_column"].strip() and section["formula_text"].strip()
        ]
        if section_index not in [index for index, _ in configured]:
            return []
        try:
            sample = self.incom_data.head(sample_n)
            if isinstance(sample, pl.LazyFrame):
                sample = sample.collect()
        except Exception:
            return []
        try:
            _, _, errors = self._run_sections(
                sample, configured, explain_index=section_index
            )
        except Exception:
            return []
        if section_index in errors:
            return [
                {
                    "message": errors[section_index],
                    "line": 1,
                    "column": 0,
                    "length": 1,
                }
            ]
        return []

    def _collect_input_data(self) -> tuple[pl.DataFrame, bool]:
        if isinstance(self.incom_data, pl.LazyFrame):
            return self.incom_data.collect(), True

        if isinstance(self.incom_data, pl.DataFrame):
            return self.incom_data.clone(), False

        raise ValueError("Formula input must be a Polars DataFrame or LazyFrame")

    def update_data(self) -> None:
        """Apply all configured formulas to the incoming data."""
        self.last_error = ""
        self.section_errors = {}

        if self.incom_data is None:
            self.data = None
            return

        configured_sections = self._configured_sections()
        if not configured_sections:
            self.data = self.incom_data
            return

        try:
            current_df, was_lazy = self._collect_input_data()
            current_df, _, errors = self._run_sections(current_df, configured_sections)
            if errors:
                self.section_errors = errors
                failed = min(errors)
                raise ValueError(f"Section {failed + 1}: {errors[failed]}")

            self.data = current_df.lazy() if was_lazy else current_df
        except Exception as exc:
            self.data = None
            self.last_error = str(exc)
        finally:
            self._refresh_section_errors()

    def store_history(self, old_state: Dict[str, List[Dict[str, Any]]]) -> None:
        """Store undo/redo history for formula-section changes."""
        new_state = self._current_state()

        if old_state["formula_sections"] != new_state["formula_sections"]:
            history_data = {
                "node": self.node,
                "old_state": old_state,
                "new_state": new_state,
            }

            self.history.storeHistory(
                desc="Formula Changed", data=history_data, setModified=True
            )
            self.evaluate.emit()

    def history_stamp_callback(self, history_data: dict, is_undo: bool) -> None:
        """Restore formula sections during undo/redo."""
        try:
            self.history.is_restoring_history = True
            state = history_data["old_state"] if is_undo else history_data["new_state"]

            self.formula_sections = self._normalize_sections(state["formula_sections"])

            self._rebuild_section_widgets()
            self.update_data()
            self.evaluate.emit()
        finally:
            self.history.is_restoring_history = False

    def get_code(self) -> str:
        """Generate Python code for all configured formula sections."""
        configured_sections = self._configured_sections()

        if not self.incoming_variable:
            return ""

        if not configured_sections:
            return f"{self.variable_name} = {self.incoming_variable}\n"

        available_columns: List[str] = []
        if self.incom_data is not None:
            available_columns.extend(list(self.incom_data.columns))

        code_lines = [
            "import duckdb",
            "import polars as pl",
            "# Initialize DuckDB connection",
            "duck = duckdb.connect(':memory:')",
            "# Convert polars LazyFrame to DataFrame if needed for DuckDB",
            (
                f"df_for_duck = {self.incoming_variable}.collect() "
                f"if hasattr({self.incoming_variable}, 'collect') else {self.incoming_variable}"
            ),
        ]

        for section_index, section in configured_sections:
            relation_name = f"df_step_{section_index}"
            query, available_columns = self._section_query(
                section, available_columns, relation_name
            )

            code_lines.append(f"duck.register('{relation_name}', df_for_duck)")
            code_lines.append(f"df_for_duck = duck.execute('''{query}''').pl()")

        code_lines.extend(
            [
                "# Preserve lazy execution when the incoming value is lazy",
                (
                    f"{self.variable_name} = df_for_duck.lazy() "
                    f"if hasattr({self.incoming_variable}, 'collect') else df_for_duck"
                ),
                "duck.close()",
            ]
        )

        return "\n".join(code_lines) + "\n"

    def serialize(self) -> dict:
        """Serialize the formula content (legacy keys still load, not written)."""
        self._sync_sections_from_widgets()
        return self.serialize_content_state(super().serialize())

    def deserialize(self, data: dict, hashmap: dict = {}) -> bool:
        """Deserialize formula content from either new or legacy saved state."""
        res = super().deserialize(data, hashmap)

        try:
            sections = data.get("formula_sections")
            if sections is None:
                sections = [
                    {
                        "target_column": data.get("target_column", ""),
                        "formula_text": data.get("formula", ""),
                    }
                ]

            self.formula_sections = self._normalize_sections(sections)
            return True & res
        except Exception as exc:
            dumpException(exc)
        return res


@register_node(PreparationNodes.FORMULA, NodeTypes.PREPARATION)
class TriggerNode_Formula(TriggerNode):
    """A node for creating calculated columns using SQL-like expressions."""

    icon = "node_formula"
    node_code = PreparationNodes.FORMULA
    node_type = NodeTypes.PREPARATION
    node_title = "Formula"
    content_label_objname = "trigger_node_formula"
    style = {}

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[3])
        self.markInvalid(True)

    def initInnerClasses(self) -> None:
        self.content: FormulaContent = FormulaContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values: list) -> Optional[list]:
        """Process input data and apply all configured formulas."""
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if not input_value:
            print("👉🚫 Input is not connected", self.__class__.__name__)
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Input is not connected")
            return None

        self.content.incom_data = input_value.get("data")
        self.content.incoming_variable = input_value.get("variable_name")
        self.content.refresh_dependencies_for_new_data()
        self.content.update_data()

        if self.content.last_error:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip(self.content.last_error)
            return None

        self.markDirty(False)
        self.markInvalid(False)
        self.grNode.setToolTip("")

        self.param = [
            {
                "data": self.content.data,
                "variable_name": self.content.variable_name,
            }
        ]
        self.evalChildren()
        return self.param

    def get_code(self) -> str:
        """Get the generated code for this formula node."""
        return self.content.get_code()
