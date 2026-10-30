"""Shared base for the Audit nodes (docs/plan/04-audit-test-nodes.md section 3.8-3.9).

Each audit test is one Qt-free function ``run_<name>(frame, params) -> AuditResult``
in ``core/audit/``. A node file therefore only declares its settings class, its
sockets and its dock; everything repeated lives here:

* the settings model (``params()``, ``serialize``/``deserialize``),
* ``set_setting`` - the one place a user edit enters the model and the undo stack,
* ``bind`` / ``add_*`` - dock controls wired to a setting, projected back by
  ``_sync_widgets_from_model`` on undo/redo,
* live evaluation (``AuditNode.processInputs``) and Run codegen (``get_code``),
  both calling the same ``run_*`` function,
* the ``TestSummary`` (``after_execution`` on Run, the Count button live) and the
  small Result section that shows it.

This module is a lazy helper (``_LAZY_HELPER_MODULES``): it is imported by the
node modules, never by the startup sweep.
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Callable, Iterable
from typing import Any

import polars as pl
from nodeeditor.utils_no_qt import dumpException
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.audit.common import (
    AuditConfigError,
    AuditResult,
    ParamsBase,
    as_lazy,
    default_of,
    params_schema,
    parse_number_list,
    parse_size_list,
)
from trigger_designer.core.audit.test_summary import TestSummary
from trigger_designer.core.codegen_safe import ident_part
from trigger_designer.core.errors import translate_exception
from trigger_designer.core.frames import frame_schema
from trigger_designer.qt.helpers.config_content import ConfigContent
from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from trigger_designer.qt.node_base import TriggerGraphicsNode, TriggerNode
from trigger_designer.qt.undo.binding import DEFAULT_DEBOUNCE_MS
from trigger_designer.qt.undo.protocol import is_syncing
from trigger_designer.qt.widgets.common import (
    CONTROL_H,
    ColumnChecklist,
    ColumnPicker,
    ConfigSection,
    EmptyStateLabel,
    IconButton,
    NoWheelComboBox,
    SegmentedControl,
    dtype_label,
)

__all__ = [
    "COUNT_TOOLTIP",
    "AuditContent",
    "AuditContentMixin",
    "AuditNode",
]

#: Tooltip and accessible name of the dock's "count exceptions" icon button.
COUNT_TOOLTIP = "Count exceptions now"

#: Kinds of control ``bind`` understands, and the signal each one is read from.
_DEBOUNCED_KINDS = frozenset({"text", "lines", "numlist", "sizelist"})


def _signal_of(widget: QWidget, kind: str):
    """The signal that says "the user changed this control"."""
    if kind in ("picker", "columns", "segment", "checklist", "digitlist"):
        return widget.changed
    if kind == "check":
        return widget.toggled
    if kind in ("spin", "optint", "dspin"):
        return widget.valueChanged
    if kind == "combo":
        return widget.currentIndexChanged
    return widget.textChanged  # text, lines, numlist, sizelist


class AuditContentMixin(SerializableContentMixin):
    """Settings model, undo wiring, codegen and summary for one audit test.

    Put it **before** ``ConfigContent`` in the bases (``AuditContent`` does) so
    its ``_sync_widgets_from_model`` wins over the undo mixin's no-op.
    """

    #: Settings dataclass (a ``ParamsBase``). Its field names become content
    #: attributes and persisted keys; never rename one, only add.
    PARAMS: type[ParamsBase]
    #: The pure run function ``run_x(frame, params) -> AuditResult``. Wrap it in
    #: ``staticmethod`` so it is not bound as a method.
    RUN: Callable[..., AuditResult]
    #: Stable op id, e.g. ``"audit.duplicates"``; also the undo merge-key prefix.
    OP: str = ""
    #: ``Summary.test_name`` family and the dock's context chip.
    TEST_NAME: str = ""
    #: Socket-ordered output kinds; variable ``var_<kind>_<id>`` per socket.
    OUTPUT_KINDS: tuple[str, ...] = ()
    #: Socket holding the one-row Summary (Sample: the Selection log), or None.
    SUMMARY_INDEX: int | None = None
    #: Socket holding the exception rows (``TestSummary.exceptions_var``), or None.
    EXCEPTIONS_INDEX: int | None = None
    #: True when ``on_result`` should fill ``test_summary`` from every live
    #: evaluation (Benford and Sample: their summary is cheap and eager).
    LIVE_SUMMARY: bool = False
    #: Undo history label of a setting without its own text (``"Noun Verbed"``).
    HISTORY: str = "Audit Setting Changed"

    # ---- schema (derived, so a node never repeats its field list) --------
    def get_serialized_state_schema(self) -> dict:
        return params_schema(self.PARAMS)

    # ---- model -----------------------------------------------------------
    def init_audit_state(self) -> None:
        """Call once from ``__init__`` after ``ConfigContent.__init__``."""
        taken = [
            f.name
            for f in dataclasses.fields(self.PARAMS)
            if hasattr(type(self), f.name)
        ]
        if taken:
            raise TypeError(
                f"{self.PARAMS.__name__} fields {taken} shadow attributes of "
                f"{type(self).__name__}; rename the field(s)"
            )
        for f in dataclasses.fields(self.PARAMS):
            setattr(self, f.name, copy.deepcopy(default_of(f)))
        self.incoming_variable: str = ""
        self.incom_data: Any = None  # LazyFrame (or DataFrame) of the input
        self.test_summary: TestSummary | None = None
        self.last_result: AuditResult | None = None  # last live evaluation
        self.output_variables: list[str] = [
            f"var_{kind}_{self.id}" for kind in self.OUTPUT_KINDS
        ]
        # Names the Run pruning step looks for (variable_name / out<i>_variable_name).
        for i, name in enumerate(self.output_variables):
            setattr(self, "variable_name" if i == 0 else f"out{i}_variable_name", name)
        self.summary_variable_name: str = (
            self.output_variables[self.SUMMARY_INDEX]
            if self.SUMMARY_INDEX is not None
            else ""
        )
        self._bindings: dict[str, tuple[QWidget, str, dict]] = {}
        self._timers: dict[str, QTimer] = {}
        self._commits: dict[str, Callable[[], None]] = {}
        self.summary_label: QLabel | None = None
        self.count_button: IconButton | None = None

    def params(self) -> ParamsBase:
        """A snapshot of the settings as the run function's dataclass."""
        return self.PARAMS(
            **{
                f.name: copy.deepcopy(getattr(self, f.name))
                for f in dataclasses.fields(self.PARAMS)
            }
        )

    def params_dict(self) -> dict:
        return self.params().to_dict()

    def schema(self) -> dict:
        """``{column: dtype}`` of the input; never collects."""
        return frame_schema(self.incom_data)

    def output_variable_names(self) -> list[str]:
        return list(self.output_variables)

    def exceptions_var_name(self) -> str | None:
        if self.EXCEPTIONS_INDEX is None:
            return None
        return self.output_variables[self.EXCEPTIONS_INDEX]

    def build_result(self) -> AuditResult:
        """Run the pure test on the live input. Override only if a node must."""
        return self.RUN(self.incom_data, self.params())

    def on_result(self, result: AuditResult) -> None:
        """Called after every successful live evaluation."""
        if self.LIVE_SUMMARY:
            self.collect_test_summary(result)

    # ---- the one place a user edit enters the model ----------------------
    def set_setting(
        self,
        name: str,
        value: Any,
        text: str | None = None,
        *,
        merge_key: str | None = None,
        structural: bool = False,
        evaluate: bool = True,
    ) -> bool:
        """Store a setting, re-evaluate, and record one undo step.

        Returns False (and does nothing) for a write-back from the model, for a
        restore, and when the value did not really change.
        """
        if is_syncing(self) or self.history.is_restoring_history:
            return False
        old = copy.deepcopy(getattr(self, name))
        new = copy.deepcopy(value)
        if new == old:
            return False
        setattr(self, name, new)  # 1. model first
        self.test_summary = None  # a result of the old settings is stale
        self._mark_scene_modified()
        self._apply_visibility()
        self._show_summary()
        self.refresh_dock_context()
        if evaluate:
            self.evaluate.emit()  # 2. re-evaluate the graph
        push = (
            self.push_list_change
            if structural and isinstance(new, list)
            else self.push_property_change
        )
        # The command's redo re-projects widgets and would evaluate a second
        # time; the emit above already ran the node on the new model.
        previous = getattr(self, "_suspend_node_evaluation", False)
        self._suspend_node_evaluation = True
        try:
            push(  # 3. one undo step
                (name,), old, new, text or self.HISTORY, merge_key=merge_key
            )
        finally:
            self._suspend_node_evaluation = previous
        return True

    def _mark_scene_modified(self) -> None:
        scene = getattr(self.node, "scene", None)
        if scene is not None:
            scene.has_been_modified = True

    # ---- widget binding ---------------------------------------------------
    def column_items(self, extra: Iterable[str] = ()) -> list[tuple[str, str]]:
        """``(name, dtype label)`` for every input column.

        ``extra`` names (a saved column the input no longer has) are appended as
        ``missing`` so the picker still shows what is chosen and the error says
        why it cannot run.
        """
        items = [(name, dtype_label(dtype)) for name, dtype in self.schema().items()]
        known = {name for name, _ in items}
        for name in extra:
            if name and name not in known:
                items.append((name, "missing"))
                known.add(name)
        return items

    def section(self, title: str = "", **kwargs: Any) -> ConfigSection:
        """A dock section that owns its controls' undo (the sweep skips them)."""
        section = ConfigSection(title, **kwargs)
        section._undo_composite = True
        return section

    def bind(
        self,
        name: str,
        widget: QWidget,
        kind: str,
        text: str | None = None,
        *,
        burst: bool = False,
        options: tuple = (),
    ) -> QWidget:
        """Wire ``widget`` to the setting ``name``.

        ``kind`` is one of ``picker`` (single column, ``str``), ``columns``
        (``list[str]``), ``check``, ``spin`` (``int``), ``optint`` (``int`` or
        ``None`` at the spin's minimum), ``dspin`` (``float``), ``segment``
        (``options`` is ``((key, label), ...)``), ``combo`` (item data),
        ``checklist`` (``ColumnChecklist``, ``list[str]``), ``digitlist``
        (``ColumnChecklist`` of digits, ``list[int]``), ``text``, ``lines``,
        ``numlist`` and ``sizelist``. ``burst=True`` folds a run of edits (typing,
        spinning) into one undo step; text-like kinds commit after the 300 ms
        debounce. Returns ``widget``.
        """
        opts = {"options": tuple(options)}
        self._bindings[name] = (widget, kind, opts)
        merge = f"{self.OP}-{name}" if burst else None
        debounced = kind in _DEBOUNCED_KINDS

        def commit() -> None:
            try:
                value = self._read_widget(widget, kind, opts)
            except ValueError:  # half-typed list: keep the previous value
                return
            except RuntimeError:  # widget deleted by a dock rebuild
                return
            self.set_setting(name, value, text, merge_key=merge)

        self._commits[name] = commit

        def on_change(*_args: Any) -> None:
            if not debounced:
                commit()
                return
            timer = self._timers.get(name)
            if timer is None:
                timer = QTimer(widget)
                timer.setSingleShot(True)
                timer.setInterval(DEFAULT_DEBOUNCE_MS)
                timer.timeout.connect(commit)
                self._timers[name] = timer
            timer.start()

        _signal_of(widget, kind).connect(on_change)
        return widget

    def _read_widget(self, w: QWidget, kind: str, opts: dict) -> Any:
        if kind == "picker":
            checked = w.checked()
            return checked[0] if checked else ""
        if kind in ("columns", "checklist"):
            return list(w.checked())
        if kind == "check":
            return w.isChecked()
        if kind == "spin":
            return int(w.value())
        if kind == "dspin":
            return float(w.value())
        if kind == "optint":
            return None if w.value() == w.minimum() else int(w.value())
        if kind == "segment":
            label = w.value()
            return next((k for k, lab in opts["options"] if lab == label), label)
        if kind == "combo":
            return w.currentData()
        if kind == "digitlist":
            return [int(x) for x in w.checked()]
        if kind == "text":
            return w.text().strip()
        if kind == "lines":
            return [s.strip() for s in w.toPlainText().splitlines() if s.strip()]
        if kind == "numlist":
            return parse_number_list(w.text())
        if kind == "sizelist":
            return parse_size_list(w.text())
        raise ValueError(f"unknown control kind {kind!r}")

    def _write_widget(self, w: QWidget, kind: str, opts: dict, value: Any) -> None:
        """Project a model value onto a control without emitting its signal."""
        blocked = w.blockSignals(True)
        try:
            if kind in ("picker", "columns"):
                names = [value] if kind == "picker" and value else list(value or [])
                if any(n not in w.column_names() for n in names):
                    w.setColumns(self.column_items(names), names)
                else:
                    w.setChecked(names)
            elif kind == "check":
                w.setChecked(bool(value))
            elif kind == "spin":
                w.setValue(int(value))
            elif kind == "dspin":
                w.setValue(float(value))
            elif kind == "optint":
                w.setValue(w.minimum() if value is None else int(value))
            elif kind == "segment":
                w.set_value(
                    next((lab for k, lab in opts["options"] if k == value), value)
                )
            elif kind == "combo":
                index = w.findData(value)
                if index < 0:
                    w.addItem(f"{value} (missing)", value)
                    index = w.count() - 1
                w.setCurrentIndex(index)
            elif kind == "checklist":
                w.setChecked(list(value))
            elif kind == "digitlist":
                w.setChecked([str(v) for v in value])
            elif kind == "text":
                w.setText(value or "")
            elif kind == "lines":
                w.setPlainText("\n".join(value or []))
            elif kind == "numlist":
                w.setText(", ".join(f"{x:g}" for x in value))
            elif kind == "sizelist":
                w.setText(", ".join("all" if x < 0 else str(x) for x in value))
        finally:
            w.blockSignals(blocked)

    # ---- ready-made controls (each is bound; wrap in a FormRow) -----------
    def add_picker(
        self,
        name: str,
        label: str,
        text: str,
        *,
        single: bool = True,
        blank: bool = False,
        placeholder: str = "",
    ) -> ColumnPicker:
        """A ``ColumnPicker`` bound to a column setting (``str`` or ``list[str]``)."""
        value = getattr(self, name)
        names = [value] if single and value else list(value or [])
        picker = ColumnPicker(
            self.column_items(names),
            names,
            placeholder or ("Choose column..." if single else "Choose columns..."),
            single=single,
            allow_blank=blank,
            rsm=self.node.rsm,
            label=label,
        )
        self.bind(name, picker, "picker" if single else "columns", text)
        return picker

    def add_segment(
        self, name: str, options: tuple, text: str, *, compact: bool = False
    ) -> SegmentedControl:
        """A ``SegmentedControl`` over ``((key, label), ...)`` bound to ``name``."""
        labels = [label for _key, label in options]
        current = next(
            (lab for key, lab in options if key == getattr(self, name)), labels[0]
        )
        control = SegmentedControl(labels, current, expanded=True, compact=compact)
        self.bind(name, control, "segment", text, options=options)
        return control  # type: ignore[return-value]

    def add_check(self, name: str, label: str, text: str) -> QCheckBox:
        box = QCheckBox(label)
        box.setChecked(bool(getattr(self, name)))
        self.bind(name, box, "check", text)
        return box

    def add_spin(
        self,
        name: str,
        text: str,
        *,
        minimum: int = 0,
        maximum: int = 1_000_000_000,
        optional: str = "",
    ) -> QSpinBox:
        """An int spin; ``optional`` is the label shown at ``minimum`` (value None)."""
        spin = QSpinBox()
        spin.setMinimumHeight(CONTROL_H)
        spin.setRange(minimum, maximum)
        if optional:
            spin.setSpecialValueText(optional)
        value = getattr(self, name)
        spin.setValue(minimum if value is None else int(value))
        self.bind(name, spin, "optint" if optional else "spin", text, burst=True)
        return spin

    def add_dspin(
        self,
        name: str,
        text: str,
        *,
        minimum: float = 0.0,
        maximum: float = 1e12,
        decimals: int = 2,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setMinimumHeight(CONTROL_H)
        spin.setDecimals(decimals)
        spin.setRange(minimum, maximum)
        spin.setValue(float(getattr(self, name)))
        self.bind(name, spin, "dspin", text, burst=True)
        return spin

    def add_combo(
        self, name: str, options: tuple, text: str, *, tip: str = ""
    ) -> NoWheelComboBox:
        """A ``NoWheelComboBox`` over ``((value, label), ...)`` bound to ``name``."""
        combo = NoWheelComboBox()
        combo.setMinimumHeight(CONTROL_H)
        for value, label in options:
            combo.addItem(label, value)
        if tip:
            combo.setToolTip(tip)
        self._write_widget(combo, "combo", {}, getattr(self, name))
        self.bind(name, combo, "combo", text)
        return combo

    def add_text(
        self, name: str, text: str, *, placeholder: str = "", kind: str = "text"
    ) -> QLineEdit:
        """A line edit; ``kind`` is ``text``, ``numlist`` or ``sizelist``."""
        edit = QLineEdit()
        edit.setMinimumHeight(CONTROL_H)
        edit.setClearButtonEnabled(True)
        if placeholder:
            edit.setPlaceholderText(placeholder)
        self._write_widget(edit, kind, {}, getattr(self, name))
        self.bind(name, edit, kind, text, burst=True)
        return edit

    def add_lines(
        self, name: str, text: str, *, placeholder: str = ""
    ) -> QPlainTextEdit:
        """A multi-line list (one item per line) bound to a ``list[str]`` setting."""
        edit = QPlainTextEdit()
        edit.setMinimumHeight(90)
        if placeholder:
            edit.setPlaceholderText(placeholder)
        self._write_widget(edit, "lines", {}, getattr(self, name))
        self.bind(name, edit, "lines", text, burst=True)
        return edit

    def add_digits(
        self, name: str, text: str, digits: Iterable[int]
    ) -> ColumnChecklist:
        """A checklist of digits bound to a ``list[int]`` setting."""
        checklist = ColumnChecklist(
            [str(d) for d in digits], [str(v) for v in getattr(self, name)]
        )
        self.bind(name, checklist, "digitlist", text)
        return checklist

    # ---- undo projection (runs inside syncing(); brief 6.3) ---------------
    def _sync_widgets_from_model(self) -> None:
        for name, (w, kind, opts) in list(self._bindings.items()):
            if self._edit_pending(name):
                continue  # the user is still typing here: keep their text
            try:
                if self._read_widget(w, kind, opts) != getattr(self, name):
                    self._write_widget(w, kind, opts, getattr(self, name))
            except RuntimeError, ValueError:
                # Widget deleted by a dock rebuild, or half-typed text: the
                # latter is rewritten from the model below.
                try:
                    self._write_widget(w, kind, opts, getattr(self, name))
                except RuntimeError:
                    self._bindings.pop(name, None)
        self._apply_visibility()
        self._show_summary()

    def _edit_pending(self, name: str) -> bool:
        """True while a debounced edit of setting ``name`` has not committed yet."""
        timer = self._timers.get(name)
        try:
            return timer is not None and timer.isActive()
        except RuntimeError:  # dock rebuilt: the timer died with its widget
            return False

    def _apply_visibility(self) -> None:
        """Override: show or hide option rows for the current mode."""

    def commit_pending_dock_edits(self, *, evaluate: bool = True) -> None:
        """Apply a text edit still inside its debounce (called when the dock closes)."""
        for name, timer in list(self._timers.items()):
            try:
                if not timer.isActive():
                    continue
                timer.stop()
            except RuntimeError:
                continue
            commit = self._commits.get(name)
            if commit is not None:
                commit()

    # ---- dock skeleton ----------------------------------------------------
    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        self._bindings.clear()
        self._commits.clear()
        self._timers.clear()
        self.summary_label = None
        self.count_button = None
        if self.incom_data is None:
            dock_layout.addWidget(EmptyStateLabel())
            return
        self.build_dock(dock_layout)
        self._apply_visibility()
        self._show_summary()

    def build_dock(self, dock_layout: QVBoxLayout) -> None:
        """Override: add the node's sections, then ``dock_layout.addStretch()``."""
        raise NotImplementedError

    def dock_context(self):
        return [(self.TEST_NAME, "accent")], ""

    def dock_summary(self) -> str:
        return self.TEST_NAME

    # ---- summary / Count --------------------------------------------------
    def result_section(self, *, count_button: bool = True) -> ConfigSection:
        """The "Result" section: the last outcome sentence and the Count button.

        Pass ``count_button=False`` for a node whose summary is already live.
        """
        section = self.section("Result")
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        label = QLabel("")
        label.setObjectName("FieldHint")
        label.setWordWrap(True)
        self.summary_label = label
        layout.addWidget(label, 1)
        if count_button:
            button = IconButton.themed(
                COUNT_TOOLTIP, rsm_icon=self.node.rsm.get("icon_refresh")
            )
            button.clicked.connect(self.count_exceptions)
            self.count_button = button
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)
        section.addWidget(row)
        return section

    def summary_text(self) -> str:
        summary = self.test_summary
        if summary is None:
            if self.count_button is not None:
                return "Not counted yet. Use the refresh button to count."
            return ""
        return f"{summary.status.upper()}: {summary.message}"

    def _show_summary(self) -> None:
        label = self.summary_label
        if label is None:
            return
        try:
            label.setText(self.summary_text())
        except RuntimeError:  # dock rebuilt
            self.summary_label = None

    def collect_test_summary(self, result: AuditResult | None = None) -> bool:
        """Build ``test_summary`` from the Summary frame of ``result``.

        Collects the one-row summary on the calling (GUI) thread with the
        streaming engine. Returns False when there is nothing to count.
        """
        result = result or self.last_result
        if result is None or self.SUMMARY_INDEX is None:
            return False
        frame = result.frames[self.SUMMARY_INDEX]
        if isinstance(frame, pl.LazyFrame):
            frame = frame.collect(engine="streaming")
        if not isinstance(frame, pl.DataFrame) or frame.height != 1:
            return False
        self.test_summary = TestSummary.from_summary_frame(
            frame,
            op=self.OP,
            node_id=getattr(self.node, "id", None),
            exceptions_var=self.exceptions_var_name(),
        )
        return True

    def count_exceptions(self) -> None:
        """Count button: summarise the last live result. Never touches the undo stack."""
        try:
            self.collect_test_summary()
        except Exception as exc:  # noqa: BLE001 - show the reason, keep the app up
            self.test_summary = None
            if self.summary_label is not None:
                self.summary_label.setText(f"Could not count: {exc}")
            return
        self._show_summary()

    # ---- run hooks --------------------------------------------------------
    def after_execution(self, variables: dict) -> None:
        """Executor worker thread, after a successful Run: pure Python only."""
        frame = variables.get(self.summary_variable_name)
        if isinstance(frame, pl.LazyFrame):
            frame = frame.collect()
        if isinstance(frame, pl.DataFrame) and frame.height == 1:
            self.test_summary = TestSummary.from_summary_frame(
                frame,
                op=self.OP,
                node_id=getattr(self.node, "id", None),
                exceptions_var=self.exceptions_var_name(),
            )

    def on_run_result(self, variables: dict) -> None:
        """GUI thread after a Run: refresh the Result text."""
        del variables
        self._show_summary()

    # ---- codegen ------------------------------------------------------------
    def audit_code(
        self, module: str, run_fn: str, params_cls: str, out_vars: list[str]
    ) -> str:
        """The generated snippet: build the params, call ``run_fn``, bind the outputs.

        ``module`` is the full dotted module of ``run_fn`` and ``params_cls``.
        Unwired, every output is defined as an empty frame so downstream code
        never raises ``NameError``; wired but misconfigured, the call raises
        ``AuditConfigError`` and the node fails loudly (an audit test must not
        silently produce nothing, which would read as "no exceptions").
        """
        if not self.incoming_variable:
            return "import polars as pl\n" + "".join(
                f"{v} = pl.DataFrame()\n" for v in out_vars
            )
        uid = ident_part(self.id)
        return (
            "import polars as pl\n"
            f"from {module} import {params_cls}, {run_fn}\n"
            f"_ap_{uid} = {params_cls}.from_dict({self.params_dict()!r})\n"
            f"{', '.join(out_vars)} = {run_fn}({self.incoming_variable}, _ap_{uid}).for_run()\n"
            f"del _ap_{uid}\n"
        )

    def get_code(self) -> str:
        run = type(self).RUN
        return self.audit_code(
            run.__module__,
            run.__name__,
            self.PARAMS.__name__,
            self.output_variable_names(),
        )

    # ---- persistence ---------------------------------------------------------
    def serialize(self):
        return self.serialize_content_state(super().serialize())

    def deserialize(self, data, hashmap={}):  # noqa: B006
        res = super().deserialize(data, hashmap)
        try:
            self.deserialize_content_state(data)
            self.test_summary = None
            return True and res
        except Exception as exc:  # noqa: BLE001
            dumpException(exc)
        return res


class AuditContent(AuditContentMixin, ConfigContent):
    """Concrete base for a node's content: declare the class attributes, a dock.

    ``evaluate`` (the Signal), the ``node`` property pair, ``initUI`` and
    ``history`` come from ``ConfigContent``.
    """

    def __init__(self, node: TriggerNode, parent: QWidget | None = None) -> None:
        super().__init__(node, parent)
        self.init_audit_state()


class AuditNode(TriggerNode):
    """Single-input audit test node.

    A subclass sets ``icon``, ``node_code``, ``node_type``, ``node_title``,
    ``content_class``, ``OUTPUT_TYPES`` (socket colour per output: ``3`` data,
    ``1`` summary/log) and ``output_text`` (one letter per output).
    """

    content_class: type[AuditContentMixin] = AuditContent
    OUTPUT_TYPES: tuple[int, ...] = (3,)
    output_text: tuple[str, ...] = ("",)
    style = {}  # noqa: RUF012 - shared empty node style

    def __init__(self, scene) -> None:
        super().__init__(
            scene,
            inputs=[1],
            outputs=list(self.OUTPUT_TYPES),
            output_text=list(self.output_text),
        )

    def initInnerClasses(self) -> None:
        self.content = self.content_class(self)
        self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def _fail(self, exc: BaseException) -> None:
        self.set_error(translate_exception(exc, node=self, phase="live"), "live")
        self.markDirty(True)
        self.markInvalid(True)

    def processInputs(self, input_values) -> list | None:
        content = self.content
        entry = None
        try:
            upstream, socket = self.getInputWithSocket(0)
            if upstream is not None and socket is not None and input_values[0]:
                entry = input_values[0][socket.index]
        except Exception:  # noqa: BLE001, S110 - unconnected input
            pass
        if not entry or entry.get("data") is None:
            content.incom_data = None
            content.incoming_variable = ""
            self.markDirty(True)
            self.markInvalid(True)
            self._set_node_tooltip("Input has no data")
            return None
        # Set BEFORE validating so the dock can still list the columns.
        content.incom_data = as_lazy(entry["data"])
        content.incoming_variable = entry["variable_name"]
        try:
            result = content.build_result()
        except AuditConfigError as exc:
            content.last_result = None
            self._fail(exc)
            return None
        content.last_result = result
        content.on_result(result)
        self.param = [
            {"data": frame, "variable_name": name}
            for frame, name in zip(result.frames, content.output_variable_names())
        ]
        return self.param

    def get_code(self) -> str:
        return self.content.get_code()
