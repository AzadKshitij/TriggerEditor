"""Aggregate node: Qt wrapper only; the logic is core/shaping/aggregate.py."""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import aggregate as core
from trigger_designer.qt.helpers.shaping_support import ShapingContent, ShapingNode
from trigger_designer.qt.widgets.common import (
    EmptyStateLabel,
    IconButton,
    NoWheelComboBox,
)


class AggregateContent(ShapingContent):
    """Ordered group-key and measure actions in one editable table."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.aggregate"
    OUTPUT_KINDS = ("aggregate",)
    INPUTS = 1
    HISTORY = "Aggregate"
    SUMMARY = "group and aggregate"

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        # Keep the generated variable name the old node used.
        self.output_variables = [f"var_groupby_{self.id}"]
        self.variable_name = self.output_variables[0]
        self.actions_table: QTableWidget | None = None
        self._building_table = False

    # -- dock construction ----------------------------------------------
    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if not self.ready():
            dock_layout.addWidget(EmptyStateLabel())
            return

        command = QWidget()
        command_layout = QHBoxLayout(command)
        command_layout.setContentsMargins(0, 0, 0, 0)
        command_layout.setSpacing(2)
        command.setFixedHeight(30)

        self.field_picker = NoWheelComboBox()
        self.field_picker.setMinimumHeight(30)
        self.field_picker.setToolTip("Field to add as a group key or measure")
        for name in self.schema(0):
            self.field_picker.addItem(name, name)
        command_layout.addWidget(self.field_picker, 1)

        self.add_btn = IconButton.themed(
            "Add field as group key or measure",
            rsm_icon=self.node.rsm.get("icon_add"),
        )
        self.add_btn.clicked.connect(self._add_selected_field)
        command_layout.addWidget(self.add_btn)

        self.remove_btn = IconButton.themed(
            "Remove selected action",
            rsm_icon=self.node.rsm.get("icon_remove"),
        )
        self.remove_btn.clicked.connect(self._remove_selected_actions)
        command_layout.addWidget(self.remove_btn)

        dock_layout.addWidget(command)
        self._create_table()
        dock_layout.addWidget(self.actions_table, 1)
        self._rebuild_table()
        self._refresh_counts()

    def _create_table(self) -> None:
        table = QTableWidget()
        table.setObjectName("ColumnTable")
        table._undo_composite = True
        table.verticalHeader().setDefaultSectionSize(22)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Field", "Action", "Output Field Name"])
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setMinimumHeight(180)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table.verticalHeader().setVisible(False)
        table.setRowCount(0)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        header = table.horizontalHeader()
        header.setFixedHeight(20)
        for column in range(3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(0, 180)
        table.setColumnWidth(1, 120)
        table.setColumnWidth(2, 240)
        table.itemChanged.connect(self._on_alias_edited)
        self.actions_table = table

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        actions = self._actions()
        chips: list[tuple[str, str]] = []
        keys = sum(1 for entry in actions if entry["action"] == "GroupBy")
        measures = len(actions) - keys
        if keys:
            chips.append((f"{keys} key{'s' if keys > 1 else ''}", ""))
        if measures:
            chips.append((f"{measures} measure{'s' if measures > 1 else ''}", "accent"))
        return chips, ""

    def _refresh_counts(self) -> None:
        self.refresh_dock_context()

    # -- model helpers ----------------------------------------------------
    def _actions(self) -> list[dict]:
        return core.normalize({"actions": self.settings.get("actions") or []})[
            "actions"
        ]

    def _commit(
        self,
        actions: list[dict],
        text: str,
        *,
        structural: bool = False,
        merge_key: str | None = None,
    ) -> None:
        normalized = core.normalize({"actions": actions})["actions"]
        if normalized == self.settings.get("actions"):
            return
        self.set_setting(
            "actions",
            normalized,
            text,
            merge_key,
            structural=structural,
        )

    def _field_dtype(self, field: str):
        return self.schema(0).get(field)

    def _allowed_actions(self, field: str) -> list[str]:
        return core.actions_for_dtype(self._field_dtype(field))

    # -- table construction ----------------------------------------------
    def _rebuild_table(self) -> None:
        table = self.actions_table
        if table is None:
            return
        self._building_table = True
        try:
            table.blockSignals(True)
            table.setRowCount(0)
            for entry in self._actions():
                self._insert_row(entry)
        finally:
            table.blockSignals(False)
            self._building_table = False

    def _insert_row(self, entry: dict) -> None:
        table = self.actions_table
        if table is None:
            return
        row = table.rowCount()
        table.insertRow(row)
        field_item = QTableWidgetItem(entry["field"])
        field_item.setFlags(field_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row, 0, field_item)

        allowed = self._allowed_actions(entry["field"])
        if entry["action"] not in allowed:
            allowed = allowed + [entry["action"]]
        combo = NoWheelComboBox()
        combo.setObjectName("CellCombo")
        combo.setMinimumHeight(18)
        for action in allowed:
            combo.addItem(action, action)
        combo.setCurrentIndex(max(0, combo.findData(entry["action"])))
        combo.currentIndexChanged.connect(
            lambda _index, w=combo: self._on_action_changed(w)
        )
        table.setCellWidget(row, 1, combo)
        table.setItem(row, 2, QTableWidgetItem(entry["output_name"]))

    def _row_field(self, row: int) -> str:
        table = self.actions_table
        if table is None:
            return ""
        item = table.item(row, 0)
        return item.text() if item is not None else ""

    def _row_for_combo(self, combo) -> int:
        table = self.actions_table
        if table is None:
            return -1
        for row in range(table.rowCount()):
            if table.cellWidget(row, 1) is combo:
                return row
        return -1

    # -- table edits ------------------------------------------------------
    def _add_selected_field(self) -> None:
        if self.actions_table is None:
            return
        field = self.field_picker.currentData() or self.field_picker.currentText()
        field = str(field or "").strip()
        if not field:
            return
        actions = self._actions()
        if any(entry["field"] == field for entry in actions):
            return
        actions.append(
            {
                "field": field,
                "action": "GroupBy",
                "output_name": field,
            }
        )
        self._commit(actions, "Aggregate Field Added", structural=True)

    def _remove_selected_actions(self) -> None:
        table = self.actions_table
        if table is None:
            return
        selected = table.selectionModel().selectedRows()
        doomed = {self._row_field(index.row()) for index in selected}
        doomed.discard("")
        if not doomed:
            return
        actions = [entry for entry in self._actions() if entry["field"] not in doomed]
        self._commit(actions, "Aggregate Field Removed", structural=True)

    def _on_action_changed(self, combo) -> None:
        if self._building_table or self.actions_table is None:
            return
        row = self._row_for_combo(combo)
        if row < 0:
            return
        field = self._row_field(row)
        action = combo.currentData() or combo.currentText()
        actions = self._actions()
        for entry in actions:
            if entry["field"] == field:
                entry["action"] = action
                entry["output_name"] = core.default_output_name(field, action)
                break
        else:
            return
        self._commit(actions, "Aggregate Action Changed")

    def _on_alias_edited(self, item: QTableWidgetItem) -> None:
        if self._building_table or self.actions_table is None or item is None:
            return
        if item.column() != 2:
            return
        field = self._row_field(item.row())
        actions = self._actions()
        for entry in actions:
            if entry["field"] == field:
                if entry["output_name"] == item.text():
                    return
                entry["output_name"] = item.text()
                break
        else:
            return
        self._commit(
            actions,
            "Aggregate Output Renamed",
            merge_key="aggregate-alias",
        )

    # -- model -> widgets -------------------------------------------------
    def _sync_widgets_from_model(self) -> None:
        table = self.actions_table
        if table is None:
            return
        actions = self._actions()
        if table.rowCount() != len(actions):
            self._rebuild_table()
            return
        self._building_table = True
        try:
            table.blockSignals(True)
            for row, entry in enumerate(actions):
                field_item = table.item(row, 0)
                output_item = table.item(row, 2)
                combo = table.cellWidget(row, 1)
                if field_item is not None and field_item.text() != entry["field"]:
                    field_item.setText(entry["field"])
                if combo is not None:
                    index = combo.findData(entry["action"])
                    if index >= 0 and combo.currentIndex() != index:
                        blocked = combo.blockSignals(True)
                        try:
                            combo.setCurrentIndex(index)
                        finally:
                            combo.blockSignals(blocked)
                if (
                    output_item is not None
                    and output_item.text() != entry["output_name"]
                ):
                    output_item.setText(entry["output_name"])
        finally:
            table.blockSignals(False)
            self._building_table = False

    def after_change(self) -> None:
        self._refresh_counts()


@register_node(PreparationNodes.GROUPBY, NodeTypes.PREPARATION)
class TriggerNode_GroupBy(ShapingNode):
    icon = "node_groupby"
    node_code = PreparationNodes.GROUPBY
    node_title = "Aggregate"
    node_type = NodeTypes.PREPARATION
    content_class = AggregateContent
    output_text = ("Out",)
    content_label_objname = "trigger_node_groupby"
    style = {}  # noqa: RUF012 - shared empty node style
