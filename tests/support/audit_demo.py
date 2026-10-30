"""A tiny audit node built only from the shared Audit base.

Real audit nodes did not exist when the base was written, so the base tests (and any
node author who wants a working template) use this one: it flags rows whose amount is
above (or below) a threshold. It exercises every control kind the base binds.

``DemoNode`` is deliberately **not** registered (``@register_node`` is only needed for
the palette and for loading a saved file); it borrows ``AuditNodes.DUPLICATES`` as its
``node_code`` so ``serialize()`` has an op id.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl
from qtpy.QtWidgets import QVBoxLayout

from trigger_designer.core.audit.common import (
    AuditConfigError,
    AuditResult,
    ParamsBase,
    amount_expr,
    as_lazy,
    check_range,
    need,
    summary_frame,
    unreadable,
    warn_unreadable,
)
from trigger_designer.core.node_configuration import AuditNodes, NodeTypes
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.common import FormRow
from trigger_designer.qt.widgets.nodes.Audit._base import AuditContent, AuditNode


@dataclass
class DemoParams(ParamsBase):
    column: str = ""
    keys: list = field(default_factory=list)
    mode: str = "above"  # above | below
    threshold: float = 0.0
    top: int | None = None
    strict: bool = False
    levels: list = field(default_factory=list)
    sizes: list = field(default_factory=list)
    note: str = ""
    digits: list = field(default_factory=list)
    lines: list = field(default_factory=list)
    kind: str = "x"  # combo


def run_demo(frame, params: DemoParams) -> AuditResult:
    """Outputs: ``E`` exceptions, ``R`` the rest, ``S`` one-row summary."""
    lf = as_lazy(frame)
    schema = lf.collect_schema()
    need(schema, "column", params.column, "amount")
    for key in params.keys:
        need(schema, "keys", key, "key")
    check_range(params.threshold >= 0, "threshold", "Threshold", "0 or more")
    if params.mode not in ("above", "below"):
        raise AuditConfigError("TD-AUDIT-004", "Mode must be above or below.")
    parsed = amount_expr(params.column, schema[params.column])
    lf = lf.with_columns(
        parsed.alias("__td_amt"),
        unreadable(params.column, parsed).alias("__td_bad"),
    )
    hit = (
        pl.col("__td_amt") > params.threshold
        if params.mode == "above"
        else pl.col("__td_amt") < params.threshold
    )
    hit = hit.fill_null(False)
    agg = lf.select(
        pl.len().cast(pl.Int64).alias("population_rows"),
        pl.col("__td_amt").abs().sum().alias("population_value"),
        hit.sum().cast(pl.Int64).alias("exception_rows"),
        pl.col("__td_amt").abs().filter(hit).sum().alias("exception_value"),
        pl.col("__td_bad").sum().cast(pl.Int64).alias("unreadable_rows"),
    )
    status = (
        pl.when(pl.col("exception_rows") > 0)
        .then(pl.lit("fail"))
        .otherwise(pl.lit("pass"))
    )
    message = pl.format(
        "{} of {} rows are {} " + f"{params.threshold:g}.",
        pl.col("exception_rows"),
        pl.col("population_rows"),
        pl.lit(params.mode),
    )
    status, message, code = warn_unreadable(
        status, message, pl.lit(None, dtype=pl.String), "unreadable_rows", "amounts"
    )
    summary = summary_frame(
        agg,
        test_name="Demo",
        criteria=f"Amounts {params.mode} {params.threshold:g}.",
        parameters=params.to_dict(),
        status=status,
        message=message,
        code=code,
        extras=("unreadable_rows",),
    )
    drop = ["__td_amt", "__td_bad"]
    return AuditResult(
        frames=(lf.filter(hit).drop(drop), lf.filter(~hit).drop(drop), summary),
        summary_index=2,
    )


class DemoContent(AuditContent):
    PARAMS = DemoParams
    RUN = staticmethod(run_demo)
    OP = "audit.demo"
    TEST_NAME = "Demo"
    OUTPUT_KINDS = ("exc", "rest", "sum")
    SUMMARY_INDEX = 2
    EXCEPTIONS_INDEX = 0
    HISTORY = "Demo Setting Changed"

    def build_dock(self, dock_layout: QVBoxLayout) -> None:
        section = self.section("")
        self.column_picker = self.add_picker(
            "column", "Amount", "Amount Column Changed"
        )
        self.keys_picker = self.add_picker(
            "keys", "Keys", "Key Columns Changed", single=False
        )
        self.mode_control = self.add_segment(
            "mode", (("above", "Above"), ("below", "Below")), "Demo Mode Changed"
        )
        self.threshold_spin = self.add_dspin("threshold", "Demo Threshold Changed")
        self.top_spin = self.add_spin("top", "Demo Top Changed", optional="All")
        self.strict_check = self.add_check("strict", "Strict", "Demo Strict Changed")
        self.levels_edit = self.add_text(
            "levels", "Demo Levels Changed", kind="numlist", placeholder="1000, 10000"
        )
        self.sizes_edit = self.add_text(
            "sizes", "Demo Sizes Changed", kind="sizelist", placeholder="20, all"
        )
        self.note_edit = self.add_text("note", "Demo Note Changed")
        self.lines_edit = self.add_lines("lines", "Demo Lines Changed")
        self.kind_combo = self.add_combo(
            "kind", (("x", "Kind X"), ("y", "Kind Y")), "Demo Kind Changed"
        )
        self.digits_list = self.add_digits(
            "digits", "Demo Digits Changed", range(1, 10)
        )
        for label, widget in (
            ("Amount", self.column_picker),
            ("Keys", self.keys_picker),
            ("Mode", self.mode_control),
            ("Threshold", self.threshold_spin),
            ("Top", self.top_spin),
            ("", self.strict_check),
            ("Levels", self.levels_edit),
            ("Sizes", self.sizes_edit),
            ("Note", self.note_edit),
            ("Lines", self.lines_edit),
            ("Kind", self.kind_combo),
            ("Digits", self.digits_list),
        ):
            section.addWidget(FormRow(label, widget, label_width=64))
        dock_layout.addWidget(section)
        dock_layout.addWidget(self.result_section())
        dock_layout.addStretch()


class DemoNode(AuditNode):
    icon = "node_filter"
    node_code = AuditNodes.DUPLICATES
    node_type = NodeTypes.AUDIT
    node_title = "Demo"
    content_class = DemoContent
    OUTPUT_TYPES = (3, 3, 1)
    output_text = ("E", "R", "S")
    content_label_objname = "trigger_node_demo"


class FrameSource(TriggerNode):
    """Test double: emits one frame the way a File Input does."""

    node_title = "Source"

    def __init__(self, scene, frame, variable_name: str = "var_src") -> None:
        super().__init__(scene, inputs=[], outputs=[3])
        self.frame = frame
        self.variable_name = variable_name

    def evalImplementation(self):
        self.value = [{"data": self.frame, "variable_name": self.variable_name}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


def demo_graph(frame, node_cls=DemoNode):
    """``(window, source, node)``: a source wired into ``node_cls``.

    Keep ``window`` referenced for the whole test; the scene dies with it.
    """
    from nodeeditor.node_edge import Edge

    from trigger_designer.qt.design_window import TriggerSubWindow

    window = TriggerSubWindow()
    source = FrameSource(window.scene, frame)
    node = node_cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    return window, source, node


__all__ = [
    "DemoContent",
    "DemoNode",
    "DemoParams",
    "FrameSource",
    "demo_graph",
    "run_demo",
]
