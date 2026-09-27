"""Normalize Columns node: deterministic column-name cleanup.

Rewrites column names (trim whitespace, collapse inner whitespace to
underscores, change case) without touching row data. Pure rename, so the
operation stays lazy end to end.
"""

import re
from typing import Optional

import polars as pl
from qtpy.QtCore import Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

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
    frame_schema,
)
from trigger_designer.qt.widgets.common import (
    ColumnChecklist,
    ConfigSection,
    EmptyStateLabel,
    NoWheelComboBox,
    TextButton,
)
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException
from trigger_designer.qt.helpers import global_logger

CASE_OPTIONS = ["None", "Lower Case", "Upper Case", "Title Case"]
_CASE_TO_MODEL = {
    "None": "none",
    "Lower Case": "lower",
    "Upper Case": "upper",
    "Title Case": "title",
}
_CASE_TO_DISPLAY = {model: display for display, model in _CASE_TO_MODEL.items()}


def normalize_column_name(
    name: str,
    *,
    trim_whitespace: bool = True,
    spaces_to_underscore: bool = True,
    remove_all_whitespace: bool = False,
    case_modification: str = "none",
) -> str:
    """Apply the name rules in a fixed order: trim, whitespace, case."""
    result = name.strip() if trim_whitespace else name
    if remove_all_whitespace:
        result = re.sub(r"\s+", "", result)
    elif spaces_to_underscore:
        result = re.sub(r"\s+", "_", result)
    if case_modification == "lower":
        result = result.lower()
    elif case_modification == "upper":
        result = result.upper()
    elif case_modification == "title":
        result = result.title()
    # Never hand back an empty name; keep the original instead.
    return result or name


def build_rename_mapping(
    columns: list[str],
    selected: list[str],
    *,
    trim_whitespace: bool = True,
    spaces_to_underscore: bool = True,
    remove_all_whitespace: bool = False,
    case_modification: str = "none",
) -> dict[str, str]:
    """Map each in-scope column to its normalized name (changed ones only)."""
    scope = set(selected) if selected else set(columns)
    mapping: dict[str, str] = {}
    for column in columns:
        if column not in scope:
            continue
        normalized = normalize_column_name(
            column,
            trim_whitespace=trim_whitespace,
            spaces_to_underscore=spaces_to_underscore,
            remove_all_whitespace=remove_all_whitespace,
            case_modification=case_modification,
        )
        if normalized != column:
            mapping[column] = normalized
    return mapping


class NormalizeColumnsContent(
    QDMNodeIconContentWidget, TriggerChangeHandler, SerializableContentMixin
):
    """Content widget for the Normalize Columns node."""

    evaluate = Signal()
    serialized_state_schema = {
        "trim_whitespace": {"default": True},
        "spaces_to_underscore": {"default": True},
        "remove_all_whitespace": {"default": False},
        "case_modification": {"default": "none"},
        "selected_columns": {"default": []},
        "field_selection_initialized": {
            "attr": "_field_selection_initialized",
            "default": False,
        },
    }

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        self.history = self.node.scene.history

        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame] = None

        self.data: Optional[pl.DataFrame] = None
        self.variable_name = f"var_normalize_columns_{self.id}"

        self.trim_whitespace = True
        self.spaces_to_underscore = True
        self.remove_all_whitespace = False
        self.case_modification = "none"

        self.selected_columns: list[str] = []
        self.field_checkboxes = {}
        self._field_selection_initialized = False

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        icon_: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon_)

    def _get_schema(self) -> dict[str, pl.DataType]:
        if self.incom_data is None:
            return {}
        return dict(frame_schema(self.incom_data))

    def _normalize_selected_columns(self) -> None:
        available = set(self._get_schema())
        self.selected_columns = [
            column for column in self.selected_columns if column in available
        ]

    def _current_mapping(self) -> dict[str, str]:
        schema = self._get_schema()
        columns = list(schema)
        if self._field_selection_initialized:
            selected = [c for c in self.selected_columns if c in schema]
        else:
            selected = list(columns)
        return build_rename_mapping(
            columns,
            selected,
            trim_whitespace=self.trim_whitespace,
            spaces_to_underscore=self.spaces_to_underscore,
            remove_all_whitespace=self.remove_all_whitespace,
            case_modification=self.case_modification,
        )

    def update_data(self) -> None:
        if self.incom_data is None:
            self.data = None
            return
        try:
            columns = list(self._get_schema())
            mapping = self._current_mapping()
            final_names = [mapping.get(column, column) for column in columns]
            if len(set(final_names)) != len(final_names):
                self.data = None
                self.node.markInvalid(True)
                self.node.grNode.setToolTip(
                    "Normalize Columns: rules produce duplicate column names"
                )
                return
            self.data = self.incom_data.rename(mapping) if mapping else self.incom_data
            self.node.markDirty(False)
            self.node.markInvalid(False)
        except Exception as exc:
            global_logger.error(f"Normalize Columns error: {exc}")
            self.data = None

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is None:
            dock_layout.addWidget(EmptyStateLabel())
            return

        self._normalize_selected_columns()
        schema = self._get_schema()

        main_layout = QVBoxLayout()
        main_layout.setSpacing(2)
        main_layout.setContentsMargins(5, 5, 5, 5)

        rules_group = ConfigSection(
            "Name Rules", info="Applied in order: trim, whitespace, case."
        )
        trim_check = QCheckBox("Trim leading and trailing whitespace")
        trim_check.setChecked(self.trim_whitespace)
        trim_check.setToolTip("Remove whitespace at the start and end of names")
        trim_check.setMinimumHeight(30)
        trim_check.stateChanged.connect(lambda state: self.on_trim_changed(bool(state)))
        underscore_check = QCheckBox("Replace inner whitespace with underscores")
        underscore_check.setChecked(self.spaces_to_underscore)
        underscore_check.setToolTip("Collapse each run of whitespace into one '_'")
        underscore_check.setMinimumHeight(30)
        underscore_check.stateChanged.connect(
            lambda state: self.on_underscore_changed(bool(state))
        )
        remove_all_check = QCheckBox("Remove all whitespace")
        remove_all_check.setChecked(self.remove_all_whitespace)
        remove_all_check.setToolTip(
            "Delete every whitespace run (overrides underscores)"
        )
        remove_all_check.setMinimumHeight(30)
        remove_all_check.stateChanged.connect(
            lambda state: self.on_remove_all_changed(bool(state))
        )
        self._underscore_check = underscore_check
        self._remove_all_check = remove_all_check
        rules_group.addWidget(trim_check)
        rules_group.addWidget(underscore_check)
        rules_group.addWidget(remove_all_check)
        main_layout.addWidget(rules_group)

        case_group = ConfigSection("Modify Case")
        case_combo = NoWheelComboBox()
        case_combo.addItems(CASE_OPTIONS)
        case_combo.setCurrentText(_CASE_TO_DISPLAY.get(self.case_modification, "None"))
        case_combo.setToolTip("Change the capitalization of column names")
        case_combo.setMinimumHeight(30)
        case_combo.currentTextChanged.connect(self.on_case_changed)
        case_group.addWidget(case_combo)
        main_layout.addWidget(case_group)

        columns_group = ConfigSection("Columns to Rename")
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        all_button = TextButton("All", "Normalize all columns")
        none_button = TextButton("None", "Normalize no columns")
        all_button.clicked.connect(self.select_all_columns)
        none_button.clicked.connect(self.select_no_columns)
        buttons_layout.addWidget(all_button)
        buttons_layout.addWidget(none_button)
        buttons_layout.addStretch()
        columns_group.addLayout(buttons_layout)

        preserve = self._field_selection_initialized
        initial_checked = list(self.selected_columns) if preserve else list(schema)
        self.columns_list = ColumnChecklist(
            list(schema),
            initial_checked,
            label_fn=lambda column: f"{column} [{schema[column]}]",
            max_height=220,
        )
        self.columns_list.changed.connect(self.on_columns_changed)
        self.field_checkboxes = self.columns_list.checkboxes
        columns_group.addWidget(self.columns_list)
        main_layout.addWidget(columns_group)

        main_layout.addStretch()
        dock_layout.addLayout(main_layout)

        self.recursively_find_widgets(dock_layout)
        self.update_data()

    def select_all_columns(self) -> None:
        # One `changed` emission -> one update/evaluate cycle (see cleansing).
        self.columns_list.set_all_checked(True)

    def select_no_columns(self) -> None:
        self.columns_list.set_all_checked(False)

    def on_columns_changed(self, *_args) -> None:
        self.update_selected_columns()
        self.update_data()
        self.evaluate.emit()

    def update_selected_columns(self) -> None:
        self.selected_columns = [
            column
            for column, checkbox in self.field_checkboxes.items()
            if checkbox.isChecked()
        ]
        self._field_selection_initialized = True

    def on_trim_changed(self, state: bool) -> None:
        self.trim_whitespace = state
        self.update_data()
        self.evaluate.emit()

    def on_underscore_changed(self, state: bool) -> None:
        self.spaces_to_underscore = state
        if state and self.remove_all_whitespace:
            self.remove_all_whitespace = False
            self._remove_all_check.blockSignals(True)
            self._remove_all_check.setChecked(False)
            self._remove_all_check.blockSignals(False)
        self.update_data()
        self.evaluate.emit()

    def on_remove_all_changed(self, state: bool) -> None:
        self.remove_all_whitespace = state
        if state and self.spaces_to_underscore:
            self.spaces_to_underscore = False
            self._underscore_check.blockSignals(True)
            self._underscore_check.setChecked(False)
            self._underscore_check.blockSignals(False)
        self.update_data()
        self.evaluate.emit()

    def on_case_changed(self, value: str) -> None:
        if value in _CASE_TO_MODEL:
            self.case_modification = _CASE_TO_MODEL[value]
            self.update_data()
            self.evaluate.emit()
        else:
            global_logger.warning(f"Invalid case option value: {value}")

    def get_code(self) -> str:
        if not self.incoming_variable:
            return f"import polars as pl\n{self.variable_name} = pl.DataFrame()\n"
        columns = (
            list(frame_schema(self.incom_data)) if self.incom_data is not None else []
        )
        if self._field_selection_initialized:
            selected = [c for c in self.selected_columns if c in columns]
        else:
            selected = list(columns)
        mapping = build_rename_mapping(
            columns,
            selected,
            trim_whitespace=self.trim_whitespace,
            spaces_to_underscore=self.spaces_to_underscore,
            remove_all_whitespace=self.remove_all_whitespace,
            case_modification=self.case_modification,
        )
        if not mapping:
            return f"{self.variable_name} = {self.incoming_variable}\n"
        return (
            "import polars as pl\n"
            f"# Normalize column names ({len(mapping)} renamed)\n"
            f"{self.variable_name} = {self.incoming_variable}.rename({mapping!r})\n"
        )

    def serialize(self):
        return self.serialize_content_state(super().serialize())

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            self.deserialize_content_state(data)
            return True and res
        except Exception as e:
            dumpException(e)
        return res


@register_node(PreparationNodes.NORMALIZE_COLUMNS, NodeTypes.PREPARATION)
class TriggerNode_NormalizeColumns(TriggerNode):
    icon = "node_select"
    node_code = PreparationNodes.NORMALIZE_COLUMNS
    node_title = "Normalize Columns"
    node_type = NodeTypes.PREPARATION
    content_label_objname = "trigger_node_normalize_columns"
    style = {}

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[3])

    def initInnerClasses(self) -> None:
        self.content: NormalizeColumnsContent = NormalizeColumnsContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values) -> Optional[list]:
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            self.content.incom_data = input_value.get("data")
            self.content.incoming_variable = input_value.get("variable_name")
            self.content.update_data()
            self.param = [
                {
                    "data": self.content.data,
                    "variable_name": self.content.variable_name,
                }
            ]
            self.evalChildren()
            return self.param
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Input is not connected")
            return None

    def get_code(self):
        return self.content.get_code()
