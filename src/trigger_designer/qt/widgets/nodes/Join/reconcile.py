"""Reconcile node: Qt wrapper around core/shaping/reconcile.py."""

from trigger_designer.core.node_configuration import (
    JoinNodes,
    NodeTypes,
    register_node,
)
from trigger_designer.core.shaping import reconcile as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    ShapingContent,
    ShapingNode,
)


class ReconcileContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.reconcile"
    OUTPUT_KINDS = ("recon_matched", "recon_left", "recon_right", "recon_summary")
    INPUTS = 2
    LIVE_CAP_ROWS = 200_000
    HISTORY = "Reconcile"
    FORM = (
        (
            "Match",
            (
                Field(
                    "match_type",
                    "Match type",
                    "combo",
                    options=(
                        ("one_to_one", "One to one"),
                        ("one_to_many", "One left to many right"),
                        ("many_to_one", "Many left to one right"),
                        ("many_to_many", "Many to many (group totals)"),
                    ),
                ),
                Field(
                    "key_pairs",
                    "Key",
                    "list",
                    max_items=10,
                    item_default={"left": "", "right": ""},
                    items=(
                        Field("left", "Left column", "column", input=0),
                        Field("right", "Right column", "column", input=1),
                    ),
                ),
            ),
        ),
        (
            "Amount",
            (
                Field(
                    "amount_left",
                    "Left amount",
                    "column",
                    input=0,
                    blank=True,
                    filter="numeric",
                ),
                Field(
                    "amount_right",
                    "Right amount",
                    "column",
                    input=1,
                    blank=True,
                    filter="numeric",
                ),
                Field(
                    "tolerance_mode",
                    "Tolerance",
                    "combo",
                    options=(("absolute", "Amount"), ("percent", "Percent of left")),
                ),
                Field(
                    "tolerance",
                    "Tolerance value",
                    "float",
                    minimum=0,
                    maximum=1e9,
                ),
            ),
        ),
        (
            "Date",
            (
                Field(
                    "date_left",
                    "Left date",
                    "column",
                    input=0,
                    blank=True,
                    filter="date",
                    show_if=lambda s: s["match_type"] != "many_to_many",
                ),
                Field(
                    "date_right",
                    "Right date",
                    "column",
                    input=1,
                    blank=True,
                    filter="date",
                    show_if=lambda s: s["match_type"] != "many_to_many",
                ),
                Field(
                    "date_window_days",
                    "Window (days)",
                    "int",
                    maximum=3650,
                    show_if=lambda s: s["match_type"] != "many_to_many",
                ),
            ),
        ),
    )


@register_node(JoinNodes.RECONCILE, NodeTypes.JOIN)
class TriggerNode_Reconcile(ShapingNode):
    icon = "node_reconcile"
    node_code = JoinNodes.RECONCILE
    node_type = NodeTypes.JOIN
    node_title = "Reconcile"
    content_class = ReconcileContent
    output_text = ("M", "L", "R", "S")
    content_label_objname = "trigger_node_reconcile"
