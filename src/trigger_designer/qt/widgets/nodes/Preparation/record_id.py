"""Record ID node: Qt wrapper only; the logic is core/shaping/record_id.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import record_id as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


def _order_summary(item: dict) -> str:
    column = item.get("column") or "Column"
    direction = "Z \u2192 A" if item.get("descending") else "A \u2192 Z"
    return f"{column} \u00b7 {direction}"


class RecordIdContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.record_id"
    OUTPUT_KINDS = ("recordid",)
    HISTORY = "Record ID"
    SUMMARY = "adds Int64 IDs"
    FORM = (
        FormSection(
            "",
            (
                Field(
                    "name",
                    "Name",
                    "text",
                    placeholder="RecordID",
                    hint="Dense Int64 numbers. The column name must be new.",
                ),
                Field(
                    "start_position",
                    "",
                    "pair",
                    items=(
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
                            "segment",
                            options=(("first", "First"), ("last", "Last")),
                        ),
                    ),
                ),
            ),
        ),
        FormSection(
            "Grouping & order",
            (
                Field("group_by", "Groups", "picker"),
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
                    "Rows keep input order. This only changes the numbers.",
                    "note",
                ),
            ),
            info="Optional numbering per group or by another column.",
            collapsible=True,
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
