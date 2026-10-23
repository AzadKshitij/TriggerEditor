"""Unpivot node: Qt wrapper around core/shaping/reshape.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    TransformNodes,
    register_node,
)
from trigger_designer.core.shaping import reshape as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    ShapingContent,
    ShapingNode,
)


class UnpivotContent(ShapingContent):
    SETTINGS = core.UNPIVOT_DEFAULTS
    MODULE = "trigger_designer.core.shaping.reshape"
    RUNNER = "run_unpivot"
    OUTPUT_KINDS = ("unpivot",)
    HISTORY = "Unpivot"
    FORM = (
        (
            "",
            (
                Field("id_columns", "Keep columns", "columns"),
                Field("value_columns", "Unpivot columns", "columns"),
                Field("variable_name", "Name column", "text"),
                Field("value_name", "Value column", "text"),
                Field("drop_nulls", "Drop empty values", "check"),
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
