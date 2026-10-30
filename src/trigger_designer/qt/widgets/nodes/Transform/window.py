"""Window node: Qt wrapper around core/shaping/window.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    TransformNodes,
    register_node,
)
from trigger_designer.core.shaping import window as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)

_OP_LABELS = {
    "lag": "Previous row (lag)",
    "lead": "Next row (lead)",
    "row_number": "Row number",
    "rank": "Rank",
    "dense_rank": "Dense rank",
    "cum_sum": "Running sum",
    "cum_min": "Running min",
    "cum_max": "Running max",
    "cum_mean": "Running mean",
    "rolling_sum": "Rolling sum",
}
_STEP = {"lag", "lead"}
_RANKS = {"rank", "dense_rank"}
_RUNNING = {"cum_sum", "cum_min", "cum_max", "cum_mean", "rolling_sum"}


def _order_summary(item: dict) -> str:
    column = item.get("column") or "Column"
    direction = "Z → A" if item.get("descending") else "A → Z"
    return f"{column} · {direction}"


def _op_summary(item: dict) -> str:
    op = str(item.get("op") or "lag")
    label = _OP_LABELS.get(op, op)
    if op == "row_number":
        return label
    return f"{label} · {item.get('source') or 'Column'}"


class WindowContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.window"
    OUTPUT_KINDS = ("window",)
    HISTORY = "Window"
    SUMMARY = "one column per calculation"
    FORM = (
        FormSection(
            "Window",
            (
                Field("partition_by", "Restart per", "picker"),
                Field(
                    "order_by",
                    "Order by",
                    "list",
                    item_default={"column": "", "descending": False},
                    summary=_order_summary,
                    items=(
                        Field("column", "Column", "column"),
                        Field("descending", "Descending", "check"),
                    ),
                ),
                Field(
                    "_order_hint",
                    "Rows keep input order. Order only decides which row is previous or next.",
                    "note",
                ),
            ),
        ),
        FormSection(
            "Calculations",
            (
                Field(
                    "ops",
                    "Calculation",
                    "list",
                    collapsible=True,
                    summary=_op_summary,
                    item_default={
                        "op": "lag",
                        "source": "",
                        "name": "",
                        "offset": 1,
                        "window": 3,
                        "partial": False,
                        "descending": False,
                        "nulls": "skip",
                    },
                    items=(
                        Field(
                            "op_name",
                            "",
                            "pair",
                            items=(
                                Field(
                                    "op",
                                    "Calculation",
                                    "combo",
                                    rebuild_on_change=True,
                                    options=tuple(
                                        (op, _OP_LABELS[op]) for op in core.OPS
                                    ),
                                ),
                                Field(
                                    "name",
                                    "Output name",
                                    "text",
                                    placeholder="Auto",
                                ),
                            ),
                        ),
                        Field(
                            "source",
                            "Column",
                            "column",
                            show_if=lambda item: item.get("op") != "row_number",
                        ),
                        Field(
                            "offset",
                            "Offset",
                            "int",
                            minimum=1,
                            maximum=100_000,
                            show_if=lambda item: item.get("op") in _STEP,
                        ),
                        Field(
                            "window",
                            "Window rows",
                            "int",
                            minimum=1,
                            maximum=100_000,
                            show_if=lambda item: item.get("op") == "rolling_sum",
                        ),
                        Field(
                            "partial",
                            "Allow partial window",
                            "check",
                            show_if=lambda item: item.get("op") == "rolling_sum",
                        ),
                        Field(
                            "descending",
                            "Rank high to low",
                            "check",
                            show_if=lambda item: item.get("op") in _RANKS,
                        ),
                        Field(
                            "nulls",
                            "Nulls",
                            "combo",
                            options=(("skip", "Skip"), ("zero", "Treat as 0")),
                            show_if=lambda item: item.get("op") in _RUNNING,
                        ),
                    ),
                ),
                Field(
                    "_calc_hint",
                    "Only fields used by the chosen calculation are shown.",
                    "note",
                ),
            ),
        ),
    )


@register_node(TransformNodes.WINDOW, NodeTypes.TRANSFORM)
class TriggerNode_Window(ShapingNode):
    icon = "node_window"
    node_code = TransformNodes.WINDOW
    node_type = NodeTypes.TRANSFORM
    node_title = "Window"
    content_class = WindowContent
    content_label_objname = "trigger_node_window"
