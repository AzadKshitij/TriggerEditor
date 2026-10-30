"""Gaps node: missing, repeated and out-of-order numbers; days with no entry.

Logic is in ``core/audit/gaps.py``; this module is the dock and the node shell.
Sockets: ``G`` the findings (one row per gap range), ``S`` the one-row summary.
"""

from __future__ import annotations

from qtpy.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from trigger_designer.core.audit.common import SUPPORTED_DATE_FORMATS
from trigger_designer.core.audit.gaps import GapsParams, run_gaps
from trigger_designer.core.node_configuration import (
    AuditNodes,
    NodeTypes,
    register_node,
)
from trigger_designer.qt.widgets.common import (
    CONTROL_H,
    ColumnChecklist,
    FormRow,
    TextButton,
)
from trigger_designer.qt.widgets.nodes.Audit._base import AuditContent, AuditNode

MODE_OPTIONS = (("number", "Number"), ("prefixed", "Prefixed"), ("date", "Date"))
MAX_NUMBER = 2_147_483_647  # QSpinBox is 32-bit; the algorithm itself is Int64
MAX_DAYS = 3660


class GapsContent(AuditContent):
    PARAMS = GapsParams
    RUN = staticmethod(run_gaps)
    OP = "audit.gaps"
    TEST_NAME = "Gaps"
    OUTPUT_KINDS = ("gaps", "gapsum")
    SUMMARY_INDEX = 1
    EXCEPTIONS_INDEX = 0
    HISTORY = "Gaps Setting Changed"

    # ---- dock ---------------------------------------------------------------
    def build_dock(self, dock_layout: QVBoxLayout) -> None:
        self.sequence_section = self.section("Sequence")
        self.column_picker = self.add_picker(
            "sequence_column", "Column", "Gaps Column Changed"
        )
        self.mode_control = self.add_segment(
            "mode", MODE_OPTIONS, "Gaps Type Changed", compact=True
        )
        self.mode_control.setToolTip(
            "Number: whole numbers. Prefixed: text then digits, such as JE-000123. "
            "Date: calendar days with no entry."
        )
        self.sequence_section.addWidget(FormRow("Column", self.column_picker))
        self.sequence_section.addWidget(FormRow("Type", self.mode_control))
        dock_layout.addWidget(self.sequence_section)

        self.group_section = self.section("Group by")
        names = [name for name, _ in self.column_items(self.group_columns)]
        self.group_list = ColumnChecklist(names, self.group_columns)
        self.bind("group_columns", self.group_list, "checklist", "Gaps Groups Changed")
        toolbar = QWidget()
        toolbar._undo_composite = True
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addStretch(1)
        for label, tip, checked in (
            ("All", "Group by every column", True),
            ("None", "Do not group", False),
        ):
            button = TextButton(label, tip, toolbar)
            button.setObjectName("BulkButton")
            button.setMinimumWidth(32)
            button.clicked.connect(
                lambda _=False, c=checked: self.group_list.set_all_checked(c)
            )
            row.addWidget(button)
        self.group_section.addWidget(toolbar)
        self.group_section.addWidget(self.group_list)
        dock_layout.addWidget(self.group_section)

        self.report_section = self.section("Also report")
        self.duplicates_check = self.add_check(
            "report_duplicates", "Repeated numbers", "Gaps Repeats Changed"
        )
        self.order_check = self.add_check(
            "report_out_of_order", "Numbers out of order", "Gaps Order Changed"
        )
        self.order_check.setToolTip(
            "A number lower than a higher one seen earlier in the same series. "
            "This depends on the order the rows arrive in."
        )
        self.report_section.addWidget(self.duplicates_check)
        self.report_section.addWidget(self.order_check)
        dock_layout.addWidget(self.report_section)

        self.range_section = self.section("Expected range")
        self.start_spin = self.add_spin(
            "range_start",
            "Gaps Range Changed",
            minimum=-1,
            maximum=MAX_NUMBER,
            optional="Lowest seen",
        )
        self.end_spin = self.add_spin(
            "range_end",
            "Gaps Range Changed",
            minimum=-1,
            maximum=MAX_NUMBER,
            optional="Highest seen",
        )
        self.start_spin.setToolTip(
            "Set the first number you expect to see to catch a missing first document."
        )
        self.end_spin.setToolTip(
            "Set the last number you expect to see to catch missing final documents."
        )
        self.range_section.addWidget(FormRow("First", self.start_spin, label_width=64))
        self.range_section.addWidget(FormRow("Last", self.end_spin, label_width=64))
        dock_layout.addWidget(self.range_section)

        self.dates_section = self.section("Dates")
        self.format_combo = self.add_combo(
            "date_format",
            tuple((fmt, fmt) for fmt in SUPPORTED_DATE_FORMATS),
            "Gaps Date Format Changed",
        )
        self.min_gap_spin = self.add_spin(
            "min_gap_days",
            "Gaps Smallest Gap Changed",
            minimum=1,
            maximum=MAX_DAYS,
        )
        self.min_gap_spin.setSuffix(" days")
        self.weekend_check = self.add_check(
            "business_days_only", "Skip weekends", "Gaps Weekends Changed"
        )
        self.holidays_edit = self.add_lines(
            "holidays", "Gaps Holidays Changed", placeholder="2024-03-29"
        )
        self.holidays_edit.setToolTip("One holiday per line, written YYYY-MM-DD.")
        self.holidays_edit.setMinimumHeight(CONTROL_H * 2)
        self.holidays_row = FormRow("Holidays", self.holidays_edit, label_width=64)
        self.dates_section.addWidget(
            FormRow("Format", self.format_combo, label_width=64)
        )
        self.dates_section.addWidget(
            FormRow("Smallest gap", self.min_gap_spin, label_width=64)
        )
        self.dates_section.addWidget(self.weekend_check)
        self.dates_section.addWidget(self.holidays_row)
        dock_layout.addWidget(self.dates_section)

        dock_layout.addWidget(self.result_section())
        dock_layout.addStretch()

    def _apply_visibility(self) -> None:
        is_date = self.mode == "date"
        for name, visible in (
            ("report_section", not is_date),
            ("range_section", not is_date),
            ("dates_section", is_date),
        ):
            section = getattr(self, name, None)
            if section is not None:
                try:
                    section.setVisible(visible)
                except RuntimeError:  # dock rebuilt: the old widgets are gone
                    setattr(self, name, None)
        row = getattr(self, "holidays_row", None)
        if row is not None:
            try:
                row.setVisible(self.business_days_only)
            except RuntimeError:
                self.holidays_row = None

    def dock_context(self):
        chips = [("Gaps", "accent"), (self.mode, "muted")]
        if self.sequence_column:
            chips.append((self.sequence_column, "muted"))
        return chips, ""


@register_node(AuditNodes.GAPS, NodeTypes.AUDIT)
class TriggerNode_Gaps(AuditNode):
    icon = "node_gaps"
    node_code = AuditNodes.GAPS
    node_type = NodeTypes.AUDIT
    node_title = "Gaps"
    content_class = GapsContent
    OUTPUT_TYPES = (3, 1)
    output_text = ("G", "S")
    content_label_objname = "trigger_node_gaps"
