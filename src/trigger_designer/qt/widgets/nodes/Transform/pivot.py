"""Pivot node: Qt wrapper around core/shaping/reshape.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    TransformNodes,
    register_node,
)
from trigger_designer.core.shaping import reshape as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
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
    SUMMARY = "long to wide"
    FORM = (
        FormSection(
            "Layout",
            (
                Field("index_columns", "Row labels", "picker"),
                Field("header_column", "Headers", "column"),
                Field("value_column", "Values", "column"),
                Field(
                    "_pivot_hint",
                    "One row per Row labels. Each header becomes a column; values are aggregated inside it.",
                    "note",
                ),
            ),
        ),
        FormSection(
            "Aggregation",
            (
                Field(
                    "aggregation_missing",
                    "",
                    "pair",
                    items=(
                        Field(
                            "aggregation",
                            "Function",
                            "combo",
                            options=tuple((agg, agg.capitalize()) for agg in core.AGGS),
                        ),
                        Field(
                            "missing_as",
                            "Empty cells",
                            "segment",
                            options=(("null", "Blank"), ("zero", "Zero")),
                        ),
                    ),
                ),
                Field(
                    "_agg_hint",
                    "Sum, mean, min, max and median read text as numbers. Count counts non-null values.",
                    "note",
                ),
            ),
        ),
        FormSection(
            "Naming & limits",
            (Field("blank_label", "Blank header", "text"),),
            info="Blank header label and the 500-column limit.",
            collapsible=True,
            collapsed=True,
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
