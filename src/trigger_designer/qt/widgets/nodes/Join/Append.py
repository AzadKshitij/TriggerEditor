"""Append node: Qt wrapper only; the logic is core/shaping/append.py."""

from trigger_designer.core.node_configuration import (
    JoinNodes,
    NodeTypes,
    register_node,
)
from trigger_designer.core.shaping import append as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


class AppendContent(ShapingContent):
    """Stack the right input's rows under the left input's rows."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.append"
    OUTPUT_KINDS = ("append",)
    INPUTS = 2
    HISTORY = "Append"
    SUMMARY = "stack two inputs"
    FORM = (
        FormSection(
            "Append",
            (
                Field(
                    "how",
                    "Method",
                    "combo",
                    options=(
                        ("diagonal_relaxed", "Diagonal (relaxed)"),
                        ("vertical", "Vertical (same columns)"),
                        ("horizontal", "Horizontal (side by side)"),
                        ("diagonal", "Diagonal (strict)"),
                    ),
                ),
            ),
            info="Vertical requires identical schemas.",
        ),
    )

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        # Keep the generated variable name the old node used.
        self.output_variables = [f"var_append_{self.id}"]
        self.variable_name = self.output_variables[0]

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        chips: list[tuple[str, str]] = [
            (str(self.settings.get("how") or "diagonal_relaxed"), "accent")
        ]
        return chips, "rows stacked, left then right"


@register_node(JoinNodes.APPEND, NodeTypes.JOIN)
class TriggerNode_Append(ShapingNode):
    icon = "node_append"
    node_code = JoinNodes.APPEND
    node_type = NodeTypes.JOIN
    node_title = "Append"
    content_class = AppendContent
    output_text = ("Out",)
    content_label_objname = "trigger_node_append"
    style = {}  # noqa: RUF012 - shared empty node style
