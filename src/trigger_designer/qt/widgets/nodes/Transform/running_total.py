"""Running Total node: Qt wrapper only; the logic is core/shaping/running_total.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    TransformNodes,
    register_node,
)
from trigger_designer.core.shaping import running_total as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


class RunningTotalContent(ShapingContent):
    """Cumulative sums for selected numeric columns, optionally per group."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.running_total"
    OUTPUT_KINDS = ("running_total",)
    INPUTS = 1
    HISTORY = "Running Total"
    SUMMARY = "cumulative sums"
    FORM = (
        FormSection(
            "Running totals",
            (
                Field("sum_columns", "Sum", "columns", filter="numeric"),
                Field("group_by_columns", "Group by", "columns"),
            ),
            info="Each selected sum column becomes RunTot_<column>.",
        ),
    )

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        # Keep the generated variable name the old node used.
        self.output_variables = [f"var_runtot_{self.id}"]
        self.variable_name = self.output_variables[0]

    def dock_summary(self) -> str:
        sums = len(self.settings.get("sum_columns") or [])
        groups = len(self.settings.get("group_by_columns") or [])
        return (
            f"{sums} sum{'' if sums == 1 else 's'} \u00b7 "
            f"{groups} group{'' if groups == 1 else 's'}"
        )


@register_node(TransformNodes.RUNNING_TOTAL, NodeTypes.TRANSFORM)
class TriggerNode_RunningTotal(ShapingNode):
    icon = "node_running_total"
    node_code = TransformNodes.RUNNING_TOTAL
    node_type = NodeTypes.TRANSFORM
    node_title = "Running Total"
    content_class = RunningTotalContent
    output_text = ("Out",)
    content_label_objname = "trigger_node_running_total"
    style = {}  # noqa: RUF012 - shared empty node style
