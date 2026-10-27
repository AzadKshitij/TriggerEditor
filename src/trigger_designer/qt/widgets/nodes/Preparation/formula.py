"""Formula node: Qt wrapper only; the logic is core/shaping/formula.py."""

from __future__ import annotations

from functools import partial
from typing import Any

import polars as pl
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import formula as core
from trigger_designer.qt.helpers.shaping_support import ShapingContent, ShapingNode
from trigger_designer.qt.widgets.common import (
    EmptyStateLabel,
    IconButton,
    NoWheelComboBox,
)
from trigger_designer.qt.widgets.sql_formula_editor import SQLFormulaWidget

EMPTY_TARGET_OPTION = "Select target column"
NEW_COLUMN_OPTION = "+ add column"
FORMULA_PLACEHOLDER = (
    "Enter formula e.g.:\nCASE WHEN [Age] > 30 THEN 'Adult' ELSE 'Young' END"
)


def _dtype_label(dtype: Any) -> str:
    base = getattr(dtype, "base_type", lambda: dtype)()
    if base in (pl.String, pl.Categorical):
        return "Categorical" if base == pl.Categorical else "String"
    if base == pl.Boolean:
        return "Boolean"
    if base == pl.Date:
        return "Date"
    if base == pl.Time:
        return "Time"
    if isinstance(base, pl.Datetime) or base == pl.Datetime:
        return "Datetime"
    text = str(base)
    if "Int" in text or "UInt" in text:
        return "Integer"
    if "Float" in text or "Decimal" in text:
        return "Float"
    return "String"


class _ResizeGrip(QFrame):
    """Drag handle adjusting one section editor's fixed height."""

    def __init__(
        self, content: FormulaContent, section_index: int, editor: QWidget
    ) -> None:
        super().__init__()
        self._content = content
        self._section_index = section_index
        self._editor = editor
        self.setObjectName("formulaResizeGrip")
        self.setFixedHeight(4)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self._press_y: int | None = None
        self._press_height = core.DEFAULT_EDITOR_HEIGHT

    def mousePressEvent(self, event) -> None:
        self._press_y = event.globalPosition().toPoint().y()
        self._press_height = self._editor.height()

    def mouseMoveEvent(self, event) -> None:
        if self._press_y is None:
            return
        delta = event.globalPosition().toPoint().y() - self._press_y
        self._editor.setFixedHeight(
            min(
                core.MAX_EDITOR_HEIGHT,
                max(core.MIN_EDITOR_HEIGHT, self._press_height + delta),
            )
        )

    def mouseReleaseEvent(self, event) -> None:
        if self._press_y is None:
            return
        self._press_y = None
        self._content._commit_height(self._section_index, self._editor.height())


class _FormulaCard(QFrame):
    """Collapsible formula card: the header keeps target + type in view."""

    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FormulaCard")
        self._undo_composite = True
        self._collapsed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = QFrame(self)
        self.header.setObjectName("FormulaCardHeader")
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_layout = QHBoxLayout(self.header)
        self.header_layout.setContentsMargins(4, 2, 4, 2)
        self.header_layout.setSpacing(2)

        self.chevron = QLabel("\u25be", self.header)
        self.chevron.setObjectName("SectionChevron")
        self.chevron.setFixedWidth(10)
        self.chevron.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.header_layout.addWidget(self.chevron)

        self.body = QFrame(self)
        self.body.setObjectName("FormulaCardBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(4, 2, 4, 4)
        self.body_layout.setSpacing(2)

        layout.addWidget(self.header)
        layout.addWidget(self.body)

        self.header.mousePressEvent = self._on_header_pressed  # type: ignore[method-assign]

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self.body.setVisible(not collapsed)
        self.chevron.setText("\u25b8" if collapsed else "\u25be")
        self.toggled.emit(collapsed)

    def _on_header_pressed(self, event) -> None:
        self.set_collapsed(not self._collapsed)


class FormulaContent(ShapingContent):
    """Ordered formula cards; each card edits one section in settings."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.formula"
    OUTPUT_KINDS = ("formula",)
    INPUTS = 1
    HISTORY = "Formula"
    SUMMARY = "calculated columns"

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        self.output_variables = [f"var_formula_{self.id}"]
        self.variable_name = self.output_variables[0]
        self.section_widgets: list[dict] = []
        self.section_errors: dict[int, str] = {}
        self._collapsed_sections: set[int] = set()

    # -- model helpers ----------------------------------------------------
    def _section_list(self) -> list[dict]:
        return core.normalize({"sections": self.settings.get("sections") or []})[
            "sections"
        ]

    def _commit(
        self,
        sections: list[dict],
        text: str,
        *,
        structural: bool = False,
        merge_key: str | None = None,
        evaluate: bool = True,
    ) -> None:
        normalized = core.normalize({"sections": sections})["sections"]
        if normalized == self.settings.get("sections"):
            return
        self.set_setting(
            "sections",
            normalized,
            text,
            merge_key,
            structural=structural,
            evaluate=evaluate,
        )

    def _configured_count(self) -> int:
        return sum(1 for section in self._section_list() if core.is_configured(section))

    def _available_before(self, index: int) -> list[str]:
        columns = list(self.schema(0))
        for section in self._section_list()[:index]:
            target = section["target_column"].strip()
            if target and target not in columns:
                columns.append(target)
        return columns

    def _target_items(self, index: int) -> list[str]:
        available = self._available_before(index)
        current = self._section_list()[index]["target_column"].strip()
        items = [EMPTY_TARGET_OPTION, NEW_COLUMN_OPTION]
        if current and current not in available:
            items.append(current)
        items.extend(available)
        return items

    def _dtype_state(self, index: int) -> tuple[str, bool]:
        section = self._section_list()[index]
        target = section["target_column"].strip()
        schema = self.schema(0)
        if target and target in schema:
            return _dtype_label(schema[target]), False
        return section.get("target_dtype") or core.AUTO_DTYPE_OPTION, True

    def _known_targets(self, exclude: int) -> set[str]:
        known = {name.lower() for name in self.schema(0)}
        for index, section in enumerate(self._section_list()):
            if index == exclude:
                continue
            target = section["target_column"].strip()
            if target:
                known.add(target.lower())
        return known

    # -- dock construction ----------------------------------------------
    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        self.cancel_pending_evaluation()
        self.add_section_button = None
        if not self.ready():
            dock_layout.addWidget(EmptyStateLabel())
            return

        self.add_section_button = IconButton.themed(
            "Add formula",
            rsm_icon=self.node.rsm.get("icon_add"),
        )
        self.add_section_button.clicked.connect(self._add_section)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)
        self.sections_layout = QVBoxLayout()
        self.sections_layout.setSpacing(2)
        main_layout.addLayout(self.sections_layout)
        main_layout.addStretch()
        dock_layout.addWidget(container, 1)

        self._rebuild_cards()

    def dock_actions(self) -> list:
        button = getattr(self, "add_section_button", None)
        return [button] if button is not None else []

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        chips: list[tuple[str, str]] = []
        columns = self.schema(0)
        if columns:
            chips.append((f"{len(columns)} columns", ""))
        chips.append(
            (
                f"{self._configured_count()} of {len(self._section_list())} formulas",
                "accent" if self._configured_count() else "",
            )
        )
        return chips, ""

    def _refresh_counts(self) -> None:
        self.refresh_dock_context()

    # -- cards ------------------------------------------------------------
    @staticmethod
    def _clear_layout(layout: QVBoxLayout | None) -> bool:
        if layout is None:
            return False
        try:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        except RuntimeError:
            # The Config Dock cleared while a modal dialog was open.
            return False
        return True

    def _rebuild_cards(self) -> None:
        layout = getattr(self, "sections_layout", None)
        if layout is None:
            return
        self.cancel_pending_evaluation()
        if not self._clear_layout(layout):
            self.sections_layout = None
            self.section_widgets = []
            self.section_errors = {}
            return
        self.section_widgets = []
        self.section_errors = {}
        sections = self._section_list()
        for index, section in enumerate(sections):
            if index > 0:
                separator = QFrame()
                separator.setObjectName("formulaSeparator")
                separator.setFixedHeight(1)
                self.sections_layout.addWidget(separator)

            card = _FormulaCard()
            target_selector = NoWheelComboBox()
            target_selector.setMinimumHeight(30)
            target_selector.addItems(self._target_items(index))
            target = section["target_column"]
            found = target_selector.findText(target or EMPTY_TARGET_OPTION)
            target_selector.setCurrentIndex(max(0, found))
            # PySide passes the signal's argument through a partial, so the
            # slots are wrapped in lambdas that ignore it.
            target_selector.activated.connect(
                lambda _i, i=index, s=target_selector: self._on_target_selected(i, s)
            )

            dtype_selector = NoWheelComboBox()
            dtype_selector.setMinimumHeight(30)
            dtype_selector.addItems(core.DTYPE_OPTIONS)
            label, enabled = self._dtype_state(index)
            dtype_selector.setCurrentText(label)
            dtype_selector.setEnabled(enabled)
            dtype_selector.activated.connect(
                lambda _i, i=index, s=dtype_selector: self._on_dtype_selected(i, s)
            )

            remove_button = IconButton.themed(
                "Remove formula",
                rsm_icon=self.node.rsm.get("icon_remove"),
            )
            remove_button.clicked.connect(partial(self._remove_section, index))

            card.header_layout.addWidget(target_selector, 1)
            card.header_layout.addWidget(dtype_selector, 1)
            card.header_layout.addStretch()
            card.header_layout.addWidget(remove_button)

            formula_input = SQLFormulaWidget()
            formula_input._undo_composite = True
            formula_input.set_placeholder_text(FORMULA_PLACEHOLDER)
            formula_input.setFixedHeight(section["editor_height"])
            formula_input.set_available_columns(self._available_before(index))
            if section["formula_text"]:
                formula_input.set_text(section["formula_text"])
            formula_input.set_validate_callback(partial(self._validate_section, index))
            formula_input.textChanged.connect(self._mark_text_dirty)
            self._debounced(
                formula_input.textChanged,
                partial(self._commit_text, index, evaluate=False),
            )
            formula_input.editingFinished.connect(
                partial(self._on_editor_finished, index)
            )

            error_label = QLabel()
            error_label.setObjectName("formulaSectionError")
            error_label.setWordWrap(True)
            error_label.hide()

            card.body_layout.addWidget(formula_input)
            card.body_layout.addWidget(_ResizeGrip(self, index, formula_input))
            card.body_layout.addWidget(error_label)
            card.set_collapsed(index in self._collapsed_sections)
            card.toggled.connect(partial(self._on_card_toggled, index))

            self.sections_layout.addWidget(card)
            self.section_widgets.append(
                {
                    "card": card,
                    "target_selector": target_selector,
                    "dtype_selector": dtype_selector,
                    "formula_input": formula_input,
                    "error_label": error_label,
                    "target": section["target_column"],
                    "dtype": section["target_dtype"],
                }
            )
        self._refresh_counts()

    def _on_card_toggled(self, index: int, collapsed: bool) -> None:
        if collapsed:
            self._collapsed_sections.add(index)
        else:
            self._collapsed_sections.discard(index)

    # -- commits ----------------------------------------------------------
    def _on_target_selected(self, index: int, selector) -> None:
        text = selector.currentText()
        if text == NEW_COLUMN_OPTION:
            self._prompt_new_column(index, selector)
            return
        target = "" if text == EMPTY_TARGET_OPTION else text
        sections = self._section_list()
        if sections[index]["target_column"] == target:
            return
        sections[index]["target_column"] = target
        self._commit(sections, "Formula Target Changed", structural=True)

    def _prompt_new_column(self, index: int, selector) -> None:
        known = self._known_targets(index)
        text = self._section_list()[index]["target_column"]
        with self._hold_deferred_evaluation():
            while True:
                name, accepted = QInputDialog.getText(
                    None, "Add Column", "Column name:", text=text
                )
                if not accepted:
                    pending = self._pending_evaluate
                    sections = self._section_list()
                    target = (
                        sections[index]["target_column"]
                        if 0 <= index < len(sections)
                        else ""
                    )
                    self._reset_target_selector(selector, target)
                    self._pending_evaluate = pending
                    return
                name = name.strip()
                if not name:
                    QMessageBox.warning(
                        self, "Add Column", "Column name cannot be empty."
                    )
                    continue
                if name.lower() in known:
                    QMessageBox.warning(
                        self, "Add Column", f"Column '{name}' already exists."
                    )
                    text = name
                    continue
                sections = self._section_list()
                sections[index]["target_column"] = name
                self._commit(sections, "Formula Target Changed", structural=True)
                return

    @staticmethod
    def _reset_target_selector(selector, target: str) -> None:
        """Put a cancelled Add Column combo back without rebuilding the dock."""
        try:
            selector.blockSignals(True)
        except RuntimeError:
            return
        try:
            selector.setCurrentText(target or EMPTY_TARGET_OPTION)
        except RuntimeError:
            pass
        finally:
            try:
                selector.blockSignals(False)
            except RuntimeError:
                pass

    def _on_dtype_selected(self, index: int, selector) -> None:
        text = selector.currentText()
        target_dtype = "" if text == core.AUTO_DTYPE_OPTION else text
        sections = self._section_list()
        if sections[index]["target_dtype"] == target_dtype:
            return
        sections[index]["target_dtype"] = target_dtype
        self._commit(sections, "Formula Type Changed")

    def _commit_text(self, index: int, *, evaluate: bool = True) -> None:
        # Capture every editor, not only the one whose debounce fired. A
        # model update re-projects the other cards, so committing one section
        # alone would write stale model text back into a sibling editor that
        # the user has typed in but whose debounce has not fired yet.
        sections, changed = self._editor_sections()
        if changed:
            merge_key = f"formula-text-{index}" if changed == [index] else None
            self._commit(
                sections,
                "Formula Text Changed",
                merge_key=merge_key,
                evaluate=evaluate,
            )
            for changed_index in changed:
                self._refresh_error(changed_index)
        if evaluate:
            self._evaluate_pending()

    def _editor_sections(self) -> tuple[list[dict], list[int]]:
        """Return the model sections with every editor's current text applied."""
        sections = self._section_list()
        changed: list[int] = []
        for index, widgets in enumerate(getattr(self, "section_widgets", ())):
            if index >= len(sections):
                break
            try:
                text = widgets["formula_input"].get_text() or ""
            except KeyError, RuntimeError:
                continue
            if sections[index]["formula_text"] == text:
                continue
            sections[index]["formula_text"] = text
            changed.append(index)
        return sections, changed

    def _on_editor_finished(self, index: int) -> None:
        """Commit on focus-out without evaluating until every editor is left."""
        self._commit_text(index, evaluate=False)
        self._schedule_focus_out_evaluation()

    def sql_editors(self) -> list:
        return [
            widgets["formula_input"]
            for widgets in getattr(self, "section_widgets", ())
            if "formula_input" in widgets
        ]

    def commit_pending_dock_edits(self, *, evaluate: bool = True) -> None:
        """Read every card's text into the model before the dock is destroyed."""
        sections, changed = self._editor_sections()
        if changed:
            merge_key = f"formula-text-{changed[0]}" if len(changed) == 1 else None
            self._commit(
                sections,
                "Formula Text Changed",
                merge_key=merge_key,
                evaluate=False,
            )
            for index in changed:
                self._refresh_error(index)

        if evaluate:
            self._evaluate_pending()
        else:
            self.cancel_pending_evaluation()

    def _commit_height(self, index: int, height: int) -> None:
        sections = self._section_list()
        if index >= len(sections):
            return
        height = min(core.MAX_EDITOR_HEIGHT, max(core.MIN_EDITOR_HEIGHT, height))
        if sections[index]["editor_height"] == height:
            return
        sections[index]["editor_height"] = height
        self._commit(
            sections,
            "Formula Height Changed",
            merge_key=f"formula-height-{index}",
        )

    def _add_section(self) -> None:
        sections = self._section_list()
        if len(sections) >= core.MAX_FORMULA_SECTIONS:
            return
        sections.append(dict(core.DEFAULT_SECTION))
        self._commit(sections, "Formula Section Added", structural=True)

    def _remove_section(self, index: int) -> None:
        sections = self._section_list()
        if not 0 <= index < len(sections):
            return
        del sections[index]
        self._commit(sections, "Formula Section Removed", structural=True)

    # -- validation -------------------------------------------------------
    def _validate_section(self, index: int, text: str) -> list[dict]:
        sections = self._section_list()
        if 0 <= index < len(sections):
            sections[index]["formula_text"] = text
        return core.validate_section(self.frames, {"sections": sections}, index)

    def _refresh_error(self, index: int) -> None:
        if index >= len(self.section_widgets):
            return
        widget = self.section_widgets[index]
        try:
            text = widget["formula_input"].get_text() or ""
        except RuntimeError:
            return
        errors = self._validate_section(index, text)
        label = widget["error_label"]
        if errors:
            message = str(errors[0].get("message") or "Invalid formula")
            self.section_errors[index] = message
            label.setText(message)
            label.show()
        else:
            self.section_errors.pop(index, None)
            label.clear()
            label.hide()

    # -- model -> widgets -------------------------------------------------
    def _sync_widgets_from_model(self) -> None:
        if self.history.is_restoring_history:
            self.cancel_pending_evaluation()
        if getattr(self, "sections_layout", None) is None:
            return
        sections = self._section_list()
        structural = len(self.section_widgets) != len(sections) or any(
            widgets["target"] != section["target_column"]
            or widgets["dtype"] != section["target_dtype"]
            for widgets, section in zip(self.section_widgets, sections)
        )
        if structural:
            self._rebuild_cards()
            return
        for widgets, section in zip(self.section_widgets, sections):
            try:
                if widgets["formula_input"].get_text() != section["formula_text"]:
                    widgets["formula_input"].set_text(section["formula_text"])
                widgets["formula_input"].setFixedHeight(section["editor_height"])
            except RuntimeError:
                continue
        self._refresh_counts()

    def after_change(self) -> None:
        self._refresh_counts()


@register_node(PreparationNodes.FORMULA, NodeTypes.PREPARATION)
class TriggerNode_Formula(ShapingNode):
    icon = "node_formula"
    node_code = PreparationNodes.FORMULA
    node_type = NodeTypes.PREPARATION
    node_title = "Formula"
    content_class = FormulaContent
    output_text = ("Out",)
    content_label_objname = "trigger_node_formula"
    style = {}  # noqa: RUF012 - shared empty node style
