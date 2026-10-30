"""Fuzzy Match node: Qt wrapper around core/shaping/fuzzy.py."""

from typing import Any

from qtpy.QtWidgets import QDoubleSpinBox, QWidget

from trigger_designer.core.node_configuration import (
    JoinNodes,
    NodeTypes,
    register_node,
)
from trigger_designer.core.shaping import fuzzy as core
from trigger_designer.core.shaping.common import LIVE_SAMPLE_ROWS
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


def _block_summary(item: dict) -> str:
    return f"{item.get('left') or 'Left'} = {item.get('right') or 'Right'}"


class FuzzyMatchContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.fuzzy"
    OUTPUT_KINDS = ("fuzzy_matched", "fuzzy_left", "fuzzy_right")
    INPUTS = 2
    HISTORY = "Fuzzy Match"
    SUMMARY = "M matched · L left · R right"
    FORM = (
        FormSection(
            "Compare",
            (
                Field(
                    "text_pair",
                    "",
                    "pair",
                    items=(
                        Field(
                            "left_column",
                            "Left text",
                            "column",
                            input=0,
                            filter="text",
                        ),
                        Field(
                            "right_column",
                            "Right text",
                            "column",
                            input=1,
                            filter="text",
                        ),
                    ),
                ),
                Field(
                    "algorithm",
                    "Algorithm",
                    "combo",
                    options=(
                        ("jaro_winkler", "Jaro-Winkler"),
                        ("levenshtein", "Levenshtein ratio"),
                    ),
                ),
                Field(
                    "threshold",
                    "Minimum score",
                    "float",
                    minimum=0.01,
                    maximum=1.0,
                    hint="1.0 is identical; pairs scoring below are dropped.",
                ),
                Field("strip_suffixes", "Ignore Inc/Ltd/LLC", "check"),
                Field(
                    "assignment",
                    "Pairs",
                    "combo",
                    options=(
                        ("one_to_one", "One to one"),
                        ("best_per_left", "Best per left row"),
                        ("all_pairs", "All pairs"),
                    ),
                ),
                Field(
                    "_compare_hint",
                    "Text is lower-cased and punctuation is ignored before "
                    "comparing. Empty text never matches.",
                    "note",
                ),
            ),
        ),
        FormSection(
            "Speed",
            (
                Field(
                    "blocking",
                    "Block on",
                    "combo",
                    options=(
                        ("prefix", "First characters"),
                        ("first_token", "First word"),
                        ("none", "Nothing (small data)"),
                    ),
                ),
                Field(
                    "prefix_length",
                    "Characters",
                    "int",
                    minimum=1,
                    maximum=10,
                    show_if=lambda s: s["blocking"] == "prefix",
                ),
                Field(
                    "block_columns",
                    "Must also match",
                    "list",
                    max_items=core.MAX_BLOCK_COLUMNS,
                    summary=_block_summary,
                    item_default={"left": "", "right": ""},
                    items=(
                        Field(
                            "block_pair",
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
                    "_speed_hint",
                    "Only rows that share the block are compared, which keeps "
                    "large inputs fast. Extra columns are trimmed and compared "
                    "as lower-case text.",
                    "note",
                ),
            ),
        ),
        FormSection(
            "Limits & output",
            (
                Field(
                    "_limits",
                    "Up to 5,000,000 candidate pairs (1,000,000 with no blocking). "
                    f"The live preview uses the first {LIVE_SAMPLE_ROWS} rows of "
                    "each input; Run gives the full result.",
                    "note",
                ),
            ),
            info="Candidate and live-preview safeguards.",
            collapsible=True,
            collapsed=True,
        ),
    )

    def _make_widget(self, spec: Field, value: Any, commit: Any) -> QWidget:
        widget = super()._make_widget(spec, value, commit)
        if isinstance(widget, QDoubleSpinBox):
            widget.setSingleStep(0.01)
        return widget


@register_node(JoinNodes.FUZZY_MATCH, NodeTypes.JOIN)
class TriggerNode_FuzzyMatch(ShapingNode):
    icon = "node_fuzzy_match"
    node_code = JoinNodes.FUZZY_MATCH
    node_type = NodeTypes.JOIN
    node_title = "Fuzzy Match"
    content_class = FuzzyMatchContent
    output_text = ("M", "L", "R")
    content_label_objname = "trigger_node_fuzzy_match"
