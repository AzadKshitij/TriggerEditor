"""Join node: Qt wrapper only; the logic is core/shaping/join.py."""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.node_configuration import (
    JoinNodes,
    NodeTypes,
    register_node,
)
from trigger_designer.core.shaping import join as core
from trigger_designer.qt.helpers.shaping_support import ShapingContent, ShapingNode
from trigger_designer.qt.node_base import upstream_rename_map
from trigger_designer.qt.widgets.common import (
    ColumnPicker,
    ConfigSection,
    EmptyStateLabel,
    IconButton,
    TextButton,
    dtype_label,
)
from trigger_designer.qt.widgets.common.column_picker import ColumnItem


class JoinContent(ShapingContent):
    """Key pairs plus an output-column selection over one full outer join."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.join"
    OUTPUT_KINDS = ("left", "join", "right")
    INPUTS = 2
    HISTORY = "Join"
    SUMMARY = "three-way join"

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        # Keep the generated variable names the old node used.
        self.output_variables = [
            f"var_l_join_{self.id}",
            f"var_join_{self.id}",
            f"var_r_join_{self.id}",
        ]
        self.variable_name = self.output_variables[0]
        self.out1_variable_name = self.output_variables[1]
        self.out2_variable_name = self.output_variables[2]
        self._mapping_rows: list[dict] = []

    # -- derived model repair --------------------------------------------
    def compute(self) -> list:
        if self.ready():
            left_names = list(self.schema(0))
            right_names = list(self.schema(1))
            settings = core.ensure_default_mapping(
                dict(self.settings), left_names, right_names
            )
            settings = core.sync_selected_with_schema(settings, left_names, right_names)
            if settings != self.settings:
                self.settings.update(settings)
        return super().compute()

    def apply_upstream_renames(self, left_map: dict, right_map: dict) -> bool:
        left_names = list(self.schema(0))
        right_names = list(self.schema(1))
        settings, changed = core.apply_upstream_renames(
            dict(self.settings), left_map, right_map, left_names, right_names
        )
        if changed:
            self.settings.update(settings)
        return changed

    # -- dock construction ----------------------------------------------
    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if not self.ready():
            dock_layout.addWidget(EmptyStateLabel("Both inputs must be connected"))
            return

        mapping_section = ConfigSection("Key pairs")
        mapping_section._undo_composite = True
        self.mapping_section = mapping_section
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(2)
        self.add_pair_button = IconButton.themed(
            "Add key pair",
            rsm_icon=self.node.rsm.get("icon_add"),
        )
        self.add_pair_button.clicked.connect(self._add_pair)
        toolbar.addStretch()
        toolbar.addWidget(self.add_pair_button)
        mapping_section.addLayout(toolbar)
        self.mapping_host = QWidget()
        self.mapping_layout = QVBoxLayout(self.mapping_host)
        self.mapping_layout.setContentsMargins(0, 0, 0, 0)
        self.mapping_layout.setSpacing(2)
        mapping_section.addWidget(self.mapping_host)
        dock_layout.addWidget(mapping_section)

        output_section = ConfigSection(
            "Output columns",
            "Unchecked columns stay out of the joined output.",
        )
        output_section._undo_composite = True
        self.output_section = output_section
        output_toolbar = QHBoxLayout()
        output_toolbar.setContentsMargins(0, 0, 0, 0)
        output_toolbar.setSpacing(2)
        self.auto_accept_check = QCheckBox("Auto-accept new columns")
        self.auto_accept_check.setChecked(
            bool(self.settings.get("auto_accept_new_columns", True))
        )
        self.auto_accept_check.toggled.connect(self._on_auto_accept)
        output_toolbar.addWidget(self.auto_accept_check)
        output_toolbar.addStretch()
        all_button = TextButton("All", "Select all output columns")
        none_button = TextButton("None", "Deselect all output columns")
        all_button.clicked.connect(lambda: self._check_all(True))
        none_button.clicked.connect(lambda: self._check_all(False))
        output_toolbar.addWidget(all_button)
        output_toolbar.addWidget(none_button)
        output_section.addLayout(output_toolbar)

        self.output_picker = ColumnPicker(
            [], (), rsm=self.node.rsm, label="Output columns"
        )
        self.output_picker.changed.connect(self._on_output_changed)
        output_section.addWidget(self.output_picker)
        dock_layout.addWidget(output_section)
        dock_layout.addStretch()

        self._sync_widgets_from_model()

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        mapping = self.settings.get("mapping_data") or []
        selected = self.settings.get("selected_columns") or []
        chips: list[tuple[str, str]] = [
            (f"{len(mapping)} key{'s' if len(mapping) != 1 else ''}", ""),
            (f"{len(selected)} column{'s' if len(selected) != 1 else ''}", "accent"),
        ]
        return chips, "full outer join"

    # -- mapping ----------------------------------------------------------
    def _add_pair(self) -> None:
        mapping = [dict(item) for item in self.settings.get("mapping_data") or []]
        left_names = list(self.schema(0))
        right_names = list(self.schema(1))
        used = {(item.get("left_column"), item.get("right_column")) for item in mapping}
        pair = {"left_column": "", "right_column": ""}
        for left_name in left_names:
            for right_name in right_names:
                if (left_name, right_name) not in used:
                    pair = {
                        "left_column": left_name,
                        "right_column": right_name,
                    }
                    break
            if pair["left_column"]:
                break
        mapping.append(pair)
        self._commit_mapping(mapping, "Join Key Pair Added", structural=True)

    def _remove_pair(self, index: int) -> None:
        mapping = [dict(item) for item in self.settings.get("mapping_data") or []]
        if not 0 <= index < len(mapping):
            return
        del mapping[index]
        self._commit_mapping(mapping, "Join Key Pair Removed", structural=True)

    def _commit_mapping(
        self, mapping: list[dict], text: str, *, structural: bool = False
    ) -> None:
        if mapping == (self.settings.get("mapping_data") or []):
            return
        self.set_setting("mapping_data", mapping, text, structural=structural)

    def _snapshot_mapping(self) -> list[dict]:
        rows = []
        for row in self._mapping_rows:
            left = row["left"].checked()
            right = row["right"].checked()
            rows.append(
                {
                    "left_column": left[0] if left else "",
                    "right_column": right[0] if right else "",
                }
            )
        return rows

    def _mapping_picker(self, side: int, value: str, label: str) -> ColumnPicker:
        schema = self.schema(side)
        items = [(name, dtype_label(schema[name])) for name in schema]
        if value and value not in schema:
            items.append(ColumnItem(value, "", f"{value} (missing)"))
        picker = ColumnPicker(
            items,
            [value] if value else (),
            single=True,
            rsm=self.node.rsm,
            label=label,
        )
        picker.changed.connect(lambda _names: self._on_mapping_combo_changed())
        return picker

    def _on_mapping_combo_changed(self) -> None:
        self._commit_mapping(self._snapshot_mapping(), "Join Key Pair Changed")

    def _rebuild_mapping_rows(self) -> None:
        while self.mapping_layout.count():
            item = self.mapping_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._mapping_rows = []
        for index, entry in enumerate(self.settings.get("mapping_data") or []):
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            left = self._mapping_picker(
                0, entry.get("left_column") or "", "Left key column"
            )
            right = self._mapping_picker(
                1, entry.get("right_column") or "", "Right key column"
            )
            arrow = QLabel("\u2192")
            arrow.setObjectName("FieldHint")
            arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
            arrow.setFixedWidth(16)
            remove = IconButton.themed(
                "Remove key pair",
                rsm_icon=self.node.rsm.get("icon_remove"),
            )
            remove.clicked.connect(lambda _=False, i=index: self._remove_pair(i))
            layout.addWidget(left, 1)
            layout.addWidget(arrow)
            layout.addWidget(right, 1)
            layout.addWidget(remove)
            self.mapping_layout.addWidget(row)
            self._mapping_rows.append({"left": left, "right": right})

    # -- output columns ---------------------------------------------------
    def _output_items(self) -> list[dict]:
        return [{"name": name, "source": "L"} for name in self.schema(0)] + [
            {"name": name, "source": "R"} for name in self.schema(1)
        ]

    @staticmethod
    def _label(entry: dict) -> str:
        return f"{entry['source']}: {entry['name']}"

    def _checked_labels(self) -> list[str]:
        selected = self.settings.get("selected_columns") or []
        if not selected:
            return [self._label(entry) for entry in self._output_items()]
        return [self._label(entry) for entry in selected]

    def _rebuild_output_checklist(self) -> None:
        items = [
            ColumnItem(label, "", label)
            for label in (self._label(entry) for entry in self._output_items())
        ]
        blocked = self.output_picker.blockSignals(True)
        try:
            self.output_picker.setColumns(items, self._checked_labels())
        finally:
            self.output_picker.blockSignals(blocked)

    def _on_output_changed(self, labels: list[str]) -> None:
        selected = []
        for label in labels:
            source, _, name = label.partition(": ")
            if name:
                selected.append({"name": name, "source": source})
        current = self.settings.get("selected_columns") or []
        if selected == current:
            return
        self.set_setting("selected_columns", selected, "Join Output Columns Changed")

    def _check_all(self, checked: bool) -> None:
        labels = [self._label(entry) for entry in self._output_items()]
        self.output_picker.set_selected(labels if checked else [], emit=True)

    def _on_auto_accept(self, checked: bool) -> None:
        self.set_setting(
            "auto_accept_new_columns",
            bool(checked),
            "Join Auto Accept Changed",
        )

    # -- model -> widgets -------------------------------------------------
    def _sync_widgets_from_model(self) -> None:
        if getattr(self, "mapping_layout", None) is None:
            return
        self._rebuild_mapping_rows()
        self._rebuild_output_checklist()
        blocked = self.auto_accept_check.blockSignals(True)
        try:
            self.auto_accept_check.setChecked(
                bool(self.settings.get("auto_accept_new_columns", True))
            )
        finally:
            self.auto_accept_check.blockSignals(blocked)


@register_node(JoinNodes.JOIN, NodeTypes.JOIN)
class TriggerNode_Join(ShapingNode):
    icon = "node_join"
    node_code = JoinNodes.JOIN
    node_type = NodeTypes.JOIN
    node_title = "Join"
    content_class = JoinContent
    output_text = ("L", "J", "R")
    content_label_objname = "trigger_node_join"
    style = {}  # noqa: RUF012 - shared empty node style

    def processInputs(self, input_values):
        try:
            left = self.getInput(0)
            right = self.getInput(1)
            if left is not None and right is not None:
                self.content.apply_upstream_renames(
                    upstream_rename_map(left), upstream_rename_map(right)
                )
        except (AttributeError, ValueError, RuntimeError):
            pass
        return super().processInputs(input_values)
