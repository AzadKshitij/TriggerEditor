"""Record ID node: Qt wrapper only; the logic is core/shaping/record_id.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import record_id as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    ShapingContent,
    ShapingNode,
)


class RecordIdContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.record_id"
    OUTPUT_KINDS = ("recordid",)
    HISTORY = "Record ID"
    FORM = (
        (
            "",
            (
                Field("name", "Name", "text", placeholder="RecordID"),
                Field(
                    "start",
                    "Start at",
                    "int",
                    minimum=-1_000_000_000,
                    maximum=1_000_000_000,
                ),
                Field(
                    "position",
                    "Position",
                    "combo",
                    options=(("first", "First"), ("last", "Last")),
                ),
            ),
        ),
        (
            "Number within groups",
            (
                Field("group_by", "Groups", "columns"),
                Field(
                    "order_by",
                    "Order by",
                    "list",
                    item_default={"column": "", "descending": False},
                    items=(
                        Field("column", "Column", "column"),
                        Field("descending", "Descending", "check"),
                    ),
                ),
            ),
        ),
    )


@register_node(PreparationNodes.RECORD_ID, NodeTypes.PREPARATION)
class TriggerNode_RecordId(ShapingNode):
    icon = "node_record_id"
    node_code = PreparationNodes.RECORD_ID
    node_type = NodeTypes.PREPARATION
    node_title = "Record ID"
    content_class = RecordIdContent
    content_label_objname = "trigger_node_record_id"
