"""Count node: Qt wrapper only; the logic is core/shaping/count.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    TransformNodes,
    register_node,
)
from trigger_designer.core.shaping import count as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


class CountContent(ShapingContent):
    """Row counter with no configuration; the result is the whole output."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.count"
    OUTPUT_KINDS = ("count",)
    INPUTS = 1
    HISTORY = "Count"
    SUMMARY = "row count"
    FORM = (
        FormSection(
            "",
            (
                Field(
                    "_note",
                    "No configuration. The output socket carries the row count.",
                    "note",
                ),
            ),
        ),
    )


@register_node(TransformNodes.COUNT_RECORDS, NodeTypes.TRANSFORM)
class TriggerNode_Count(ShapingNode):
    icon = "node_count"
    node_code = TransformNodes.COUNT_RECORDS
    node_type = NodeTypes.TRANSFORM
    node_title = "Count"
    content_class = CountContent
    output_text = ("Out",)
    content_label_objname = "trigger_node_count_records"
    style = {}  # noqa: RUF012 - shared empty node style
