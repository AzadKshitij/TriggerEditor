"""Split node: Qt wrapper only; the logic is core/shaping/split.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import split as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


class SplitContent(ShapingContent):
    """Estimation/validation split, random or in input order."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.split"
    OUTPUT_KINDS = ("estimation", "validation")
    INPUTS = 1
    HISTORY = "Split"
    SUMMARY = "train/validation split"
    FORM = (
        FormSection(
            "Split",
            (
                Field(
                    "is_random",
                    "Method",
                    "combo",
                    options=((True, "Random"), (False, "Sequential")),
                ),
                Field(
                    "estimation_percent",
                    "Estimation %",
                    "int",
                    minimum=1,
                    maximum=99,
                ),
                Field(
                    "random_seed",
                    "Random seed",
                    "int",
                    minimum=0,
                    maximum=2_147_483_647,
                    show_if=lambda s: s.get("is_random"),
                ),
            ),
            info="Estimation rows first; the rest go to Validation.",
        ),
    )


@register_node(PreparationNodes.SPLIT, NodeTypes.PREPARATION)
class TriggerNode_Split(ShapingNode):
    icon = "node_split"
    node_code = PreparationNodes.SPLIT
    node_title = "Split"
    node_type = NodeTypes.PREPARATION
    content_class = SplitContent
    output_text = ("E", "V")
    content_label_objname = "trigger_node_split"
    style = {}  # noqa: RUF012 - shared empty node style
