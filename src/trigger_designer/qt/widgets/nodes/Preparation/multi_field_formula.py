"""Multi-Field Formula node: Qt wrapper around core/shaping/multi_formula.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import multi_formula as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


class MultiFieldFormulaContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.multi_formula"
    OUTPUT_KINDS = ("multi_field_formula",)
    HISTORY = "Multi-Field Formula"
    SUMMARY = "one formula for many columns"
    FORM = (
        FormSection(
            "Columns",
            (
                Field(
                    "columns",
                    "Columns",
                    "columns",
                    hint="The formula runs once for each ticked column (up to 200).",
                ),
            ),
        ),
        FormSection(
            "Formula",
            (
                Field(
                    "template",
                    "Formula",
                    "textarea",
                    placeholder=("UPPER(TRIM({col}))   or   TRY_CAST({col} AS DOUBLE)"),
                    tip=(
                        "One SQL expression. {col} is replaced by each column; "
                        "{name} by the column's name as text."
                    ),
                    label_above=True,
                ),
                Field(
                    "_template_note",
                    "Use {col} for the column and {name} for its name. "
                    "One expression only: no semicolons.",
                    "note",
                ),
            ),
        ),
        FormSection(
            "Output",
            (
                Field(
                    "mode",
                    "Result",
                    "combo",
                    options=(
                        ("in_place", "Replace the columns"),
                        ("suffix", "Add new columns"),
                    ),
                ),
                Field(
                    "suffix",
                    "New column suffix",
                    "text",
                    show_if=lambda s: s.get("mode") == "suffix",
                ),
            ),
        ),
    )


@register_node(PreparationNodes.MULTI_FIELD_FORMULA, NodeTypes.PREPARATION)
class TriggerNode_MultiFieldFormula(ShapingNode):
    icon = "node_multi_field_formula"
    node_code = PreparationNodes.MULTI_FIELD_FORMULA
    node_type = NodeTypes.PREPARATION
    node_title = "Multi-Field Formula"
    content_class = MultiFieldFormulaContent
    content_label_objname = "trigger_node_multi_field_formula"
