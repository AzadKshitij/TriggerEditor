"""Pivot node: Qt wrapper around core/shaping/reshape.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    TransformNodes,
    register_node,
)
from trigger_designer.core.shaping import reshape as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    ShapingContent,
    ShapingNode,
)


class PivotContent(ShapingContent):
    SETTINGS = core.PIVOT_DEFAULTS
    MODULE = "trigger_designer.core.shaping.reshape"
    RUNNER = "run_pivot"
    OUTPUT_KINDS = ("pivot",)
    LIVE_CAP_ROWS = 5_000_000
    HISTORY = "Pivot"
    FORM = (
        (
            "",
            (
                Field("index_columns", "Row labels", "columns"),
                Field("header_column", "Column headers", "column"),
                Field("value_column", "Values", "column"),
                Field(
                    "aggregation",
                    "Aggregate",
                    "combo",
                    options=tuple((agg, agg.capitalize()) for agg in core.AGGS),
                ),
                Field("blank_label", "Blank header", "text"),
                Field(
                    "missing_as",
                    "Empty cells",
                    "combo",
                    options=(("null", "Blank"), ("zero", "Zero")),
                ),
            ),
        ),
    )


@register_node(TransformNodes.PIVOT, NodeTypes.TRANSFORM)
class TriggerNode_Pivot(ShapingNode):
    icon = "node_pivot"
    node_code = TransformNodes.PIVOT
    node_type = NodeTypes.TRANSFORM
    node_title = "Pivot"
    content_class = PivotContent
    content_label_objname = "trigger_node_pivot"
