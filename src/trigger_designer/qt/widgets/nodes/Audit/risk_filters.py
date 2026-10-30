"""Risk Filters node: seven journal-entry risk indicators, one Flagged output.

The settings model, evaluation, undo, Run code and the Result text all come from
``Audit/_base.py``; this file declares the sockets and the dock. Each risk test has
its own section: a switch, the test's options and its weight. The options of a test
that is switched off stay in the model (and visible but disabled), so turning a
test off and on again loses nothing.
"""

from __future__ import annotations

from qtpy.QtWidgets import QSpinBox, QVBoxLayout, QWidget

from trigger_designer.core.audit.common import SUPPORTED_DATE_FORMATS
from trigger_designer.core.audit.risk_filters import (
    LABELS,
    TEST_IDS,
    RiskParams,
    run_risk_filters,
)
from trigger_designer.core.node_configuration import (
    AuditNodes,
    NodeTypes,
    register_node,
)
from trigger_designer.qt.widgets.common import CONTROL_H, FormRow
from trigger_designer.qt.widgets.nodes.Audit._base import AuditContent, AuditNode

_DATE_FORMAT_LABELS = {
    "%Y-%m-%d": "2024-03-31 (year-month-day)",
    "%d/%m/%Y": "31/03/2024 (day/month/year)",
    "%m/%d/%Y": "03/31/2024 (month/day/year)",
    "%d-%m-%Y": "31-03-2024 (day-month-year)",
    "%Y%m%d": "20240331 (compact)",
}
_LABEL_WIDTH = 78


class RiskFiltersContent(AuditContent):
    PARAMS = RiskParams
    RUN = staticmethod(run_risk_filters)
    OP = "audit.risk_filters"
    TEST_NAME = "Risk Filters"
    OUTPUT_KINDS = ("riskflag", "risknone", "risksum")
    SUMMARY_INDEX = 2
    EXCEPTIONS_INDEX = 0
    HISTORY = "Risk Setting Changed"

    def __init__(self, node, parent: QWidget | None = None) -> None:
        super().__init__(node, parent)
        #: test id -> the option rows that are disabled while its switch is off
        self._test_bodies: dict[str, list[QWidget]] = {}
        self._weight_spins: dict[str, QSpinBox] = {}

    # ---- dock ---------------------------------------------------------------
    def build_dock(self, dock_layout: QVBoxLayout) -> None:
        self._test_bodies = {}
        self._weight_spins = {}
        columns = self.section("Columns")
        self.date_picker = self.add_picker(
            "date_column", "Posting date", "Risk Date Column Changed"
        )
        self.effective_picker = self.add_picker(
            "effective_date_column",
            "Effective date",
            "Risk Effective Column Changed",
            blank=True,
            placeholder="None (optional)",
        )
        self.amount_picker = self.add_picker(
            "amount_column", "Amount", "Risk Amount Column Changed"
        )
        self.description_picker = self.add_picker(
            "description_column", "Description", "Risk Description Column Changed"
        )
        self.manual_picker = self.add_picker(
            "manual_column", "Manual flag", "Risk Manual Column Changed"
        )
        self.format_combo = self.add_combo(
            "date_format",
            tuple((f, _DATE_FORMAT_LABELS[f]) for f in SUPPORTED_DATE_FORMATS),
            "Risk Date Format Changed",
            tip="How dates stored as text are written",
        )
        for label, widget in (
            ("Posting date", self.date_picker),
            ("Effective", self.effective_picker),
            ("Amount", self.amount_picker),
            ("Description", self.description_picker),
            ("Manual flag", self.manual_picker),
            ("Date format", self.format_combo),
        ):
            columns.addWidget(FormRow(label, widget, label_width=_LABEL_WIDTH))
        dock_layout.addWidget(columns)

        self.holidays_edit = self.add_lines(
            "holidays", "Risk Holiday Dates Changed", placeholder="2024-12-25"
        )
        self.round_spin = self.add_spin(
            "round_multiple", "Risk Round Multiple Changed", minimum=1
        )
        self.limits_edit = self.add_text(
            "approval_limits",
            "Risk Approval Limits Changed",
            kind="numlist",
            placeholder="5000, 10000",
        )
        self.below_spin = self.add_dspin(
            "below_pct", "Risk Below Percent Changed", minimum=0.1, maximum=99.9
        )
        self.below_spin.setSuffix(" %")
        self.keywords_edit = self.add_lines(
            "keywords", "Risk Keywords Changed", placeholder="reversal"
        )
        self.period_edit = self.add_text(
            "period_end", "Risk Period End Changed", placeholder="2024-03-31"
        )
        self.manual_values_edit = self.add_lines(
            "manual_values", "Risk Manual Values Changed", placeholder="manual"
        )
        options: dict[str, list[tuple[str, QWidget]]] = {
            "weekend": [],
            "holiday": [("Dates", self.holidays_edit)],
            "round_amount": [("Multiple of", self.round_spin)],
            "just_below_limit": [
                ("Limits", self.limits_edit),
                ("Within", self.below_spin),
            ],
            "keyword": [("Words", self.keywords_edit)],
            "after_period_end": [("Period end", self.period_edit)],
            "manual_journal": [("Values", self.manual_values_edit)],
        }
        self.switches = {}
        for test in TEST_IDS:
            section = self.section(LABELS[test])
            switch = self.add_check(test, "Enabled", f"Risk {LABELS[test]} Changed")
            self.switches[test] = switch
            switch.setToolTip(f"Flag entries: {LABELS[test].lower()}")
            section.addWidget(FormRow("", switch, label_width=_LABEL_WIDTH))
            body: list[QWidget] = []
            for label, widget in options[test]:
                row = FormRow(label, widget, label_width=_LABEL_WIDTH)
                section.addWidget(row)
                body.append(row)
            weight = self._make_weight_spin(test)
            row = FormRow("Weight", weight, label_width=_LABEL_WIDTH)
            section.addWidget(row)
            body.append(row)
            self._test_bodies[test] = body
            dock_layout.addWidget(section)
        dock_layout.addWidget(self.result_section())
        dock_layout.addStretch()

    def _make_weight_spin(self, test: str) -> QSpinBox:
        spin = QSpinBox()
        spin.setMinimumHeight(CONTROL_H)
        spin.setRange(1, 10)
        spin.setValue(int(self.weights.get(test, 1)))
        spin.setToolTip(f"Points added to the risk score: {LABELS[test].lower()}")
        spin.setAccessibleName(f"{LABELS[test]} weight")

        def commit(value: int, test: str = test) -> None:
            self.set_setting(
                "weights",
                {**self.weights, test: int(value)},
                "Risk Weight Changed",
                merge_key=f"{self.OP}-weights-{test}",
            )

        spin.valueChanged.connect(commit)
        self._weight_spins[test] = spin
        return spin

    # ---- model -> widgets -----------------------------------------------------
    def _sync_widgets_from_model(self) -> None:
        for test, spin in list(self._weight_spins.items()):
            try:
                want = int(self.weights.get(test, 1))
                if spin.value() != want:
                    blocked = spin.blockSignals(True)
                    try:
                        spin.setValue(want)
                    finally:
                        spin.blockSignals(blocked)
            except RuntimeError:  # dock rebuilt
                self._weight_spins.pop(test, None)
        super()._sync_widgets_from_model()

    def _apply_visibility(self) -> None:
        for test, rows in list(self._test_bodies.items()):
            on = bool(getattr(self, test))
            for row in rows:
                try:
                    row.setEnabled(on)
                except RuntimeError:  # dock rebuilt
                    self._test_bodies.pop(test, None)
                    break

    # ---- names the plan gives the outputs ---------------------------------------
    @property
    def flagged_var(self) -> str:
        return self.output_variables[0]

    @property
    def not_flagged_var(self) -> str:
        return self.output_variables[1]


@register_node(AuditNodes.RISK_FILTERS, NodeTypes.AUDIT)
class TriggerNode_RiskFilters(AuditNode):
    icon = "node_risk_filters"
    node_code = AuditNodes.RISK_FILTERS
    node_type = NodeTypes.AUDIT
    node_title = "Risk Filters"
    content_class = RiskFiltersContent
    OUTPUT_TYPES = (3, 3, 1)
    output_text = ("F", "N", "S")
    content_label_objname = "trigger_node_risk_filters"
    style = {}  # noqa: RUF012 - shared empty node style
