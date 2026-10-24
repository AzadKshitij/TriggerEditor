"""Unpivot node: Qt wrapper around core/shaping/reshape.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    TransformNodes,
    register_node,
)
from trigger_designer.core.shaping import reshape as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


class UnpivotContent(ShapingContent):
    SETTINGS = core.UNPIVOT_DEFAULTS
    MODULE = "trigger_designer.core.shaping.reshape"
    RUNNER = "run_unpivot"
    OUTPUT_KINDS = ("unpivot",)
    HISTORY = "Unpivot"
    SUMMARY = "wide to long"
    FORM = (
        FormSection(
            "Shape",
            (
                Field("id_columns", "Keep", "picker"),
                Field("value_columns", "Unpivot", "picker"),
                Field(
                    "_unpivot_hint",
                    "Every input row becomes one row per unpivoted column. Keep the identifiers, stack the measures.",
                    "note",
                ),
            ),
        ),
        FormSection(
            "Output columns",
            (
                Field(
                    "output_names",
                    "",
                    "pair",
                    items=(
                        Field("variable_name", "Name column", "text"),
                        Field("value_name", "Value column", "text"),
                    ),
                ),
                Field(
                    "drop_nulls",
                    "Drop empty values",
                    "check",
                    hint="Off keeps null measurements. Mixed types are cast to text.",
                ),
            ),
        ),
    )


@register_node(TransformNodes.UNPIVOT, NodeTypes.TRANSFORM)
class TriggerNode_Unpivot(ShapingNode):
    icon = "node_unpivot"
    node_code = TransformNodes.UNPIVOT
    node_type = NodeTypes.TRANSFORM
    node_title = "Unpivot"
    content_class = UnpivotContent
    content_label_objname = "trigger_node_unpivot"
