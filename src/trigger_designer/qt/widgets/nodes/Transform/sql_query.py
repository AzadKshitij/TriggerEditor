"""SQL Query node: Qt wrapper around core/shaping/sql_query.py.

The query text is the only setting. It reaches the model through
``set_setting`` (one undo step per typing burst) and runs only through
``core.sql_guard`` - the dock never executes SQL itself, apart from the
zero-row schema probe behind the editor's error line.
"""

from __future__ import annotations

from typing import Any

from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

from trigger_designer.core.node_configuration import (
    NodeTypes,
    TransformNodes,
    register_node,
)
from trigger_designer.core.shaping import sql_query as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)
from trigger_designer.qt.widgets.sql_formula_editor import SQLFormulaWidget

SQL_PLACEHOLDER = "SELECT *\nFROM t1"
SQL_EDITOR_MIN_HEIGHT = 170


class SqlQueryContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.sql_query"
    OUTPUT_KINDS = ("sql",)
    INPUTS = 3
    OPTIONAL_INPUTS = frozenset({1, 2})
    HISTORY = "SQL Query"
    SUMMARY = "t1 required · t2, t3 optional"
    FORM = (
        FormSection(
            "Query",
            (
                Field("sql", "SQL", "sql", label_above=True),
                Field(
                    "_sql_hint",
                    "One read-only SELECT. Connected inputs are the tables t1, t2 and t3 "
                    "(t2 and t3 are optional). Files and random functions are blocked.",
                    "note",
                ),
            ),
        ),
    )

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        self._sql_widget: SQLFormulaWidget | None = None
        self._sql_error: QLabel | None = None

    # -- editor ------------------------------------------------------------
    def _burst_key(self, spec: Field, prefix: str = "") -> str | None:
        if spec.kind == "sql":
            return f"{self.node.node_title}-{prefix}{spec.key}"
        return super()._burst_key(spec, prefix)

    def _completion_names(self) -> list[str]:
        names = list(core.TABLE_NAMES)
        for index in range(len(core.TABLE_NAMES)):
            for column in self.schema(index):
                if column not in names:
                    names.append(column)
        return names

    def _validate(self, text: str) -> list[dict]:
        schemas = {
            name: self.schema(index)
            for index, name in enumerate(core.TABLE_NAMES)
            if index < len(self.frames) and self.frames[index] is not None
        }
        return core.diagnostics(text, schemas)

    def _make_widget(self, spec: Field, value: Any, commit) -> QWidget:
        if spec.kind != "sql":
            return super()._make_widget(spec, value, commit)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        editor = SQLFormulaWidget()
        editor._undo_composite = True
        editor.editor.bracket_columns = False
        editor.set_placeholder_text(SQL_PLACEHOLDER)
        editor.setMinimumHeight(SQL_EDITOR_MIN_HEIGHT)
        editor.set_available_columns(self._completion_names())
        editor.set_validate_callback(self._validate)
        if value:
            editor.set_text(str(value))

        error = QLabel()
        error.setObjectName("formulaSectionError")
        error.setWordWrap(True)
        error.hide()
        editor.editor.allErrorsDetected.connect(self._show_errors)

        editor.textChanged.connect(self._mark_text_dirty)
        self._debounced(editor.textChanged, lambda: self._commit_editor(commit))
        editor.editingFinished.connect(lambda: self._commit_editor(commit))

        layout.addWidget(editor)
        layout.addWidget(error)
        self._sql_widget, self._sql_error = editor, error
        return container

    def _editor_text(self) -> str | None:
        try:
            return None if self._sql_widget is None else self._sql_widget.get_text()
        except RuntimeError:
            self._sql_widget = None
            return None

    def _commit_editor(self, commit) -> None:
        text = self._editor_text()
        if text is not None:
            commit(text)

    def _show_errors(self, messages: list) -> None:
        label = self._sql_error
        if label is None:
            return
        try:
            if messages:
                label.setText(str(messages[0]))
                label.show()
            else:
                label.clear()
                label.hide()
        except RuntimeError:
            self._sql_error = None

    def sql_editors(self) -> list[QWidget]:
        return [] if self._sql_widget is None else [self._sql_widget]

    def commit_pending_dock_edits(self, *, evaluate: bool = True) -> None:
        """Read the editor into the model before the dock is destroyed."""
        text = self._editor_text()
        if text is not None and text != self.settings.get("sql"):
            self.set_setting(
                "sql",
                text,
                f"{self.HISTORY} SQL Changed",
                f"{self.node.node_title}-sql",
                evaluate=False,
            )
        if evaluate:
            self._evaluate_pending()

    # -- model -> widgets ----------------------------------------------------
    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        self._sql_widget = self._sql_error = None
        self.cancel_pending_evaluation()
        super().create_layout(dock_layout)

    def _write_widget(self, spec: Field, widget: QWidget, value: Any = None) -> None:
        if spec.kind != "sql":
            super()._write_widget(spec, widget)
            return
        text = self.settings.get(spec.key) or ""
        editor = self._sql_widget
        if editor is None or editor.get_text() == text:
            return
        editor.blockSignals(True)
        try:
            editor.set_text(text)
        finally:
            editor.blockSignals(False)

    def _sync_widgets_from_model(self) -> None:
        if self.history.is_restoring_history:
            self.cancel_pending_evaluation()
        super()._sync_widgets_from_model()


@register_node(TransformNodes.SQL_QUERY, NodeTypes.TRANSFORM)
class TriggerNode_SqlQuery(ShapingNode):
    icon = "node_sql_query"
    node_code = TransformNodes.SQL_QUERY
    node_type = NodeTypes.TRANSFORM
    node_title = "SQL Query"
    content_class = SqlQueryContent
    output_text = ("",)
    content_label_objname = "trigger_node_sql_query"
