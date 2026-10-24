"""Select Records node: Qt wrapper around core/shaping/select_records.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import select_records as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)

_RANKED = ("largest_n", "smallest_n")


class SelectRecordsContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.select_records"
    OUTPUT_KINDS = ("records_sel", "records_rest")
    HISTORY = "Select Records"
    SUMMARY = "S selected \u00b7 R remaining"
    FORM = (
        FormSection(
            "Mode",
            (
                Field(
                    "mode",
                    "Mode",
                    "segment",
                    options=(
                        ("first_n", "First"),
                        ("last_n", "Last"),
                        ("row_range", "Range"),
                        ("largest_n", "Large"),
                        ("smallest_n", "Small"),
                    ),
                ),
                Field(
                    "_mode_hint",
                    "Only the fields used by the chosen mode appear below.",
                    "note",
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
                    "range",
                    "",
                    "pair",
                    show_if=lambda s: s["mode"] == "row_range",
                    items=(
                        Field(
                            "range_start",
                            "From row",
                            "int",
                            minimum=1,
                            maximum=100_000_000,
                        ),
                        Field(
                            "range_end",
                            "To row",
                            "int",
                            minimum=1,
                            maximum=100_000_000,
                        ),
                    ),
                ),
                Field(
                    "by",
                    "Rank by",
                    "column",
                    filter="numeric",
                    blank=True,
                    show_if=lambda s: s["mode"] in _RANKED,
                ),
                Field(
                    "ties",
                    "Ties",
                    "segment",
                    options=(
                        ("exact", "Exact N"),
                        ("include_ties", "Include ties"),
                    ),
                    show_if=lambda s: s["mode"] in _RANKED,
                ),
                Field(
                    "group_by",
                    "Per group",
                    "picker",
                    show_if=lambda s: s["mode"] != "row_range",
                ),
                Field(
                    "_range_hint",
                    "Row range is global and 1-based. Per-group selection does not apply.",
                    "note",
                    show_if=lambda s: s["mode"] == "row_range",
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
