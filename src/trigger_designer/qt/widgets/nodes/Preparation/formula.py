from functools import partial
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import duckdb
import polars as pl
from qtpy.QtCore import Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
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
from trigger_designer.qt.widgets.sql_formula_editor import SQLFormulaWidget

if TYPE_CHECKING:
    from nodeeditor.node_node import Node
    from nodeeditor.node_scene import Scene


MAX_FORMULA_SECTIONS = 5
EMPTY_TARGET_OPTION = "Select target column"
NEW_COLUMN_OPTION = "+ add column"
FORMULA_PLACEHOLDER = (
    "Enter formula e.g.:\nCASE WHEN [Age] > 30 THEN 'Adult' ELSE 'Young' END"
)


class FormulaContent(
    QDMNodeIconContentWidget, TriggerChangeHandler, SerializableContentMixin
):
    """Content widget for the formula node with support for multiple formulas."""

    evaluate = Signal()
    serialized_state_schema = {
        "formula_sections": {"default": [{"target_column": "", "formula_text": ""}]}
    }

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        self.history = self.node.scene.history
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        self.formula: str = ""
        self.formula_text: Optional[str] = None
        self.target_column: Optional[str] = None
        self.is_new_column: bool = False

        self.formula_sections: List[Dict[str, str]] = [self._default_section()]
        self.section_widgets: List[Dict[str, Any]] = []
        self.sections_layout: Optional[QVBoxLayout] = None
        self.add_section_button: Optional[QPushButton] = None
        self.section_count_label: Optional[QLabel] = None
        self._dock_layout: Optional[QVBoxLayout] = None

        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame | pl.LazyFrame] = None

        self.data: Optional[pl.DataFrame | pl.LazyFrame] = None
        self.variable_name = f"var_formula_{self.id}"
        self.last_error: str = ""

        self._sync_legacy_fields()

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
        self._dock_layout = dock_layout

        if self.incom_data is None:
            dock_layout.addWidget(EmptyStateLabel())
            return

        self.formula_sections = self._normalize_sections(self.formula_sections)

        main_layout = QVBoxLayout()
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
        dock_layout.addLayout(main_layout)

        self._rebuild_section_widgets()

    def _default_section(self) -> Dict[str, str]:
        return {"target_column": "", "formula_text": ""}

    def _normalize_sections(
        self, sections: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, str]]:
        normalized_sections: List[Dict[str, str]] = []

        for section in sections or []:
            normalized_sections.append(
                {
                    "target_column": str(section.get("target_column") or ""),
                    "formula_text": str(section.get("formula_text") or ""),
                }
            )

        if not normalized_sections:
            normalized_sections.append(self._default_section())

        return normalized_sections[:MAX_FORMULA_SECTIONS]

    def _sync_legacy_fields(self) -> None:
        first_section = (
            self.formula_sections[0]
            if self.formula_sections
            else self._default_section()
        )
        self.formula_text = first_section["formula_text"] or None
        self.target_column = first_section["target_column"] or None
        self.formula = first_section["formula_text"]

    def _sync_sections_from_widgets(self) -> None:
        for index, widgets in enumerate(self.section_widgets):
            try:
                self.formula_sections[index]["formula_text"] = (
                    widgets["formula_input"].get_text() or ""
                )
            except (AttributeError, RuntimeError, IndexError):
                continue

        self._sync_legacy_fields()

    def _current_state(self) -> Dict[str, List[Dict[str, str]]]:
        self._sync_sections_from_widgets()
        return {
            "formula_sections": [section.copy() for section in self.formula_sections]
        }

    def _configured_sections(self) -> List[Tuple[int, Dict[str, str]]]:
        self._sync_sections_from_widgets()
        return [
            (index, section.copy())
            for index, section in enumerate(self.formula_sections)
            if section["target_column"].strip() and section["formula_text"].strip()
        ]

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
        self.clearInputWidgets()
        if self._dock_layout is not None:
            self.recursively_find_widgets(self._dock_layout)

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
            target_row.addWidget(QLabel("Target:"))
            target_row.addWidget(target_selector)

            formula_label = QLabel("Formula:")
            formula_input = SQLFormulaWidget()
            formula_input.set_placeholder_text(FORMULA_PLACEHOLDER)
            formula_input.setMinimumHeight(120)
            formula_input.set_available_columns(
                self._available_columns_before_section(index)
            )
            if section["formula_text"]:
                formula_input.set_text(section["formula_text"])
            formula_input.set_validate_callback(
                partial(self.validate_section_text, index)
            )
            formula_input.editingFinished.connect(
                partial(self.commit_formula_text, index)
            )

            card_layout.addLayout(header_layout)
            card_layout.addLayout(target_row)
            card_layout.addWidget(formula_label)
            card_layout.addWidget(formula_input)

            self.sections_layout.addWidget(card)
            self.section_widgets.append(
                {
                    "card": card,
                    "title_label": title_label,
                    "remove_button": remove_button,
                    "target_selector": target_selector,
                    "formula_input": formula_input,
                }
            )

        self._refresh_section_controls()
        self._refresh_section_dependencies()
        self._refresh_input_tracking()

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

    def _refresh_section_dependencies(self) -> None:
        for index, widgets in enumerate(self.section_widgets):
            selector = widgets["target_selector"]
            current_target = self.formula_sections[index]["target_column"]

            selector.blockSignals(True)
            selector.clear()
            selector.addItems(self._target_items_for_section(index))
            self._set_target_selector_value(selector, current_target)
            selector.blockSignals(False)

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
        self._sync_legacy_fields()
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
        self._sync_legacy_fields()
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

    def _prompt_new_column(self,section_index: int, parent=None, ) -> None:
        """App-level dialog loop for adding a target column."""
        existing_target = self.formula_sections[section_index]["target_column"]
        known = self._known_target_names(exclude_section=section_index)
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
        self._sync_legacy_fields()
        self._refresh_section_dependencies()
        self.update_data()
        self.store_history(old_state)

    def commit_formula_text(self, section_index: int) -> None:
        """Commit a section's formula text after editing finishes."""
        if self.history.is_restoring_history:
            return

        old_state = self._current_state()

        try:
            current_formula = (
                self.section_widgets[section_index]["formula_input"].get_text() or ""
            )
        except (IndexError, KeyError, RuntimeError):
            return

        if self.formula_sections[section_index]["formula_text"] == current_formula:
            return

        self.formula_sections[section_index]["formula_text"] = current_formula
        self._sync_legacy_fields()
        self.update_data()
        self.store_history(old_state)

    def _quote_identifier(self, identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    def _apply_outside_string_literals(self, formula: str, transform: Any) -> str:
        parts: List[str] = []
        current_pos = 0
        string_literals = list(re.finditer(r"'[^']*'|\"[^\"]*\"", formula))

        for match in string_literals:
            before_string = formula[current_pos : match.start()]
            parts.append(transform(before_string))
            parts.append(match.group())
            current_pos = match.end()

        remaining = formula[current_pos:]
        parts.append(transform(remaining))
        return "".join(parts)

    def _normalize_function_bracket_calls(self, formula: str) -> str:
        """Support legacy shorthand like YEAR[column] by inserting call parens."""

        return self._apply_outside_string_literals(
            formula,
            lambda segment: re.sub(
                r"\b([A-Za-z_][A-Za-z0-9_]*)(\[[^\]]+\])",
                r"\1(\2)",
                segment,
            ),
        )

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

    def _prepare_formula_for_sql(
        self, formula_text: str, available_columns: List[str]
    ) -> str:
        sql_formula = self._normalize_function_bracket_calls(formula_text)
        for column_name in available_columns:
            sql_formula = self._replace_column_names(sql_formula, column_name)
        return sql_formula

    def _section_query(
        self,
        section: Dict[str, str],
        available_columns: List[str],
        relation_name: str,
    ) -> Tuple[str, List[str]]:
        """Build the SELECT query for one section (shared by run/codegen)."""
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
            query = (
                f"SELECT *, {sql_formula} AS {self._quote_identifier(target_column)} "
                f"FROM {relation_name}"
            )
            available_columns = available_columns + [target_column]
        return query, available_columns

    def _run_sections(
        self,
        current_df: pl.DataFrame,
        configured: List[Tuple[int, Dict[str, str]]],
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
                    errors[index] = str(exc)
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
                failed = min(errors)
                raise ValueError(f"Section {failed + 1}: {errors[failed]}")

            self.data = current_df.lazy() if was_lazy else current_df
        except Exception as exc:
            self.data = None
            self.last_error = str(exc)

    def store_history(self, old_state: Dict[str, List[Dict[str, str]]]) -> None:
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
            self._sync_legacy_fields()

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
        """Serialize the formula content, keeping legacy fields for compatibility."""
        self._sync_sections_from_widgets()
        payload = self.serialize_content_state(super().serialize())
        payload["formula"] = self.formula_sections[0]["formula_text"]
        payload["target_column"] = self.formula_sections[0]["target_column"]
        return payload

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
            self._sync_legacy_fields()
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
