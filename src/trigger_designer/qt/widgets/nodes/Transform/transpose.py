"""Transpose node: Qt wrapper only; the logic is core/shaping/transpose.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    TransformNodes,
    register_node,
)
from trigger_designer.core.shaping import transpose as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


class TransposeContent(ShapingContent):
    """Wide-to-long reshape: data columns become ``Name``/``Value`` rows."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.transpose"
    OUTPUT_KINDS = ("transpose",)
    INPUTS = 1
    HISTORY = "Transpose"
    SUMMARY = "wide to long"
    FORM = (
        FormSection(
            "Transpose",
            (
                Field("key_columns", "Key columns", "columns"),
                Field("data_columns", "Data columns", "columns"),
                Field(
                    "missing_action",
                    "If columns are missing",
                    "combo",
                    options=(
                        ("warn", "Warn and skip"),
                        ("error", "Error"),
                        ("ignore", "Ignore"),
                    ),
                ),
            ),
            info="Data columns become Name/Value rows; key columns repeat. "
            "No data columns passes the input through.",
        ),
    )


@register_node(TransformNodes.TRANSPOSE, NodeTypes.TRANSFORM)
class TriggerNode_Transpose(ShapingNode):
    icon = "node_transpose"
    node_code = TransformNodes.TRANSPOSE
    node_title = "Transpose"
    node_type = NodeTypes.TRANSFORM
    content_class = TransposeContent
    output_text = ("Out",)
    content_label_objname = "trigger_node_transpose"
    style = {}  # noqa: RUF012 - shared empty node style
