"""Reconcile node: Qt wrapper around core/shaping/reconcile.py."""

from trigger_designer.core.node_configuration import (
    JoinNodes,
    NodeTypes,
    register_node,
)
from trigger_designer.core.shaping import reconcile as core
from trigger_designer.core.shaping.common import LIVE_SAMPLE_ROWS
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


def _key_summary(item: dict) -> str:
    return f"{item.get('left') or 'Left'} = {item.get('right') or 'Right'}"


class ReconcileContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.reconcile"
    OUTPUT_KINDS = ("recon_matched", "recon_left", "recon_right", "recon_summary")
    INPUTS = 2
    HISTORY = "Reconcile"
    SUMMARY = "M matched \u00b7 L left \u00b7 R right \u00b7 S summary"
    FORM = (
        FormSection(
            "Match",
            (
                Field(
                    "match_type",
                    "Match type",
                    "segment",
                    options=(
                        ("one_to_one", "1 : 1"),
                        ("one_to_many", "1 : N"),
                        ("many_to_one", "N : 1"),
                        ("many_to_many", "N : N"),
                    ),
                ),
                Field(
                    "_match_hint",
                    "Match type controls how many times each side may be used.",
                    "note",
                ),
                Field(
                    "key_pairs",
                    "Key pairs",
                    "list",
                    max_items=10,
                    summary=_key_summary,
                    item_default={"left": "", "right": ""},
                    items=(
                        Field(
                            "key_pair",
                            "",
                            "pair",
                            items=(
                                Field("left", "Left column", "column", input=0),
                                Field("right", "Right column", "column", input=1),
                            ),
                        ),
                    ),
                ),
                Field(
                    "_key_hint",
                    "Keys are trimmed and compared as lower-case text. Null keys never match.",
                    "note",
                ),
            ),
        ),
        FormSection(
            "Amount",
            (
                Field(
                    "amount_pair",
                    "",
                    "pair",
                    items=(
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
                    ),
                ),
                Field(
                    "tolerance_pair",
                    "",
                    "pair",
                    items=(
                        Field(
                            "tolerance_mode",
                            "Tolerance",
                            "segment",
                            options=(
                                ("absolute", "Amount"),
                                ("percent", "Percent"),
                            ),
                        ),
                        Field(
                            "tolerance",
                            "Value",
                            "float",
                            minimum=0,
                            maximum=1e9,
                            step=0.01,
                            decimals=2,
                        ),
                    ),
                ),
                Field(
                    "_amount_hint",
                    "Leave both amounts blank to skip amount matching. Percent is of the left amount.",
                    "note",
                ),
            ),
        ),
        FormSection(
            "Date window",
            (
                Field(
                    "date_pair",
                    "",
                    "pair",
                    show_if=lambda s: s["match_type"] != "many_to_many",
                    items=(
                        Field(
                            "date_left",
                            "Left date",
                            "column",
                            input=0,
                            blank=True,
                            filter="date",
                        ),
                        Field(
                            "date_right",
                            "Right date",
                            "column",
                            input=1,
                            blank=True,
                            filter="date",
                        ),
                    ),
                ),
                Field(
                    "date_window_days",
                    "Window (days)",
                    "int",
                    maximum=3650,
                    hint="Leave both dates blank to skip date matching.",
                    show_if=lambda s: s["match_type"] != "many_to_many",
                ),
            ),
        ),
        FormSection(
            "Limits & output",
            (
                Field(
                    "_limits",
                    "Up to 5,000,000 candidate pairs. The live preview uses the first "
                    f"{LIVE_SAMPLE_ROWS} rows of each input; Run gives the full result.",
                    "note",
                ),
            ),
            info="Candidate and live-preview safeguards.",
            collapsible=True,
            collapsed=True,
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
