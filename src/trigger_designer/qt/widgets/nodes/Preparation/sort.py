"""Sort node: Qt wrapper only; the logic is core/shaping/sort.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import sort as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


class SortContent(ShapingContent):
    """Ordered sort keys, applied in card order."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.sort"
    OUTPUT_KINDS = ("sort",)
    INPUTS = 1
    HISTORY = "Sort"
    SUMMARY = "sort keys"
    FORM = (
        FormSection(
            "Sort",
            (
                Field(
                    "keys",
                    "Sort keys",
                    "list",
                    max_items=10,
                    item_default={"column": "", "order": "Ascending"},
                    items=(
                        Field("column", "Column", "column"),
                        Field(
                            "order",
                            "Order",
                            "combo",
                            options=(
                                ("Ascending", "Ascending"),
                                ("Descending", "Descending"),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


@register_node(PreparationNodes.SORT, NodeTypes.PREPARATION)
class TriggerNode_Sort(ShapingNode):
    icon = "node_sort"
    node_code = PreparationNodes.SORT
    node_type = NodeTypes.PREPARATION
    node_title = "Sort"
    content_class = SortContent
    output_text = ("Out",)
    content_label_objname = "trigger_node_sort"
    style = {}  # noqa: RUF012 - shared empty node style
