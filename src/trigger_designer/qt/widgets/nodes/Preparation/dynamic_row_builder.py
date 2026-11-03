"""Rows node: Qt wrapper only; the logic is core/shaping/rows.py."""

from __future__ import annotations

from datetime import datetime

from qtpy.QtCore import QDateTime
from qtpy.QtWidgets import (
    QDateTimeEdit,
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import rows as core
from trigger_designer.qt.helpers.shaping_support import ShapingContent, ShapingNode
from trigger_designer.qt.widgets.common import (
    ConfigSection,
    FormRow,
    NoWheelComboBox,
)

_TYPE_ITEMS = (
    ("int", "Int"),
    ("float", "Float"),
    ("string", "Text"),
    ("datetime", "Date/time"),
)

_VALUE_LABELS = (
    ("initial_value", "Start"),
    ("increment_value", "Increment"),
    ("max_value", "End"),
)

_INT_DEFAULT = {"initial_value": 1, "increment_value": 1, "max_value": 10}
_FLOAT_DEFAULT = {"initial_value": 1.0, "increment_value": 1.0, "max_value": 10.0}
_STRING_DEFAULT = {"initial_value": "A", "increment_value": "1", "max_value": "Z"}
_DATETIME_DEFAULT = {
    "initial_value": "2024-01-01T00:00:00",
    "increment_value": 3600,
    "max_value": "2024-01-02T00:00:00",
}
#: Settings store naive ISO strings; the editor mirrors that.
_DEFAULT_DATETIME = datetime(2024, 1, 1)  # noqa: DTZ001


def _parse_iso(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except TypeError, ValueError:
        return None


class RowsContent(ShapingContent):
    """Generate a typed column and concatenate it to the input."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.rows"
    OUTPUT_KINDS = ("rows",)
    INPUTS = 1
    HISTORY = "Rows"
    SUMMARY = "generated rows"

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        # Keep the generated variable name the old node used.
        self.output_variables = [f"var_genrows_{self.id}"]
        self.variable_name = self.output_variables[0]
        self._widget_type: str | None = None
        self._value_widgets: dict = {}
        self._value_rows: dict = {}

    # -- dock construction ----------------------------------------------
    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        field_type = str(self.settings.get("field_type") or "int")

        field_section = ConfigSection()
        field_section._undo_composite = True
        self.field_section = field_section

        self.name_edit = QLineEdit()
        self.name_edit.setMinimumHeight(30)
        self.name_edit.setToolTip("Name of the generated column")
        self.name_edit.setText(str(self.settings.get("field_name") or ""))
        self._debounced(
            self.name_edit.textChanged,
            lambda: self.set_setting(
                "field_name",
                self.name_edit.text(),
                "Rows Field name Changed",
                "Rows-field_name",
            ),
        )
        field_section.addWidget(FormRow("Name", self.name_edit, label_width=88))

        self.type_combo = NoWheelComboBox()
        self.type_combo.setMinimumHeight(30)
        for value, label in _TYPE_ITEMS:
            self.type_combo.addItem(label, value)
        index = self.type_combo.findData(field_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        self.type_combo.currentIndexChanged.connect(
            lambda _index: self._commit_type(self.type_combo.currentData() or "int")
        )
        field_section.addWidget(FormRow("Type", self.type_combo, label_width=88))

        value_section = ConfigSection()
        value_section._undo_composite = True
        self.value_section = value_section
        self._value_widgets = {}
        self._value_rows = {}
        for key, label in _VALUE_LABELS:
            widget = self._make_value_widget(key, field_type)
            row = FormRow(label, widget, label_width=88)
            self._value_rows[key] = row
            self._value_widgets[key] = widget
            value_section.addWidget(row)

        dock_layout.addWidget(field_section)
        dock_layout.addWidget(value_section)
        dock_layout.addStretch()

        self._widget_type = field_type
        self._apply_visibility()
        self._refresh_counts()

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        field_type = str(self.settings.get("field_type") or "int")
        chips: list[tuple[str, str]] = [(field_type, "accent")]
        if field_type in ("int", "float"):
            summary = (
                f"{self.settings.get('initial_value')} to "
                f"{self.settings.get('max_value')} by "
                f"{self.settings.get('increment_value')}"
            )
            chips.append((summary, ""))
        return chips, ""

    def _refresh_counts(self) -> None:
        self.refresh_dock_context()
        section = getattr(self, "field_section", None)
        if section is not None:
            section.set_count(str(self.settings.get("field_name") or ""))

    # -- value widgets ----------------------------------------------------
    def _make_value_widget(self, key: str, field_type: str):
        value = self.settings.get(key)
        label = dict(_VALUE_LABELS)[key]
        if field_type == "datetime" and key != "increment_value":
            widget = QDateTimeEdit()
            widget.setCalendarPopup(True)
            widget.setMinimumHeight(30)
            dt = _parse_iso(value) or _DEFAULT_DATETIME
            widget.setDateTime(QDateTime(dt))
            widget.dateTimeChanged.connect(
                lambda dt, k=key, l=label: self.set_setting(
                    k,
                    dt.toPython().isoformat(),
                    f"Rows {l} Changed",
                    f"Rows-{k}",
                )
            )
            return widget
        if field_type == "datetime":
            widget = QSpinBox()
            widget.setRange(-1_000_000_000, 1_000_000_000)
            return self._finish_spin(widget, key, value, label)
        if field_type == "int":
            widget = QSpinBox()
            widget.setRange(-1_000_000_000, 1_000_000_000)
            return self._finish_spin(widget, key, value, label)
        if field_type == "float":
            widget = QDoubleSpinBox()
            widget.setRange(-1_000_000_000, 1_000_000_000)
            widget.setDecimals(4)
            widget.setMinimumHeight(30)
            try:
                widget.setValue(float(value))
            except TypeError, ValueError:
                widget.setValue(0.0)
            widget.valueChanged.connect(
                lambda v, k=key, l=label: self.set_setting(
                    k, float(v), f"Rows {l} Changed", f"Rows-{k}"
                )
            )
            return widget

        widget = QLineEdit()
        widget.setMinimumHeight(30)
        widget.setText("" if value is None else str(value))
        self._debounced(
            widget.textChanged,
            lambda w=widget, k=key, l=label: self.set_setting(
                k, w.text(), f"Rows {l} Changed", f"Rows-{k}"
            ),
        )
        return widget

    def _finish_spin(self, widget: QSpinBox, key: str, value, label: str):
        widget.setMinimumHeight(30)
        try:
            widget.setValue(int(float(value)))
        except TypeError, ValueError:
            widget.setValue(0)
        widget.valueChanged.connect(
            lambda v, k=key, l=label: self.set_setting(
                k, int(v), f"Rows {l} Changed", f"Rows-{k}"
            )
        )
        return widget

    def _rebuild_value_widgets(self) -> None:
        field_type = str(self.settings.get("field_type") or "int")
        for key, _label in _VALUE_LABELS:
            row = self._value_rows.get(key)
            if row is None:
                continue
            old = self._value_widgets.get(key)
            widget = self._make_value_widget(key, field_type)
            row.replace_field(widget)
            if old is not None:
                old.deleteLater()
            self._value_widgets[key] = widget
        self._widget_type = field_type
        self._write_value_widgets()

    def _write_value_widgets(self) -> None:
        for key, widget in self._value_widgets.items():
            value = self.settings.get(key)
            blocked = widget.blockSignals(True)
            try:
                if isinstance(widget, QDateTimeEdit):
                    dt = _parse_iso(value) or _DEFAULT_DATETIME
                    widget.setDateTime(QDateTime(dt))
                elif isinstance(widget, QDoubleSpinBox):
                    try:
                        widget.setValue(float(value))
                    except TypeError, ValueError:
                        pass
                elif isinstance(widget, QSpinBox):
                    try:
                        widget.setValue(int(float(value)))
                    except TypeError, ValueError:
                        pass
                elif isinstance(widget, QLineEdit):
                    text = "" if value is None else str(value)
                    if widget.text() != text:
                        widget.setText(text)
            except RuntimeError:
                continue
            finally:
                widget.blockSignals(blocked)

    def _apply_visibility(self) -> None:
        field_type = str(self.settings.get("field_type") or "int")
        max_row = self._value_rows.get("max_value")
        if max_row is not None:
            max_row.setVisible(field_type != "string")

    # -- commits ----------------------------------------------------------
    def _commit_type(self, value: str) -> None:
        if value == str(self.settings.get("field_type") or "int"):
            return
        changes = self._converted_values(value)
        previous = getattr(self, "_suspend_node_evaluation", False)
        self._suspend_node_evaluation = True
        try:
            for key, converted in changes.items():
                self.set_setting(
                    key,
                    converted,
                    f"Rows {dict(_VALUE_LABELS)[key]} Changed",
                )
            self.set_setting("field_type", value, "Rows Field type Changed")
        finally:
            self._suspend_node_evaluation = previous
        self.request_evaluation()

    def _converted_values(self, target: str) -> dict:
        settings = self.settings
        if target == "int":
            return {
                key: self._number(settings.get(key), default, int)
                for key, default in _INT_DEFAULT.items()
            }
        if target == "float":
            return {
                key: self._number(settings.get(key), default, float)
                for key, default in _FLOAT_DEFAULT.items()
            }
        if target == "string":
            return {
                key: "" if settings.get(key) is None else str(settings.get(key))
                for key in _STRING_DEFAULT
            }
        initial = _parse_iso(settings.get("initial_value"))
        maximum = _parse_iso(settings.get("max_value"))
        increment = self._number(settings.get("increment_value"), 3600, float)
        return {
            "initial_value": (
                initial or datetime.fromisoformat(_DATETIME_DEFAULT["initial_value"])
            ).isoformat(),
            "increment_value": increment,
            "max_value": (
                maximum or datetime.fromisoformat(_DATETIME_DEFAULT["max_value"])
            ).isoformat(),
        }

    @staticmethod
    def _number(value, default, cast):
        try:
            return cast(float(value))
        except TypeError, ValueError:
            return default

    # -- model -> widgets -------------------------------------------------
    def after_change(self) -> None:
        if getattr(self, "name_edit", None) is None:
            return
        self._sync_widgets_from_model()
        self._refresh_counts()

    def _sync_widgets_from_model(self) -> None:
        if getattr(self, "name_edit", None) is None:
            return
        field_type = str(self.settings.get("field_type") or "int")
        if self._widget_type != field_type:
            self._rebuild_value_widgets()
        else:
            self._write_value_widgets()

        text = str(self.settings.get("field_name") or "")
        if self.name_edit.text() != text:
            blocked = self.name_edit.blockSignals(True)
            try:
                self.name_edit.setText(text)
            finally:
                self.name_edit.blockSignals(blocked)

        index = self.type_combo.findData(field_type)
        if index >= 0:
            blocked = self.type_combo.blockSignals(True)
            try:
                self.type_combo.setCurrentIndex(index)
            finally:
                self.type_combo.blockSignals(blocked)
        self._apply_visibility()


@register_node(PreparationNodes.DYNAMIC_ROW_BUILDER, NodeTypes.PREPARATION)
class TriggerNode_Rows(ShapingNode):
    icon = "node_generate_rows"
    node_code = PreparationNodes.DYNAMIC_ROW_BUILDER
    node_title = "Rows"
    node_type = NodeTypes.PREPARATION
    content_class = RowsContent
    output_text = ("Out",)
    content_label_objname = "trigger_node_generate_rows"
    style = {}  # noqa: RUF012 - shared empty node style
