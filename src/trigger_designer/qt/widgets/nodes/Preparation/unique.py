"""Unique node: Qt wrapper only; the logic is core/shaping/unique.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import unique as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


class UniqueContent(ShapingContent):
    """De-duplicate on the selected columns and expose every duplicate row."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.unique"
    OUTPUT_KINDS = ("unique", "duplicates")
    INPUTS = 1
    HISTORY = "Unique"
    SUMMARY = "duplicate detection"
    FORM = (
        FormSection(
            "Duplicate key",
            (
                Field(
                    "selected_columns",
                    "Columns",
                    "columns",
                    hint="Rows matching on all selected columns are duplicates.",
                ),
            ),
        ),
    )

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        # Keep the generated variable names the old node used.
        self.output_variables = [
            f"var_unique_{self.id}",
            f"var_duplicate_{self.id}",
        ]
        self.variable_name = self.output_variables[0]
        self.out1_variable_name = self.output_variables[1]

    def dock_summary(self) -> str:
        selected = len(self.settings.get("selected_columns") or [])
        return f"{selected} column{'' if selected == 1 else 's'} selected"


@register_node(PreparationNodes.UNIQUE, NodeTypes.PREPARATION)
class TriggerNode_Unique(ShapingNode):
    icon = "node_unique"
    node_code = PreparationNodes.UNIQUE
    node_type = NodeTypes.PREPARATION
    node_title = "Unique"
    content_class = UniqueContent
    output_text = ("Unique", "Duplicates")
    content_label_objname = "trigger_node_unique"
    style = {}  # noqa: RUF012 - shared empty node style
