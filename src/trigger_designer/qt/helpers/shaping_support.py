"""Shared scaffolding for the shaping nodes (docs/plan/07-shaping-nodes.md)."""

from __future__ import annotations

import copy
import importlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import polars as pl
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException
from qtpy.QtCore import QTimer, Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.errors import translate_exception
from trigger_designer.core.shaping.common import ShapingError
from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerGraphicsNode,
    TriggerNode,
    frame_schema,
)
from trigger_designer.qt.undo.protocol import is_syncing
from trigger_designer.qt.widgets.common import (
    ColumnChecklist,
    ConfigSection,
    EmptyStateLabel,
    FormRow,
    NoWheelComboBox,
    RuleStack,
)


@dataclass(frozen=True)
class Field:
    """One dock control bound to ``settings[key]`` (or a key inside a list card)."""

    key: str
    label: str
    kind: str
    options: tuple = ()
    minimum: float = 0
    maximum: float = 1_000_000
    placeholder: str = ""
    tip: str = ""
    blank: bool = False
    input: int = 0
    filter: str = ""
    show_if: Callable[[dict], bool] | None = None
    items: tuple = ()
    item_default: dict = field(default_factory=dict)
    max_items: int = 50


def _passes(dtype: pl.DataType, kind: str) -> bool:
    if kind == "text":
        return dtype == pl.String
    if kind == "numeric":
        return dtype == pl.String or dtype.is_numeric()
    if kind == "date":
        return dtype == pl.String or dtype == pl.Date or isinstance(dtype, pl.Datetime)
    return True


class ShapingContent(
    QDMNodeIconContentWidget, TriggerChangeHandler, SerializableContentMixin
):
    evaluate = Signal()
    SETTINGS: dict = {}  # noqa: RUF012 - subclass defaults, never mutated
    MODULE = ""
    RUNNER = "run_node"
    OUTPUT_KINDS: tuple = ("out",)
    INPUTS = 1
    OPTIONAL_INPUTS: frozenset = frozenset()
    LIVE_CAP_ROWS = 0
    FORM: tuple = ()
    HISTORY = "Node"

    def get_serialized_state_schema(self) -> dict:
        return {"settings": {"default": copy.deepcopy(self.SETTINGS)}}

    def __init__(self, node: TriggerNode, parent: QWidget | None = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, node.scene, node)
        self.history = node.scene.history
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

    @property
    def node(self) -> TriggerNode:
        return self._node

    @node.setter
    def node(self, value: TriggerNode) -> None:
        self._node = value

    def initUI(self, _icon: QPixmap | None = None) -> None:
        super().initUI(self.node.rsm.get(f"{self.node.icon}"))

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

    def _rows_in(self) -> int:
        total = 0
        for frame in self.frames:
            if isinstance(frame, pl.LazyFrame):
                total += frame.select(pl.len()).collect().item()
            elif frame is not None:
                total += frame.height
        return total

    def compute(self) -> list:
        module = importlib.import_module(self.MODULE)
        settings = copy.deepcopy(self.settings)
        frames = list(self.frames)
        self.chips = []
        capped = bool(self.LIVE_CAP_ROWS) and self._rows_in() > self.LIVE_CAP_ROWS
        if capped:
            frames = [
                None
                if frame is None
                else pl.DataFrame(schema=frame_schema(frame)).lazy()
                for frame in frames
            ]
            self.chips = [
                (f"Over {self.LIVE_CAP_ROWS:,} rows: full result at Run", "warning")
            ]
        runner = getattr(module, self.RUNNER)
        outs = runner(frames, settings)
        self.outputs = [
            out.lazy() if isinstance(out, pl.DataFrame) else out for out in outs
        ]
        describe = getattr(module, "describe", None)
        if describe is not None and not capped:
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
        payload = json.dumps(self.settings, sort_keys=True)
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
    ) -> None:
        if is_syncing(self) or self.history.is_restoring_history:
            return
        old = self.settings.get(key)
        if value == old:
            return
        self.settings[key] = copy.deepcopy(value)
        self._update_visibility()
        self.after_change()
        self.refresh_dock_context()
        self.evaluate.emit()
        push = (
            self.push_list_change
            if isinstance(value, list)
            else self.push_property_change
        )
        push(
            ("settings", key),
            copy.deepcopy(old),
            copy.deepcopy(value),
            text,
            merge_key=merge_key,
        )

    def after_change(self) -> None:
        """Hook after every model change."""

    # ---- dock ------------------------------------------------------------
    def ready(self) -> bool:
        return all(
            self.frames[i] is not None
            for i in range(self.INPUTS)
            if i not in self.OPTIONAL_INPUTS
        )

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if not self.ready():
            dock_layout.addWidget(EmptyStateLabel())
            return
        self._widgets, self._rows, self._stacks = {}, {}, {}
        for title, fields in self.FORM:
            section = ConfigSection(title)
            section._undo_composite = True
            for spec in fields:
                row = (
                    self._build_list(spec)
                    if spec.kind == "list"
                    else self._build_row(spec)
                )
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
        return FormRow(spec.label, widget, label_width=96)

    def _make_widget(self, spec: Field, value: Any, commit: Callable) -> QWidget:
        if spec.kind in ("combo", "column"):
            widget = NoWheelComboBox()
            widget.setMinimumHeight(30)
            if spec.kind == "column":
                if spec.blank:
                    widget.addItem("(none)", "")
                for name in self.names(spec):
                    widget.addItem(name, name)
            else:
                for item_value, label in spec.options:
                    widget.addItem(label, item_value)
            self._set_combo(widget, value if value is not None else "")
            widget.currentIndexChanged.connect(
                lambda _index, w=widget: commit(w.currentData())
            )
            return widget
        if spec.kind in ("columns", "choices"):
            if spec.kind == "columns":
                options = self.names(spec)
            else:
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
        timer.timeout.connect(fire)
        signal.connect(lambda *_args, t=timer: t.start())
        self._timers.append(timer)

    def flush_pending(self) -> None:
        for timer in list(self._timers):
            try:
                if timer.isActive():
                    timer.stop()
                    timer.timeout.emit()
            except RuntimeError:
                continue

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
        self._stacks[spec.key] = stack
        self._fill_stack(spec, stack)
        return stack

    def _fill_stack(self, spec: Field, stack: RuleStack) -> None:
        stack.clear()
        items = self.settings.get(spec.key) or []
        for index, item in enumerate(items):
            body = QWidget()
            layout = QVBoxLayout(body)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            for sub in spec.items:
                value = item.get(sub.key, spec.item_default.get(sub.key))

                def commit(new_value, f=spec, i=index, s=sub):
                    self._list_change(f, "edit", i, s, new_value)

                widget = self._make_widget(sub, value, commit)
                layout.addWidget(FormRow(sub.label, widget, label_width=84))
            stack.add_card(index, len(items), body)
        stack.add_button.setEnabled(len(items) < spec.max_items)

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
        }
        if operation == "add":
            items.append(copy.deepcopy(dict(spec.item_default)))
        elif operation == "remove" and 0 <= index < len(items):
            del items[index]
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
        self.set_setting(
            spec.key,
            items,
            f"{self.HISTORY} {spec.label} {verbs[operation]}",
            merge,
        )
        if operation != "edit":
            self._fill_stack(spec, self._stacks[spec.key])

    # ---- undo projection -------------------------------------------------
    def _all_fields(self):
        for _title, fields in self.FORM:
            yield from fields

    def _sync_widgets_from_model(self) -> None:
        for spec in self._all_fields():
            widget = self._widgets.get(spec.key)
            if widget is None or spec.kind == "list":
                continue
            try:
                self._write_widget(spec, widget)
            except RuntimeError:
                self._widgets.pop(spec.key, None)
        self._update_visibility()
        self.after_change()

    def _write_widget(self, spec: Field, widget: QWidget) -> None:
        value = self.settings.get(spec.key)
        widget.blockSignals(True)
        try:
            if spec.kind in ("combo", "column"):
                self._set_combo(widget, value if value is not None else "")
            elif spec.kind in ("columns", "choices"):
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
            try:
                self._fill_stack(spec, stack)
            except RuntimeError:
                self._stacks.pop(spec.key, None)
        self._sync_widgets_from_model()

    def _update_visibility(self) -> None:
        for spec in self._all_fields():
            row = self._rows.get(spec.key)
            if row is None or spec.show_if is None:
                continue
            try:
                row.setVisible(bool(spec.show_if(self.settings)))
            except RuntimeError:
                self._rows.pop(spec.key, None)

    def dock_context(self):
        return list(self.chips), ""

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
            content.frames[index] = entry["data"]
            content.input_vars[index] = entry["variable_name"]
        try:
            outs = content.compute()
        except ShapingError as exc:
            self.set_error(translate_exception(exc, node=self, phase="live"), "live")
            self.markDirty(True)
            self.markInvalid(True)
            return None
        self.param = [
            {"data": frame, "variable_name": name}
            for frame, name in zip(outs, content.output_variables)
        ]
        return self.param

    def get_code(self) -> str:
        return self.content.get_code()
