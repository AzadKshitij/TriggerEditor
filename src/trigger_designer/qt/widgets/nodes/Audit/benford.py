"""Benford node: digit table (``T``), one-row verdict (``S``), drill-down rows (``D``).

All maths is ``core/audit/benford.py``; this module is the settings dock, the
chart and the node. Live evaluation reads at most ``LIVE_ROW_LIMIT`` leading
rows and collects only the small digit-count table; Run reads everything.
"""

from __future__ import annotations

from typing import Any

from qtpy.QtWidgets import QLabel, QVBoxLayout

from trigger_designer.core.audit.benford import (
    LIVE_ROW_LIMIT,
    BenfordParams,
    digit_range,
    run_benford,
)
from trigger_designer.core.audit.common import AuditResult
from trigger_designer.core.node_configuration import (
    AuditNodes,
    NodeTypes,
    register_node,
)
from trigger_designer.qt.widgets.common import ColumnChecklist, FormRow
from trigger_designer.qt.widgets.nodes.Audit._base import AuditContent, AuditNode
from trigger_designer.qt.widgets.nodes.Audit.benford_chart import BenfordChartWidget

_DIGIT_OPTIONS = ((1, "First digit"), (2, "First two"))


class BenfordContent(AuditContent):
    PARAMS = BenfordParams
    RUN = staticmethod(run_benford)
    OP = "audit.benford"
    TEST_NAME = "Benford"
    OUTPUT_KINDS = ("benford", "benfordsum", "benforddrill")
    SUMMARY_INDEX = 1
    EXCEPTIONS_INDEX = 2
    LIVE_SUMMARY = True
    HISTORY = "Benford Setting Changed"

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        self.chart: BenfordChartWidget | None = None
        self.chi_label: QLabel | None = None
        self.drill_list: ColumnChecklist | None = None

    # ---- outputs -----------------------------------------------------------
    @property
    def table_var(self) -> str:
        return self.output_variables[0]

    @property
    def drill_var(self) -> str:
        return self.output_variables[2]

    def build_result(self) -> AuditResult:
        """Live: the first ``LIVE_ROW_LIMIT`` rows; only digit counts are collected."""
        return run_benford(self.incom_data, self.params(), row_limit=LIVE_ROW_LIMIT)

    def on_live_failed(self) -> None:
        # Blank the chart instead of keeping a picture of settings that no
        # longer run (the base clears the result and summary and re-shows).
        super().on_live_failed()

    # ---- dock --------------------------------------------------------------
    def build_dock(self, dock_layout: QVBoxLayout) -> None:
        amount = self.section("Amount")
        self.column_picker = self.add_picker(
            "amount_column", "Column", "Benford Column Changed"
        )
        amount.addWidget(FormRow("Column", self.column_picker, label_width=64))
        dock_layout.addWidget(amount)

        test = self.section("Test")
        self.digits_control = self.add_segment(
            "digits", _DIGIT_OPTIONS, "Benford Digits Changed"
        )
        self.digits_control.setToolTip("Test the first digit or the first two digits")
        self.min_spin = self.add_dspin(
            "min_abs_amount",
            "Benford Minimum Changed",
            minimum=0.0,
            maximum=1e12,
            decimals=2,
        )
        self.min_spin.setToolTip(
            "Amounts smaller than this (in either sign) are not tested"
        )
        self.min_spin.setAccessibleName("Minimum amount")
        test.addWidget(FormRow("Digits", self.digits_control, label_width=64))
        test.addWidget(FormRow("Minimum", self.min_spin, label_width=64))
        dock_layout.addWidget(test)

        result = self.section("Result")
        self.chart = BenfordChartWidget()
        result.addWidget(self.chart)
        self.summary_label = self._hint_label()
        self.chi_label = self._hint_label()
        result.addWidget(self.summary_label)
        result.addWidget(self.chi_label)
        dock_layout.addWidget(result)

        drill = self.section("Drill-down digits")
        self.drill_auto_check = self.add_check(
            "drill_auto",
            "Digits that stand out (automatic)",
            "Benford Drill-down Mode Changed",
        )
        self.drill_list = self.add_digits(
            "drill_digits",
            "Benford Drill-down Digits Changed",
            digit_range(self.digits),
            label_fn=self._digit_label,
            max_height=200,
        )
        self.drill_list.setAccessibleName("Drill-down digits")
        self.drill_list.setToolTip("Digits whose rows go to the drill-down output")
        drill.addWidget(self.drill_auto_check)
        drill.addWidget(self.drill_list)
        dock_layout.addWidget(drill)
        dock_layout.addStretch()

    @staticmethod
    def _hint_label() -> QLabel:
        label = QLabel("")
        label.setObjectName("FieldHint")
        label.setWordWrap(True)
        return label

    def _digit_label(self, key: Any) -> str:
        digit = int(key)
        result = getattr(self, "last_result", None)
        chart = result.extras.get("chart") if result is not None else None
        if chart is None or digit not in chart.digits:
            return str(digit)
        i = chart.digits.index(digit)
        return f"{digit}   z {chart.z[i]:.1f}   {chart.counts[i]:,} rows"

    def _apply_visibility(self) -> None:
        """The checklist matches the digit mode and is live only for manual drill-down."""
        checklist = self.drill_list
        if checklist is None:
            return
        try:
            wanted = [str(d) for d in digit_range(self.digits)]
            if list(checklist.checkboxes) != wanted:
                checklist.setColumns(wanted, [str(d) for d in self.drill_digits])
            for key, box in checklist.checkboxes.items():
                box.setText(self._digit_label(key))
            checklist.setEnabled(not self.drill_auto)
        except RuntimeError:  # dock rebuilt
            self.drill_list = None

    def _sync_widgets_from_model(self) -> None:
        self._apply_visibility()  # rebuild the digit rows before values are written
        super()._sync_widgets_from_model()

    # ---- live result -> chart and text ----------------------------------------
    def _show_summary(self) -> None:
        super()._show_summary()
        result = self.last_result
        try:
            if self.chart is not None:
                self.chart.set_data(
                    result.extras["chart"] if result is not None else None
                )
            if self.chi_label is not None:
                self.chi_label.setText(self._chi_text(result))
        except RuntimeError:  # dock rebuilt
            self.chart = self.chi_label = None
        self._apply_visibility()

    @staticmethod
    def _chi_text(result: AuditResult | None) -> str:
        stats = result.extras["stats"] if result is not None else None
        if not stats or stats["chi_square"] is None:
            return ""
        return (
            f"Chi-square {stats['chi_square']:.2f} (df {stats['df']}), "
            f"p = {stats['p_value']:.4g}"
        )

    def on_result(self, result: AuditResult) -> None:
        super().on_result(result)  # fills test_summary (LIVE_SUMMARY)
        self._show_summary()

    def set_setting(self, name: str, value: Any, *args: Any, **kwargs: Any) -> bool:
        changed = super().set_setting(name, value, *args, **kwargs)
        if changed:
            self._show_summary()  # also covers a failed evaluation (no result)
        return changed

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        self.chart = self.chi_label = self.drill_list = None
        super().create_layout(dock_layout)


@register_node(AuditNodes.BENFORD, NodeTypes.AUDIT)
class TriggerNode_Benford(AuditNode):
    icon = "node_benford"
    node_code = AuditNodes.BENFORD
    node_type = NodeTypes.AUDIT
    node_title = "Benford"
    content_class = BenfordContent
    OUTPUT_TYPES = (3, 1, 3)
    output_text = ("T", "S", "D")
    content_label_objname = "trigger_node_benford"
    style = {}  # noqa: RUF012 - shared empty node style


__all__ = ["BenfordContent", "TriggerNode_Benford"]
