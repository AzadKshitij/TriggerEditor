"""Duplicates audit node: Qt wrapper only; the test is core/audit/duplicates.py.

Sockets: ``D`` Duplicates (every row of a group of 2+, with ``dup_group_id`` and
``dup_count``), ``U`` Unique (every other row) and ``S`` the one-row Summary.
"""

from __future__ import annotations

from qtpy.QtWidgets import QHBoxLayout, QSpinBox, QVBoxLayout, QWidget

from trigger_designer.core.audit.common import SUPPORTED_DATE_FORMATS
from trigger_designer.core.audit.duplicates import DuplicatesParams, run_duplicates
from trigger_designer.core.node_configuration import (
    AuditNodes,
    NodeTypes,
    register_node,
)
from trigger_designer.qt.widgets.common import (
    ColumnChecklist,
    FormRow,
    TextButton,
)
from trigger_designer.qt.widgets.nodes.Audit._base import AuditContent, AuditNode

NEAR_TIP = "Near matching also groups rows linked through a chain of close neighbours."


class DuplicatesContent(AuditContent):
    PARAMS = DuplicatesParams
    RUN = staticmethod(run_duplicates)
    OP = "audit.duplicates"
    TEST_NAME = "Duplicates"
    OUTPUT_KINDS = ("dup", "uniq", "dupsum")
    SUMMARY_INDEX = 2
    EXCEPTIONS_INDEX = 0
    HISTORY = "Duplicate Setting Changed"

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        self.duplicates_var: str = self.output_variables[0]
        self.unique_var: str = self.output_variables[1]
        self.near_section = None

    # ---- dock ---------------------------------------------------------
    def build_dock(self, dock_layout: QVBoxLayout) -> None:
        match = self.section("Match on")
        names = [name for name, _label in self.column_items(self.key_columns)]
        self.keys_list = ColumnChecklist(names, list(self.key_columns))
        self.bind("key_columns", self.keys_list, "checklist", "Duplicate Keys Changed")
        toolbar = QWidget()
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(4)
        bar.addStretch(1)
        self.all_btn = TextButton("All", "Use every column as a key", toolbar)
        self.none_btn = TextButton("None", "Use no column as a key", toolbar)
        for button, state in ((self.all_btn, True), (self.none_btn, False)):
            button.setObjectName("BulkButton")
            button.setMinimumWidth(32)
            button.clicked.connect(
                lambda _checked=False, s=state: self.keys_list.set_all_checked(s)
            )
            bar.addWidget(button)
        match.addWidget(toolbar)
        match.addWidget(self.keys_list)
        self.trim_check = self.add_check(
            "trim_text", "Trim spaces", "Duplicate Trim Changed"
        )
        self.case_check = self.add_check(
            "ignore_case", "Ignore case", "Duplicate Case Changed"
        )
        self.trim_check.setToolTip("Ignore spaces before and after text when matching.")
        self.case_check.setToolTip("Treat upper and lower case letters as equal.")
        match.addWidget(self.trim_check)
        match.addWidget(self.case_check)
        dock_layout.addWidget(match)

        kind = self.section("Match type")
        self.mode_control = self.add_segment(
            "mode",
            (("exact", "Exact"), ("near", "Near")),
            "Duplicate Match Type Changed",
        )
        self.mode_control.setToolTip(NEAR_TIP)
        kind.addWidget(self.mode_control)
        dock_layout.addWidget(kind)

        near = self.section("Near match")
        self.near_section = near
        self.amount_picker = self.add_picker(
            "amount_column", "Amount", "Duplicate Amount Changed", blank=True
        )
        self.tolerance_spin = self.add_dspin("tolerance", "Duplicate Tolerance Changed")
        self.tolerance_kind_control = self.add_segment(
            "tolerance_kind",
            (("absolute", "Amount"), ("percent", "Percent")),
            "Duplicate Tolerance Kind Changed",
            compact=True,
        )
        tolerance = QWidget()
        row = QHBoxLayout(tolerance)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(self.tolerance_spin, 1)
        row.addWidget(self.tolerance_kind_control, 1)
        self.date_picker = self.add_picker(
            "date_column", "Date", "Duplicate Date Column Changed", blank=True
        )
        self.window_spin: QSpinBox = self.add_spin(
            "window_days", "Duplicate Window Changed", maximum=3660
        )
        self.window_spin.setSuffix(" days")
        self.format_combo = self.add_combo(
            "date_format",
            tuple((f, f) for f in SUPPORTED_DATE_FORMATS),
            "Duplicate Date Format Changed",
            tip="How text dates are read; ignored for date columns.",
        )
        for label, widget in (
            ("Amount", self.amount_picker),
            ("Tolerance", tolerance),
            ("Date", self.date_picker),
            ("Window", self.window_spin),
            ("Date format", self.format_combo),
        ):
            near.addWidget(FormRow(label, widget, label_width=80))
        dock_layout.addWidget(near)

        value = self.section("Value")
        self.value_picker = self.add_picker(
            "value_column", "Value", "Duplicate Value Column Changed", blank=True
        )
        value.addWidget(FormRow("Value", self.value_picker, label_width=80))
        dock_layout.addWidget(value)

        dock_layout.addWidget(self.result_section())
        dock_layout.addStretch()

    def _apply_visibility(self) -> None:
        section = self.near_section
        if section is None:
            return
        try:
            section.setVisible(self.mode == "near")
        except RuntimeError:  # dock rebuilt
            self.near_section = None

    def dock_context(self):
        n = len(self.key_columns)
        keys = f"{n} key column{'' if n == 1 else 's'}"
        return [(keys, "accent"), (self.mode, "muted")], ""

    def dock_summary(self) -> str:
        n = len(self.key_columns)
        return f"{self.mode} match on {n} column{'' if n == 1 else 's'}"


@register_node(AuditNodes.DUPLICATES, NodeTypes.AUDIT)
class TriggerNode_Duplicates(AuditNode):
    icon = "node_duplicates"
    node_code = AuditNodes.DUPLICATES
    node_type = NodeTypes.AUDIT
    node_title = "Duplicates"
    content_class = DuplicatesContent
    OUTPUT_TYPES = (3, 3, 1)
    output_text = ("D", "U", "S")
    content_label_objname = "trigger_node_duplicates"
    style = {}  # noqa: RUF012 - shared empty node style
