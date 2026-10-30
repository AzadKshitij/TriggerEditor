"""Shared scaffolding for the shaping nodes (docs/plan/07-shaping-nodes.md)."""

from __future__ import annotations

import copy
import importlib
import json
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import polars as pl
from nodeeditor.utils_no_qt import dumpException
from qtpy.QtCore import QTimer, Signal
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.errors import translate_exception
from trigger_designer.core.shaping.common import ShapingError, live_sample
from trigger_designer.qt.helpers.config_content import ConfigContent
from trigger_designer.qt.helpers.deferred_evaluation import DeferredEvaluation
from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from trigger_designer.qt.node_base import (
    TriggerGraphicsNode,
    TriggerNode,
    frame_schema,
)
from trigger_designer.qt.undo.protocol import is_syncing
from trigger_designer.qt.widgets.common import (
    CONTROL_H,
    ColumnChecklist,
    ColumnPicker,
    ConfigSection,
    EmptyStateLabel,
    FormGrid,
    FormRow,
    NoWheelComboBox,
    RuleStack,
    SegmentedControl,
    dtype_label,
)

#: "No explicit value" marker for ``_write_widget``.
_UNSET = object()


@dataclass(frozen=True)
class Field:
    """One dock control bound to ``settings[key]`` (or a key inside a list card)."""

    key: str
    label: str
    kind: str
    options: tuple = ()
    minimum: float = 0
    maximum: float = 1_000_000
    #: ``float`` kinds only: spin-box step and decimals (None keeps Qt's 1.0 / 2)
    step: float | None = None
    decimals: int | None = None
    placeholder: str = ""
    tip: str = ""
    blank: bool = False
    input: int = 0
    filter: str = ""  # "" all | "text" | "numeric" | "numeric_only" | "date"
    show_if: Callable[[dict], bool] | None = None
    items: tuple = ()
    item_default: dict = field(default_factory=dict)
    max_items: int = 50
    hint: str = ""
    summary: Callable[[dict], str] | None = None
    collapsible: bool = False
    rebuild_on_change: bool = False
    label_above: bool = False


@dataclass(frozen=True)
class FormSection:
    """A form section; ``collapsible`` hides genuinely optional controls."""

    title: str = ""
    fields: tuple = ()
    info: str = ""
    collapsible: bool = False
    collapsed: bool = False


def _passes(dtype: pl.DataType, kind: str) -> bool:
    if kind == "text":
        return dtype == pl.String
    if kind == "numeric":
        return dtype == pl.String or dtype.is_numeric()
    if kind == "numeric_only":
        return dtype.is_numeric()
    if kind == "date":
        return dtype == pl.String or dtype == pl.Date or isinstance(dtype, pl.Datetime)
    return True


class WeekdayPicker(QWidget):
    """Seven 30px working-day toggles, in one compact row."""

    _undo_composite = True

    changed = Signal(list)

    def __init__(
        self,
        options: tuple,
        checked=(),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("WeekdayPicker")
        self._buttons: list[QPushButton] = []
        self._values: list[str] = []
        self._suspend = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        selected = set(checked)
        for value, label in options:
            button = QPushButton(label, self)
            button.setObjectName("DayToggle")
            button.setCheckable(True)
            button.setFixedSize(30, CONTROL_H)
            button.setChecked(value in selected)
            button.setToolTip(value)
            button.setAccessibleName(value)
            button.toggled.connect(self._emit)
            layout.addWidget(button)
            self._buttons.append(button)
            self._values.append(value)
        layout.addStretch(1)

    def value(self) -> list[str]:
        return [
            value
            for value, button in zip(self._values, self._buttons)
            if button.isChecked()
        ]

    def set_value(self, checked) -> None:
        self._suspend = True
        try:
            selected = set(checked or ())
            for value, button in zip(self._values, self._buttons):
                button.blockSignals(True)
                button.setChecked(value in selected)
                button.blockSignals(False)
        finally:
            self._suspend = False

    def _emit(self, _checked: bool) -> None:
        if not self._suspend:
            self.changed.emit(self.value())


class SuffixEditor(QWidget):
    """Replace-in-place or keep the source and write a suffixed column."""

    _undo_composite = True

    changed = Signal(str)

    def __init__(self, value: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SuffixEditor")
        self._suspend = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._keep = QCheckBox("Keep original", self)
        self._keep.toggled.connect(self._toggled)
        layout.addWidget(self._keep)

        self._suffix = QLineEdit(self)
        self._suffix.setObjectName("SuffixEdit")
        self._suffix.setMinimumHeight(CONTROL_H)
        self._suffix.setPlaceholderText("_clean")
        self._suffix.setClearButtonEnabled(True)
        self._suffix.textChanged.connect(self._text_changed)
        self._suffix.editingFinished.connect(self._finished)
        layout.addWidget(self._suffix, 1)
        self.set_value(value)

    def value(self) -> str:
        if not self._keep.isChecked():
            return ""
        return self._suffix.text().strip() or "_clean"

    def set_value(self, value: str) -> None:
        self._suspend = True
        try:
            self._keep.blockSignals(True)
            self._keep.setChecked(bool(value))
            self._keep.blockSignals(False)
            self._suffix.blockSignals(True)
            self._suffix.setText(value or "_clean")
            self._suffix.blockSignals(False)
            self._suffix.setVisible(bool(value))
        finally:
            self._suspend = False

    def _toggled(self, checked: bool) -> None:
        if self._suspend:
            return
        self._suffix.setVisible(checked)
        if checked and not self._suffix.text().strip():
            self._suffix.setText("_clean")
        self.changed.emit(self.value())

    def _text_changed(self, text: str) -> None:
        if not self._suspend and self._keep.isChecked() and text.strip():
            self.changed.emit(self.value())

    def _finished(self) -> None:
        if not self._suspend and self._keep.isChecked():
            if not self._suffix.text().strip():
                self._suffix.setText("_clean")
            self.changed.emit(self.value())


def clear_layout(layout: QLayout | None, *, delete: bool = False) -> bool:
    """Delete the widgets and nested layouts in ``layout``; keep it unless ``delete``.

    False when there is nothing to clear or its C++ object is already gone
    (the Config Dock cleared while a modal dialog was open).
    """
    if layout is None:
        return False
    try:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                clear_layout(item.layout(), delete=True)
        if delete:
            layout.deleteLater()
    except RuntimeError:
        return False
    return True


class ShapingContent(DeferredEvaluation, ConfigContent, SerializableContentMixin):
    SETTINGS: dict = {}  # noqa: RUF012 - subclass defaults, never mutated
    MODULE = ""
    RUNNER = "run_node"
    OUTPUT_KINDS: tuple = ("out",)
    INPUTS = 1
    OPTIONAL_INPUTS: frozenset = frozenset()
    FORM: tuple = ()
    HISTORY = "Node"
    SUMMARY = ""
    #: Settings that shape only the window, never the pipeline. They stay out
    #: of the generated code, so a presentation choice cannot change the code.
    PRESENTATION_SETTINGS: tuple = ()

    def get_serialized_state_schema(self) -> dict:
        return {"settings": {"default": copy.deepcopy(self.SETTINGS)}}

    def __init__(self, node: TriggerNode, parent: QWidget | None = None) -> None:
        super().__init__(node, parent)
        self.settings: dict = copy.deepcopy(self.SETTINGS)
        self.frames: list = [None] * self.INPUTS
        self.input_vars: list = [""] * self.INPUTS
        self.outputs: list = []
        self.chips: list = []
        self.output_variables = [f"var_{k}_{self.id}" for k in self.OUTPUT_KINDS]
        for i, name in enumerate(self.output_variables):
            setattr(self, "variable_name" if i == 0 else f"out{i}_variable_name", name)
        self._widgets: dict = {}
        self._rows: dict = {}
        self._stacks: dict = {}
        self._timers: list[QTimer] = []
        self._expanded_cards: dict[str, set[int]] = {}
        self._card_widgets: dict[str, list[dict]] = {}
        #: A text edit has reached the model but its node evaluation is waiting
        #: for focus to leave the SQL editor (see ``sql_editors``).
        self._pending_evaluate = False
        #: Invalidates a queued focus-out callback after a dock rebuild.
        self._eval_generation = 0
        #: A modal dialog is running; hold the focus-out callback until it
        #: closes so the nested event loop cannot recompute behind the dialog.
        self._modal_open = False

    # ---- data and code generation ---------------------------------------
    def schema(self, index: int = 0) -> dict:
        frame = self.frames[index] if index < len(self.frames) else None
        return frame_schema(frame) if frame is not None else {}

    def names(self, spec: Field) -> list:
        return [
            name
            for name, dtype in self.schema(spec.input).items()
            if _passes(dtype, spec.filter)
        ]

    def _column_items(self, spec: Field) -> list[tuple[str, str]]:
        schema = self.schema(spec.input)
        return [(name, dtype_label(schema[name])) for name in self.names(spec)]

    def compute(self) -> list:
        module = importlib.import_module(self.MODULE)
        settings = copy.deepcopy(self.settings)
        frames = list(self.frames)
        self.chips = []
        runner = getattr(module, self.RUNNER)
        outs = runner(frames, settings)
        self.outputs = [
            out.lazy() if isinstance(out, pl.DataFrame) else out for out in outs
        ]
        describe = getattr(module, "describe", None)
        if describe is not None:
            try:
                self.chips += describe(frames, settings)
            except Exception:  # noqa: BLE001, S110 - chips are advisory
                pass
        return self.outputs

    def get_code(self) -> str:
        outs = self.output_variables
        missing = [
            i
            for i in range(self.INPUTS)
            if not self.input_vars[i] and i not in self.OPTIONAL_INPUTS
        ]
        if missing or not outs:
            lines = ["import polars as pl"]
            lines += [f"{name} = pl.DataFrame().lazy()" for name in outs]
            return "\n".join(lines) + "\n"
        target = ", ".join(outs) + ("," if len(outs) == 1 else "")
        inputs = ", ".join(var or "None" for var in self.input_vars)
        payload = json.dumps(
            {
                key: value
                for key, value in self.settings.items()
                if key not in self.PRESENTATION_SETTINGS
            },
            sort_keys=True,
        )
        return (
            "import json\nimport polars as pl\n"
            f"from {self.MODULE} import {self.RUNNER} as _run_node\n"
            f"{target} = _run_node([{inputs}], json.loads({payload!r}))\n"
        )

    # ---- one setting change = one undo step ------------------------------
    def set_setting(
        self,
        key: str,
        value: Any,
        text: str,
        merge_key: str | None = None,
        *,
        structural: bool = False,
        evaluate: bool | None = None,
    ) -> None:
        """Store a setting. ``evaluate`` forces (True) or skips (False) the run.

        Left as None the class decides: deferred classes mark the run pending.
        """
        if is_syncing(self) or self.history.is_restoring_history:
            return
        old = self.settings.get(key)
        if value == old:
            return
        self.settings[key] = copy.deepcopy(value)
        self._mark_scene_modified()
        self._update_visibility()
        self.after_change()
        self.refresh_dock_context()
        if evaluate is None:
            self.request_evaluation()
        elif evaluate:
            self._pending_evaluate = False
            self._show_changes_pending(False)
            self.evaluate.emit()
        else:
            self._pending_evaluate = True
            self._show_changes_pending(True)
        push = (
            self.push_list_change
            if structural and isinstance(value, list)
            else self.push_property_change
        )
        # The command's redo re-projects the widgets and would evaluate a
        # second time; the emit above already ran the node on the new model.
        previous = getattr(self, "_suspend_node_evaluation", False)
        self._suspend_node_evaluation = True
        try:
            push(
                ("settings", key),
                copy.deepcopy(old),
                copy.deepcopy(value),
                text,
                merge_key=merge_key,
            )
        finally:
            self._suspend_node_evaluation = previous

    # ---- deferred evaluation -------------------------------------------
    def sql_editors(self) -> list[QWidget]:
        """SQL editors whose focus-out applies a deferred evaluation.

        Most shaping nodes have none. Formula and Filter return the editors
        they own; the shared helper then coalesces a focus move between those
        editors into one evaluation when focus finally leaves them all.
        """
        return []

    def _mark_scene_modified(self) -> None:
        """Mark the document dirty without recording an undo step."""
        scene = getattr(getattr(self, "node", None), "scene", None)
        if scene is None or getattr(scene, "_bulk_loading", False):
            return
        try:
            scene.has_been_modified = True
        except RuntimeError:
            # A queued widget signal can arrive after the design window was
            # deleted; its title listener is no longer callable.
            return

    def _mark_text_dirty(self) -> None:
        """Dirty immediately on a user keystroke, before the debounce fires.

        ``set_text`` during a dock rebuild or a history restore also emits
        ``textChanged``; those writes must not dirty the document.
        """
        if (
            is_syncing(self)
            or self.history.is_restoring_history
            or getattr(self, "_suspend_input_tracking", False)
        ):
            return
        self._mark_scene_modified()

    def _schedule_focus_out_evaluation(self) -> None:
        """Check focus on the next event turn and evaluate once it has left."""
        if self.DEFER_EVALUATION or not self._pending_evaluate:
            # Deferred nodes run when the dock is left, not on editor focus-out.
            return
        self._eval_generation += 1
        generation = self._eval_generation
        QTimer.singleShot(0, lambda: self._focus_out_timer_fired(generation))

    def _focus_out_timer_fired(self, generation: int) -> None:
        if generation != self._eval_generation or self._modal_open:
            return
        if self._sql_editor_has_focus():
            return
        self._evaluate_pending()

    @contextmanager
    def _hold_deferred_evaluation(self):
        """Keep a modal dialog's nested event loop from evaluating behind it."""
        previous = self._modal_open
        self._modal_open = True
        try:
            yield
        finally:
            self._modal_open = previous
            if not previous and self._pending_evaluate:
                self._schedule_focus_out_evaluation()

    def _sql_editor_has_focus(self) -> bool:
        focus = QApplication.focusWidget()
        if focus is None:
            return False
        for editor in self.sql_editors():
            try:
                if editor is focus or editor.isAncestorOf(focus):
                    return True
            except RuntimeError:
                # The dock rebuilt and deleted this editor between the
                # focus-out signal and the timer.
                continue
        return False

    def after_change(self) -> None:
        """Hook after every model change."""

    # ---- dock ------------------------------------------------------------
    def ready(self) -> bool:
        return all(
            self.frames[i] is not None
            for i in range(self.INPUTS)
            if i not in self.OPTIONAL_INPUTS
        )

    def _sections(self):
        for entry in self.FORM:
            if isinstance(entry, FormSection):
                yield entry
            else:
                title, fields = entry
                yield FormSection(title, tuple(fields))

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if not self.ready():
            dock_layout.addWidget(EmptyStateLabel())
            return
        self.release_dock_timers()  # timers of the previous dock's editors
        self._widgets, self._rows, self._stacks = {}, {}, {}
        for section_spec in self._sections():
            section = ConfigSection(
                section_spec.title,
                info=section_spec.info or None,
                collapsible=section_spec.collapsible,
                collapsed=section_spec.collapsed,
            )
            section._undo_composite = True
            for spec in section_spec.fields:
                if spec.kind == "list":
                    row = self._build_list(spec)
                elif spec.kind == "pair":
                    row = self._build_pair(spec)
                elif spec.kind == "note":
                    row = self._build_note(spec)
                else:
                    row = self._build_row(spec)
                self._rows[spec.key] = row
                section.addWidget(row)
            dock_layout.addWidget(section)
        dock_layout.addStretch()
        self._update_visibility()

    def _burst_key(self, spec: Field, prefix: str = "") -> str | None:
        if spec.kind in ("text", "textarea", "int", "float"):
            return f"{self.node.node_title}-{prefix}{spec.key}"
        return None

    def _build_row(self, spec: Field) -> QWidget:
        def commit(value, spec=spec) -> None:
            self.set_setting(
                spec.key,
                value,
                f"{self.HISTORY} {spec.label} Changed",
                self._burst_key(spec),
            )

        widget = self._make_widget(spec, self.settings.get(spec.key), commit)
        self._widgets[spec.key] = widget
        if spec.label_above:
            grid = FormGrid()
            grid.add(spec.label, widget)
            return grid
        return FormRow(spec.label, widget, hint=spec.hint or None, label_width=96)

    def _build_pair(self, spec: Field) -> QWidget:
        grid = FormGrid()
        for column, sub in enumerate(spec.items):

            def commit(value, s=sub) -> None:
                self.set_setting(
                    s.key,
                    value,
                    f"{self.HISTORY} {s.label} Changed",
                    self._burst_key(s),
                )

            widget = self._make_widget(sub, self.settings.get(sub.key), commit)
            self._widgets[sub.key] = widget
            grid.add(sub.label, widget, 0, column)
        return grid

    def _build_note(self, spec: Field) -> QWidget:
        label = QLabel(spec.label)
        label.setObjectName("FieldHint")
        label.setWordWrap(True)
        self._widgets.pop(spec.key, None)
        return label

    def _make_widget(self, spec: Field, value: Any, commit: Callable) -> QWidget:
        if spec.kind in ("picker", "columns"):
            widget = ColumnPicker(
                self._column_items(spec),
                value or (),
                rsm=self.node.rsm,
                label=spec.label,
            )
            widget.changed.connect(commit)
            return widget
        if spec.kind == "segment":
            labels = [label for _value, label in spec.options]
            current = next(
                (label for option, label in spec.options if option == value),
                labels[0] if labels else "",
            )
            widget = SegmentedControl(
                labels,
                current,
                expanded=True,
                compact=len(labels) >= 5,
            )
            widget.changed.connect(
                lambda label, options=spec.options: commit(
                    next(
                        (option for option, text in options if text == label),
                        label,
                    )
                )
            )
            return widget
        if spec.kind == "weekdays":
            widget = WeekdayPicker(spec.options, value or ())
            widget.changed.connect(commit)
            return widget
        if spec.kind == "suffix":
            widget = SuffixEditor("" if value is None else str(value))
            widget.changed.connect(commit)
            return widget
        if spec.kind == "column":
            widget = ColumnPicker(
                self._column_items(spec),
                [value] if value else (),
                "Choose column...",
                single=True,
                allow_blank=spec.blank,
                rsm=self.node.rsm,
                label=spec.label,
            )
            widget.changed.connect(lambda names: commit(names[0] if names else ""))
            return widget
        if spec.kind == "combo":
            widget = NoWheelComboBox()
            widget.setMinimumHeight(30)
            for item_value, label in spec.options:
                widget.addItem(label, item_value)
            self._set_combo(widget, value if value is not None else "")
            widget.currentIndexChanged.connect(
                lambda _index, w=widget: commit(w.currentData())
            )
            return widget
        if spec.kind == "choices":
            options = [item_value for item_value, _label in spec.options]
            widget = ColumnChecklist(options, value or ())
            widget.setMinimumHeight(30)
            widget.changed.connect(commit)
            return widget
        if spec.kind == "check":
            widget = QCheckBox()
            widget.setChecked(bool(value))
            widget.toggled.connect(commit)
            return widget
        if spec.kind in ("int", "float"):
            widget = QSpinBox() if spec.kind == "int" else QDoubleSpinBox()
            widget.setMinimumHeight(30)
            if spec.kind == "float":
                if spec.decimals is not None:
                    widget.setDecimals(spec.decimals)
                if spec.step is not None:
                    widget.setSingleStep(spec.step)
            widget.setRange(spec.minimum, spec.maximum)
            widget.setValue(value if value is not None else spec.minimum)
            self._debounced(widget.valueChanged, lambda w=widget: commit(w.value()))
            return widget
        if spec.kind == "textarea":
            widget = QPlainTextEdit()
            widget.setMinimumHeight(90)
            widget.setPlainText("" if value is None else str(value))
            if spec.placeholder:
                widget.setPlaceholderText(spec.placeholder)
            if spec.tip:
                widget.setToolTip(spec.tip)
            self._debounced(
                widget.textChanged,
                lambda w=widget: commit(w.toPlainText()),
            )
            return widget
        widget = QLineEdit()
        widget.setMinimumHeight(30)
        if spec.placeholder:
            widget.setPlaceholderText(spec.placeholder)
        if spec.tip:
            widget.setToolTip(spec.tip)
        widget.setText("" if value is None else str(value))
        self._debounced(widget.textChanged, lambda w=widget: commit(w.text()))
        return widget

    def _debounced(self, signal, fire: Callable[[], None]) -> None:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(300)

        def guarded() -> None:
            try:
                fire()
            except RuntimeError:  # the editor it captured was destroyed
                pass

        timer.timeout.connect(guarded)
        signal.connect(lambda *_args, t=timer: t.start())
        self._timers.append(timer)

    def flush_pending(self) -> None:
        """Commit every edit still inside its debounce."""
        for timer in list(self._timers):
            try:
                if timer.isActive():
                    timer.stop()
                    timer.timeout.emit()
            except RuntimeError:
                continue

    def release_dock_timers(self) -> None:
        """Stop and drop every debounce timer (the dock's editors are going away).

        A timer holds a callback that reads its editor; one that fires after the
        dock was destroyed would touch a deleted widget.
        """
        timers, self._timers = self._timers, []
        for timer in timers:
            try:
                timer.stop()
                timer.deleteLater()
            except RuntimeError:
                continue

    def commit_pending_dock_edits(self, *, evaluate: bool = True) -> None:
        """Commit text edits still inside their debounce, then the deferred run."""
        self.flush_pending()
        super().commit_pending_dock_edits(evaluate=evaluate)

    @staticmethod
    def _set_combo(widget: NoWheelComboBox, value: Any) -> None:
        index = widget.findData(value)
        if index < 0:
            widget.addItem(f"{value} (missing)", value)
            index = widget.count() - 1
        widget.blockSignals(True)
        widget.setCurrentIndex(index)
        widget.blockSignals(False)

    # ---- ordered lists ---------------------------------------------------
    def _build_list(self, spec: Field) -> QWidget:
        stack = RuleStack(f"Add {spec.label}", self.node.rsm)
        stack.add_requested.connect(lambda f=spec: self._list_change(f, "add"))
        stack.remove_requested.connect(
            lambda index, f=spec: self._list_change(f, "remove", index)
        )
        stack.move_requested.connect(
            lambda index, delta, f=spec: self._list_change(f, "move", index, delta)
        )
        stack.duplicate_requested.connect(
            lambda index, f=spec: self._list_change(f, "duplicate", index)
        )
        self._stacks[spec.key] = stack
        self._fill_stack(spec, stack)
        return stack

    def _card_expanded(self, spec: Field, index: int) -> bool:
        expanded = self._expanded_cards.setdefault(spec.key, {0})
        return index in expanded

    def _set_card_expanded(self, key: str, index: int, expanded: bool) -> None:
        cards = self._expanded_cards.setdefault(key, {0})
        if expanded:
            cards.add(index)
        else:
            cards.discard(index)

    @staticmethod
    def _item_visible(spec: Field, item: dict) -> bool:
        if spec.show_if is None:
            return True
        try:
            return bool(spec.show_if(item))
        except Exception:  # noqa: BLE001 - a bad predicate must not break the dock
            return True

    def _build_card(
        self, spec: Field, stack: RuleStack, index: int, item: dict, count: int
    ) -> dict:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        widgets: dict = {}
        for sub in spec.items:
            value = item.get(sub.key, spec.item_default.get(sub.key))

            def commit(new_value, f=spec, i=index, s=sub):
                self._list_change(f, "edit", i, s, new_value)

            if sub.kind == "pair":
                grid = FormGrid()
                for column, child in enumerate(sub.items):
                    child_value = item.get(child.key, spec.item_default.get(child.key))

                    def child_commit(new_value, f=spec, i=index, s=child):
                        self._list_change(f, "edit", i, s, new_value)

                    child_widget = self._make_widget(child, child_value, child_commit)
                    widgets[child.key] = child_widget
                    grid.add(child.label, child_widget, 0, column)
                layout.addWidget(grid)
            elif sub.kind == "note":
                note = QLabel(sub.label)
                note.setObjectName("FieldHint")
                note.setWordWrap(True)
                layout.addWidget(note)
            else:
                widget = self._make_widget(sub, value, commit)
                widgets[sub.key] = widget
                row = FormRow(sub.label, widget, hint=sub.hint or None, label_width=96)
                row.setVisible(self._item_visible(sub, item))
                layout.addWidget(row)
        summary = ""
        if spec.summary is not None:
            try:
                summary = spec.summary(item)
            except Exception:  # noqa: BLE001 - summary is advisory
                summary = ""
        stack.add_card(
            index,
            count,
            body,
            summary=summary,
            collapsible=spec.collapsible,
            collapsed=not self._card_expanded(spec, index),
            on_toggle=lambda expanded, k=spec.key, i=index: self._set_card_expanded(
                k, i, expanded
            ),
        )
        return widgets

    def _fill_stack(self, spec: Field, stack: RuleStack) -> None:
        stack.setUpdatesEnabled(False)
        try:
            stack.clear()
            items = self.settings.get(spec.key) or []
            self._card_widgets[spec.key] = [
                self._build_card(spec, stack, index, item, len(items))
                for index, item in enumerate(items)
            ]
            stack.add_button.setEnabled(len(items) < spec.max_items)
        finally:
            stack.setUpdatesEnabled(True)

    def _append_card(
        self, spec: Field, stack: RuleStack, item: dict, count: int
    ) -> None:
        widgets = self._build_card(spec, stack, count - 1, item, count)
        self._card_widgets.setdefault(spec.key, []).append(widgets)
        stack.add_button.setEnabled(count < spec.max_items)

    def _remove_card_at(self, spec: Field, stack: RuleStack, index: int) -> None:
        stack.remove_card(index)
        cards = self._card_widgets.get(spec.key) or []
        if 0 <= index < len(cards):
            cards.pop(index)
        stack.add_button.setEnabled(len(cards) < spec.max_items)

    @staticmethod
    def _card_sub_fields(spec: Field):
        for sub in spec.items:
            if sub.kind == "pair":
                yield from sub.items
            elif sub.kind != "note":
                yield sub

    def _sync_list_widgets(self, spec: Field) -> bool:
        """Write list-card values in place (no rebuild); False if it cannot."""
        stack = self._stacks.get(spec.key)
        cards = self._card_widgets.get(spec.key) or []
        items = self.settings.get(spec.key) or []
        if stack is None:
            return True
        if len(cards) != len(items):
            return False
        subs = list(self._card_sub_fields(spec))
        if any(sub.show_if is not None for sub in subs):
            return False
        try:
            for index, item in enumerate(items):
                widgets = cards[index]
                for sub in subs:
                    widget = widgets.get(sub.key)
                    if widget is None:
                        continue
                    value = item.get(sub.key, spec.item_default.get(sub.key))
                    self._write_widget(sub, widget, value)
        except RuntimeError:
            return False
        return True

    def _list_change(
        self,
        spec: Field,
        operation: str,
        index: int = 0,
        arg: Any = None,
        value: Any = None,
    ) -> None:
        items = copy.deepcopy(self.settings.get(spec.key) or [])
        merge = None
        verbs = {
            "add": "Added",
            "remove": "Removed",
            "move": "Moved",
            "edit": "Changed",
            "duplicate": "Duplicated",
        }
        if operation == "add":
            items.append(copy.deepcopy(dict(spec.item_default)))
            self._set_card_expanded(spec.key, len(items) - 1, True)
        elif operation == "duplicate" and 0 <= index < len(items):
            items.insert(index + 1, copy.deepcopy(items[index]))
            self._set_card_expanded(spec.key, index + 1, True)
        elif operation == "remove" and 0 <= index < len(items):
            del items[index]
            self._expanded_cards.setdefault(spec.key, {0}).discard(index)
        elif (
            operation == "move"
            and 0 <= index < len(items)
            and 0 <= index + arg < len(items)
        ):
            items[index], items[index + arg] = items[index + arg], items[index]
        elif operation == "edit" and index < len(items):
            items[index][arg.key] = value
            merge = self._burst_key(arg, f"{spec.key}{index}-")
        else:
            return
        structural = operation in ("add", "remove", "move", "duplicate") or (
            operation == "edit" and arg.rebuild_on_change
        )
        # Add and remove update the visible stack in place, so the pointer
        # never lands on a freshly rebuilt control. Reordering or reshaping a
        # card clears the projection and lets the undo command rebuild it.
        stack = self._stacks.get(spec.key)
        if stack is not None:
            if operation == "add":
                self._append_card(spec, stack, items[-1], len(items))
            elif operation == "remove":
                self._remove_card_at(spec, stack, index)
            elif structural:
                self._card_widgets.pop(spec.key, None)
        self.set_setting(
            spec.key,
            items,
            f"{self.HISTORY} {spec.label} {verbs[operation]}",
            merge,
            structural=structural,
        )
        if not structural and spec.summary is not None:
            stack = self._stacks.get(spec.key)
            if stack is not None and index < len(items):
                try:
                    stack.set_card_summary(index, spec.summary(items[index]))
                except Exception:  # noqa: BLE001, S110 - summary is advisory
                    pass

    # ---- undo projection -------------------------------------------------
    def _iter_fields(self, fields):
        for spec in fields:
            if spec.kind == "pair":
                yield from self._iter_fields(spec.items)
            else:
                yield spec

    def _all_fields(self):
        for section in self._sections():
            yield from self._iter_fields(section.fields)

    def _sync_widgets_from_model(self) -> None:
        for spec in self._all_fields():
            if spec.kind == "list":
                if not self._sync_list_widgets(spec):
                    stack = self._stacks.get(spec.key)
                    if stack is not None:
                        self._fill_stack(spec, stack)
                continue
            widget = self._widgets.get(spec.key)
            if widget is None or spec.kind == "note":
                continue
            try:
                self._write_widget(spec, widget)
            except RuntimeError:
                self._widgets.pop(spec.key, None)
        self._update_visibility()
        self.after_change()

    def _write_widget(self, spec: Field, widget: QWidget, value: Any = _UNSET) -> None:
        if value is _UNSET:
            value = self.settings.get(spec.key)
        widget.blockSignals(True)
        try:
            if spec.kind == "combo":
                self._set_combo(widget, value if value is not None else "")
            elif spec.kind in ("column", "picker", "columns"):
                items = self._column_items(spec)
                names = [name for name, _dtype in items]
                if widget.column_names() != names:
                    widget.setColumns(
                        items,
                        [value] if spec.kind == "column" and value else value or (),
                    )
                else:
                    widget.setChecked(
                        [value] if spec.kind == "column" and value else value or ()
                    )
            elif spec.kind == "segment":
                label = next(
                    (text for option, text in spec.options if option == value),
                    "",
                )
                if label:
                    widget.set_value(label)
            elif spec.kind == "weekdays":
                widget.set_value(value or ())
            elif spec.kind == "suffix":
                widget.set_value("" if value is None else str(value))
            elif spec.kind == "choices":
                widget.setChecked(value or ())
            elif spec.kind == "check":
                widget.setChecked(bool(value))
            elif spec.kind in ("int", "float"):
                widget.setValue(value if value is not None else spec.minimum)
            elif spec.kind == "textarea":
                text = "" if value is None else str(value)
                if widget.toPlainText() != text:
                    widget.setPlainText(text)
            elif spec.kind == "text":
                text = "" if value is None else str(value)
                if widget.text() != text:
                    widget.setText(text)
        finally:
            widget.blockSignals(False)

    def _rebuild_widgets(self) -> None:
        for spec in self._all_fields():
            if spec.kind != "list":
                continue
            stack = self._stacks.get(spec.key)
            if stack is None:
                continue
            cards = self._card_widgets.get(spec.key) or []
            items = self.settings.get(spec.key) or []
            if len(cards) == len(items):
                # In-place add/remove already projected the new structure.
                continue
            try:
                self._fill_stack(spec, stack)
            except RuntimeError:
                self._stacks.pop(spec.key, None)
        self._sync_widgets_from_model()

    def _update_visibility(self) -> None:
        for section in self._sections():
            for spec in section.fields:
                row = self._rows.get(spec.key)
                if row is None or spec.show_if is None:
                    continue
                try:
                    row.setVisible(bool(spec.show_if(self.settings)))
                except RuntimeError:
                    self._rows.pop(spec.key, None)

    def dock_context(self):
        return list(self.chips), ""

    def dock_summary(self) -> str:
        inputs = f"{self.INPUTS} input" + ("s" if self.INPUTS != 1 else "")
        count = len(self.OUTPUT_KINDS)
        outputs = f"{count} output" + ("s" if count != 1 else "")
        parts = [inputs, outputs]
        if self.SUMMARY:
            parts.append(self.SUMMARY)
        return " \u00b7 ".join(parts)

    # ---- persistence -----------------------------------------------------
    def serialize(self):
        return self.serialize_content_state(super().serialize())

    def deserialize(self, data, hashmap={}):  # noqa: B006
        res = super().deserialize(data, hashmap)
        try:
            self.deserialize_content_state(data)
            self.after_change()
            return True and res
        except Exception as exc:  # noqa: BLE001
            dumpException(exc)
        return res


class ShapingNode(TriggerNode):
    """Base node. Subclasses set the identity and ``content_class``."""

    content_class: type = ShapingContent
    output_text: tuple = ("",)
    style = {}  # noqa: RUF012

    @property
    def optional_inputs(self) -> frozenset:
        return self.content_class.OPTIONAL_INPUTS

    def __init__(self, scene) -> None:
        spec = self.content_class
        super().__init__(
            scene,
            inputs=[1] * spec.INPUTS,
            outputs=[3] * len(spec.OUTPUT_KINDS),
            output_text=list(self.output_text),
        )

    def initInnerClasses(self) -> None:
        self.content = self.content_class(self)
        self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values) -> list | None:
        content = self.content
        for index in range(content.INPUTS):
            upstream = socket = None
            try:
                upstream, socket = self.getInputWithSocket(index)
            except Exception:  # noqa: BLE001, S110 - unconnected input
                pass
            entry = None
            if upstream is not None and socket is not None and input_values[index]:
                entry = input_values[index][socket.index]
            if entry is None or entry.get("data") is None:
                content.frames[index] = None
                content.input_vars[index] = ""
                if index in content.OPTIONAL_INPUTS:
                    continue
                error = translate_exception(
                    ShapingError("TD-SHAPE-005", f"Input {index + 1} has no data"),
                    node=self,
                    phase="live",
                )
                self.set_error(error, "live")
                self.markDirty(True)
                self.markInvalid(True)
                return None
            # Live evaluation works on the leading rows; Run reads the whole input.
            content.frames[index] = live_sample(entry["data"])
            content.input_vars[index] = entry["variable_name"]
        try:
            outs = content.compute()
        except ShapingError as exc:
            self.set_error(translate_exception(exc, node=self, phase="live"), "live")
            self.markDirty(True)
            self.markInvalid(True)
            return None
        self.param = [
            {"data": live_sample(frame), "variable_name": name}
            for frame, name in zip(outs, content.output_variables)
        ]
        return self.param

    def get_code(self) -> str:
        return self.content.get_code()
