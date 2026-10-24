"""Filter node: Qt wrapper only; the logic is core/shaping/filter.py."""

from __future__ import annotations

import duckdb
import polars as pl
from qtpy.QtWidgets import QLineEdit, QVBoxLayout

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import filter as core
from trigger_designer.core.shaping.sql_expression import (
    prepare_expression_sql,
    shorten_error,
)
from trigger_designer.qt.helpers.shaping_support import ShapingContent, ShapingNode
from trigger_designer.qt.node_base import frame_schema
from trigger_designer.qt.widgets.common import (
    ConfigSection,
    EmptyStateLabel,
    FormRow,
    NoWheelComboBox,
    SegmentedControl,
)
from trigger_designer.qt.widgets.sql_formula_editor import SQLFormulaWidget

EXPRESSION_PLACEHOLDER = (
    "Filter rows with SQL, e.g.:\n"
    "[order_value] in_between (0, 500) AND [status] = 'paid'"
)


class FilterContent(ShapingContent):
    """Simple one-column builder or a SQL WHERE expression."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.filter"
    OUTPUT_KINDS = ("true", "false")
    INPUTS = 1
    HISTORY = "Filter"
    SUMMARY = "row filter"

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        # Keep the generated variable names the old node used.
        self.output_variables = [
            f"var_t_filter_{self.id}",
            f"var_f_filter_{self.id}",
        ]
        self.variable_name = self.output_variables[0]
        self.out1_variable_name = self.output_variables[1]

    # -- settings helpers -------------------------------------------------
    def _mode(self) -> str:
        return str(self.settings.get("mode") or "builder")

    # -- dock construction ----------------------------------------------
    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if not self.ready():
            dock_layout.addWidget(EmptyStateLabel())
            return

        self.mode_selector = SegmentedControl(["Simple", "Expression"])
        self.mode_selector.setToolTip(
            "Simple builds one column condition; Expression filters rows "
            "with a SQL WHERE clause (no new columns)"
        )
        self.mode_selector.changed.connect(self._commit_mode)
        dock_layout.addWidget(self.mode_selector)

        condition = ConfigSection()
        condition._undo_composite = True
        self.condition_section = condition

        self.column_selector = NoWheelComboBox()
        self.column_selector.setObjectName("columnSelector")
        self.column_selector.setMinimumHeight(30)
        self.column_selector.currentIndexChanged.connect(
            lambda _index: self._commit_column(self.column_selector.currentData() or "")
        )
        condition.addWidget(FormRow("Column", self.column_selector, label_width=88))

        self.operation_selector = NoWheelComboBox()
        self.operation_selector.setObjectName("operationSelector")
        self.operation_selector.setMinimumHeight(30)
        self.operation_selector.currentIndexChanged.connect(
            lambda _index: self.set_setting(
                "operation",
                self.operation_selector.currentData() or "Equals",
                "Filter Operation Changed",
            )
        )
        condition.addWidget(
            FormRow("Operation", self.operation_selector, label_width=88)
        )

        self.value_input = QLineEdit()
        self.value_input.setObjectName("valueInput")
        self.value_input.setPlaceholderText("Enter filter value...")
        self.value_input.setMinimumHeight(30)
        self._debounced(
            self.value_input.textChanged,
            lambda: self.set_setting(
                "value", self.value_input.text(), "Filter Value Changed"
            ),
        )
        condition.addWidget(FormRow("Value", self.value_input, label_width=88))

        self.value2_input = QLineEdit()
        self.value2_input.setObjectName("value2Input")
        self.value2_input.setPlaceholderText("Enter max value...")
        self.value2_input.setMinimumHeight(30)
        self._debounced(
            self.value2_input.textChanged,
            lambda: self.set_setting(
                "value2", self.value2_input.text(), "Filter Max value Changed"
            ),
        )
        self.value2_row = FormRow("Max value", self.value2_input, label_width=88)
        condition.addWidget(self.value2_row)

        expression = ConfigSection()
        expression._undo_composite = True
        self.expression_section = expression
        self.expression_input = SQLFormulaWidget()
        self.expression_input.set_placeholder_text(EXPRESSION_PLACEHOLDER)
        self.expression_input.set_available_columns(list(self.schema(0)))
        self.expression_input.set_validate_callback(self.validate_expression)
        self.expression_input.setMinimumHeight(120)
        self._debounced(self.expression_input.textChanged, self._commit_expression)
        self.expression_input.editingFinished.connect(self._commit_expression)
        expression.addWidget(self.expression_input)

        dock_layout.addWidget(condition)
        dock_layout.addWidget(expression)
        dock_layout.addStretch()

        self._sync_widgets_from_model()

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        if self._mode() == "expression":
            chips: list[tuple[str, str]] = [("Expression", "accent")]
            if str(self.settings.get("expression") or "").strip():
                chips.append(("WHERE clause set", ""))
            return chips, ""
        chips = [("Simple", "accent")]
        column = str(self.settings.get("column") or "")
        if column:
            operation = str(self.settings.get("operation") or "")
            chips.append((f"{column} {operation}".strip(), ""))
        return chips, ""

    # -- commits ----------------------------------------------------------
    def _commit_mode(self, label: str) -> None:
        mode = "expression" if label == "Expression" else "builder"
        self.set_setting("mode", mode, "Filter Mode Changed")

    def _commit_column(self, value: str) -> None:
        if value != self.settings.get("column"):
            self.set_setting("column", value, "Filter Column Changed")
        operations = core.operations_for(self._column_dtype(value))
        if self.settings.get("operation") not in operations:
            self.set_setting("operation", "Equals", "Filter Operation Changed")

    def _commit_expression(self) -> None:
        try:
            text = self.expression_input.get_text() or ""
        except (AttributeError, RuntimeError):
            return
        self.set_setting(
            "expression", text, "Filter Expression Changed", "filter-expression"
        )

    def _column_dtype(self, column: str):
        return self.schema(0).get(column) if column else None

    # -- model -> widgets ------------------------------------------------
    def _sync_widgets_from_model(self) -> None:
        if getattr(self, "mode_selector", None) is None:
            return
        self._sync_mode_widget()
        self._fill_column_combo()
        self._fill_operation_combo()

        for widget, key in (
            (self.value_input, "value"),
            (self.value2_input, "value2"),
        ):
            text = str(self.settings.get(key) or "")
            if widget.text() != text:
                blocked = widget.blockSignals(True)
                try:
                    widget.setText(text)
                finally:
                    widget.blockSignals(blocked)

        expression = str(self.settings.get("expression") or "")
        try:
            if self.expression_input.get_text() != expression:
                self.expression_input.set_text(expression)
        except RuntimeError:
            pass

        self._apply_visibility()

    def _sync_mode_widget(self) -> None:
        label = "Expression" if self._mode() == "expression" else "Simple"
        self.mode_selector.blockSignals(True)
        try:
            self.mode_selector.set_value(label)
        finally:
            self.mode_selector.blockSignals(False)

    def _fill_column_combo(self) -> None:
        columns = list(self.schema(0))
        value = str(self.settings.get("column") or "")
        blocked = self.column_selector.blockSignals(True)
        try:
            self.column_selector.clear()
            self.column_selector.addItem("(select column)", "")
            for name in columns:
                self.column_selector.addItem(name, name)
            if value and value not in columns:
                self.column_selector.addItem(f"{value} (missing)", value)
            index = self.column_selector.findData(value) if value else 0
            self.column_selector.setCurrentIndex(max(0, index))
        finally:
            self.column_selector.blockSignals(blocked)

    def _fill_operation_combo(self) -> None:
        column = str(self.settings.get("column") or "")
        operations = core.operations_for(self._column_dtype(column))
        value = str(self.settings.get("operation") or "Equals")
        blocked = self.operation_selector.blockSignals(True)
        try:
            self.operation_selector.clear()
            for operation in operations:
                self.operation_selector.addItem(operation, operation)
            index = self.operation_selector.findData(value)
            self.operation_selector.setCurrentIndex(max(0, index))
        finally:
            self.operation_selector.blockSignals(blocked)

    def _apply_visibility(self) -> None:
        if getattr(self, "condition_section", None) is None:
            return
        is_expression = self._mode() == "expression"
        self.condition_section.setVisible(not is_expression)
        self.expression_section.setVisible(is_expression)
        self.value2_row.setVisible(
            not is_expression and self.settings.get("operation") == "In Between"
        )

    def after_change(self) -> None:
        if getattr(self, "condition_section", None) is None:
            return
        self._apply_visibility()
        self._fill_operation_combo()

    # -- expression validation -------------------------------------------
    def validate_expression(self, text: str) -> list[dict]:
        """EXPLAIN the WHERE clause against the live schema for the editor."""
        columns = list(self.schema(0))
        if not columns or not (text or "").strip():
            return []
        try:
            sample = pl.DataFrame(schema=frame_schema(self.frames[0]))
            prepared = prepare_expression_sql(text, columns)
            with duckdb.connect(":memory:") as duck:
                duck.register("df_filter", sample)
                duck.execute(
                    f"EXPLAIN SELECT * FROM df_filter WHERE {prepared}"
                ).fetchall()
            return []
        except Exception as exc:  # noqa: BLE001 - diagnostics are advisory
            return [
                {
                    "message": shorten_error(str(exc)),
                    "line": 1,
                    "column": 0,
                    "length": 1,
                }
            ]


@register_node(PreparationNodes.FILTER, NodeTypes.PREPARATION)
class TriggerNode_Filter(ShapingNode):
    icon = "node_filter"
    node_code = PreparationNodes.FILTER
    node_type = NodeTypes.PREPARATION
    node_title = "Filter"
    content_class = FilterContent
    output_text = ("T", "F")
    content_label_objname = "trigger_node_filter"
    style = {}  # noqa: RUF012 - shared empty node style
