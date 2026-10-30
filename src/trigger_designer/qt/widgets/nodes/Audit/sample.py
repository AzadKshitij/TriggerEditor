"""Sample node: draw a sample a reviewer can redraw.

``S`` the sampled rows, ``N`` the rest (both in input order), ``L`` the Selection
log that lets a reviewer re-perform the draw. The logic is ``core/audit/sampling.py``;
this module is the dock and the sockets.

Live evaluation. Upstream nodes pass only their leading rows while you edit (File
Input and the shaping nodes trim their output), so the draw normally runs on a
small preview. An input that still arrives with more than ``LIVE_ROW_LIMIT`` rows
is not drawn live (the draw sorts the population on the GUI thread): the node
shows empty outputs and a tooltip until you Run. Run always draws the whole input.
"""

from __future__ import annotations

import time

import polars as pl
from qtpy.QtWidgets import QVBoxLayout

from trigger_designer.core.audit.common import AuditResult
from trigger_designer.core.audit.sampling import (
    KEY_TIP,
    SamplingParams,
    run_sample,
    sample_test_summary,
)
from trigger_designer.core.audit.test_summary import TestSummary
from trigger_designer.core.node_configuration import (
    AuditNodes,
    NodeTypes,
    register_node,
)
from trigger_designer.qt.widgets.common import FormRow, IconButton
from trigger_designer.qt.widgets.nodes.Audit._base import AuditContent, AuditNode

NEW_SEED_TOOLTIP = "New random seed"
SEED_MAX_SPIN = 2_147_483_647
METHOD_OPTIONS = (
    ("random", "Random"),
    ("systematic", "Systematic"),
    ("mus", "Monetary unit"),
    ("stratified", "Stratified"),
)
SIZE_KIND_OPTIONS = (("count", "Count"), ("percent", "Percent"))
LABEL_W = 64


class SampleContent(AuditContent):
    PARAMS = SamplingParams
    RUN = staticmethod(run_sample)
    OP = "audit.sample"
    TEST_NAME = "Sample"
    OUTPUT_KINDS = ("sample", "notsampled", "samplelog")
    SUMMARY_INDEX = 2  # the Selection log plays the Summary's part
    EXCEPTIONS_INDEX = 0
    LIVE_SUMMARY = True
    HISTORY = "Sample Setting Changed"

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        self._rows: dict[str, FormRow] = {}
        self._size_section = None
        self._strata_section = None

    # ---- live evaluation ---------------------------------------------------
    def build_result(self) -> AuditResult:
        return run_sample(self.incom_data, self.params(), live=True)

    # ---- summary -----------------------------------------------------------
    def summary_from_frame(self, log: pl.DataFrame) -> TestSummary | None:
        """The Selection log has one row per scope (a stratified draw has several)."""
        if log.is_empty():
            return None
        return sample_test_summary(
            log,
            self.params(),
            node_id=getattr(self.node, "id", None),
            sample_var=self.exceptions_var_name(),
        )

    def format_summary(self, summary: TestSummary) -> str:
        text = summary.message
        interval = summary.details.get("interval")
        if interval is not None:
            text += f" Interval {interval:,.2f}."
        log = summary.details.get("selection_log") or []
        note = (log[0].get("note") if log else "") or ""
        return f"{text} {note}".strip()

    # ---- dock --------------------------------------------------------------
    def _row(self, name: str, label: str, widget, **kwargs) -> FormRow:
        row = FormRow(label, widget, label_width=LABEL_W, **kwargs)
        self._rows[name] = row
        return row

    def build_dock(self, dock_layout: QVBoxLayout) -> None:
        self._rows = {}

        method = self.section("Method")
        self.method_combo = self.add_combo(
            "method", METHOD_OPTIONS, "Sample Method Changed"
        )
        method.addWidget(self._row("method", "Method", self.method_combo))
        dock_layout.addWidget(method)

        size = self.section("Size")
        self.size_kind_control = self.add_segment(
            "size_kind", SIZE_KIND_OPTIONS, "Sample Size Kind Changed"
        )
        self.size_spin = self.add_spin(
            "sample_size", "Sample Size Changed", minimum=1, maximum=100_000_000
        )
        self.percent_spin = self.add_dspin(
            "sample_percent", "Sample Percent Changed", minimum=0.01, maximum=100.0
        )
        self.percent_spin.setSuffix(" %")
        size.addWidget(self._row("size_kind", "Kind", self.size_kind_control))
        size.addWidget(self._row("sample_size", "Rows", self.size_spin))
        size.addWidget(self._row("sample_percent", "Percent", self.percent_spin))
        self._size_section = size
        dock_layout.addWidget(size)

        seed = self.section("Seed")
        self.seed_spin = self.add_spin(
            "seed", "Sample Seed Changed", minimum=0, maximum=SEED_MAX_SPIN
        )
        self.seed_button = IconButton.themed(
            NEW_SEED_TOOLTIP, rsm_icon=self.node.rsm.get("icon_refresh")
        )
        self.seed_button.clicked.connect(self.new_seed)
        seed.addWidget(
            self._row("seed", "Seed", self.seed_spin, action=self.seed_button)
        )
        dock_layout.addWidget(seed)

        columns = self.section("Columns")
        self.key_picker = self.add_picker(
            "key_columns",
            "Stable key",
            "Sample Key Changed",
            single=False,
            placeholder="All columns",
        )
        self.key_picker.setToolTip(KEY_TIP)
        self.amount_picker = self.add_picker(
            "amount_column",
            "Amount",
            "Sample Amount Changed",
            blank=True,
            placeholder="None",
        )
        columns.addWidget(self._row("key_columns", "Key", self.key_picker))
        columns.addWidget(self._row("amount_column", "Amount", self.amount_picker))
        dock_layout.addWidget(columns)

        strata = self.section("Strata")
        self.edges_edit = self.add_text(
            "band_edges",
            "Sample Edges Changed",
            kind="numlist",
            placeholder="1000, 10000",
        )
        self.sizes_edit = self.add_text(
            "band_sizes",
            "Sample Strata Sizes Changed",
            kind="sizelist",
            placeholder="20, 20, all",
        )
        strata.addWidget(self._row("band_edges", "Edges", self.edges_edit))
        strata.addWidget(self._row("band_sizes", "Sizes", self.sizes_edit))
        self._strata_section = strata
        dock_layout.addWidget(strata)

        dock_layout.addWidget(self.result_section(count_button=False))
        dock_layout.addStretch()

    def _apply_visibility(self) -> None:
        stratified = self.method == "stratified"
        percent = self.size_kind == "percent"
        shown = (
            (self._size_section, not stratified),
            (self._strata_section, stratified),
            (self._rows.get("sample_size"), not percent),
            (self._rows.get("sample_percent"), percent),
        )
        for widget, visible in shown:
            if widget is None:
                continue
            try:
                widget.setVisible(visible)
            except RuntimeError:  # dock rebuilt
                self._rows = {}
                self._size_section = self._strata_section = None
                return

    def new_seed(self) -> None:
        """The refresh button: a fresh seed, one undo step."""
        value = time.time_ns() % (SEED_MAX_SPIN + 1)
        if self.set_setting("seed", value, "Sample Seed Changed"):
            self._write_widget(self.seed_spin, "spin", {}, value)


@register_node(AuditNodes.SAMPLE, NodeTypes.AUDIT)
class TriggerNode_Sample(AuditNode):
    icon = "node_sample"
    node_code = AuditNodes.SAMPLE
    node_type = NodeTypes.AUDIT
    node_title = "Sample"
    content_class = SampleContent
    OUTPUT_TYPES = (3, 3, 1)
    output_text = ("S", "N", "L")
    content_label_objname = "trigger_node_sample"
