"""Select Records node: Qt wrapper around core/shaping/select_records.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import select_records as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    ShapingContent,
    ShapingNode,
)


class SelectRecordsContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.select_records"
    OUTPUT_KINDS = ("records_sel", "records_rest")
    HISTORY = "Select Records"
    FORM = (
        (
            "",
            (
                Field(
                    "mode",
                    "Mode",
                    "combo",
                    options=(
                        ("first_n", "First N rows"),
                        ("last_n", "Last N rows"),
                        ("row_range", "Row range"),
                        ("largest_n", "Largest N by column"),
                        ("smallest_n", "Smallest N by column"),
                    ),
                ),
                Field(
                    "n",
                    "N",
                    "int",
                    minimum=1,
                    maximum=100_000_000,
                    show_if=lambda s: s["mode"] != "row_range",
                ),
                Field(
                    "range_start",
                    "From row",
                    "int",
                    minimum=1,
                    maximum=100_000_000,
                    show_if=lambda s: s["mode"] == "row_range",
                ),
                Field(
                    "range_end",
                    "To row",
                    "int",
                    minimum=1,
                    maximum=100_000_000,
                    show_if=lambda s: s["mode"] == "row_range",
                ),
                Field(
                    "by",
                    "Rank by",
                    "column",
                    filter="numeric",
                    blank=True,
                    show_if=lambda s: s["mode"] in ("largest_n", "smallest_n"),
                ),
                Field(
                    "ties",
                    "Ties",
                    "combo",
                    options=(
                        ("exact", "Exactly N rows"),
                        ("include_ties", "Include ties"),
                    ),
                    show_if=lambda s: s["mode"] in ("largest_n", "smallest_n"),
                ),
                Field(
                    "group_by",
                    "Per group",
                    "columns",
                    show_if=lambda s: s["mode"] != "row_range",
                ),
            ),
        ),
    )


@register_node(PreparationNodes.SELECT_RECORDS, NodeTypes.PREPARATION)
class TriggerNode_SelectRecords(ShapingNode):
    icon = "node_select_records"
    node_code = PreparationNodes.SELECT_RECORDS
    node_type = NodeTypes.PREPARATION
    node_title = "Select Records"
    content_class = SelectRecordsContent
    output_text = ("S", "R")
    content_label_objname = "trigger_node_select_records"
