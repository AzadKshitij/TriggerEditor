"""Text to Columns node: Qt wrapper around core/shaping/text_to_columns.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import text_to_columns as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


def _is_columns(settings: dict) -> bool:
    return settings.get("output", "columns") == "columns"


def _is_rows(settings: dict) -> bool:
    return settings.get("output", "columns") == "rows"


class TextToColumnsContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.text_to_columns"
    OUTPUT_KINDS = ("text_to_columns",)
    HISTORY = "Text to Columns"
    SUMMARY = "text split into columns or rows"
    FORM = (
        FormSection(
            "Split",
            (
                Field(
                    "column",
                    "Column",
                    "column",
                    filter="text",
                    hint="Text columns only.",
                ),
                Field(
                    "split_mode",
                    "Split by",
                    "segment",
                    options=(("delimiter", "Delimiter"), ("regex", "Regex")),
                ),
                Field(
                    "pattern",
                    "Pattern",
                    "text",
                    placeholder=", or \\t",
                    hint="Delimiter is literal text; \\t \\n \\r \\\\ are accepted. "
                    "A regex must match at least one character.",
                ),
            ),
        ),
        FormSection(
            "Output",
            (
                Field(
                    "output",
                    "Output",
                    "segment",
                    options=(("columns", "Columns"), ("rows", "Rows")),
                ),
                Field(
                    "max_splits",
                    "Max splits",
                    "int",
                    minimum=0,
                    maximum=core.MAX_SPLITS,
                    hint="Columns: 1-49, the last column gets the remainder. "
                    "Rows: 0 means no limit.",
                ),
                Field(
                    "names",
                    "Column names",
                    "text",
                    placeholder="a, b, c",
                    show_if=_is_columns,
                    hint="Missing names become <column>_1, <column>_2 ...",
                ),
                Field(
                    "row_index_column",
                    "Piece number",
                    "text",
                    placeholder="n",
                    show_if=_is_rows,
                    hint="Optional column holding the 1-based piece number.",
                ),
            ),
        ),
        FormSection(
            "Options",
            (
                Field(
                    "trim_keep",
                    "",
                    "pair",
                    items=(
                        Field("trim", "Trim spaces", "check"),
                        Field("keep_original", "Keep original", "check"),
                    ),
                ),
                Field("skip_empty", "Skip empty", "check", show_if=_is_rows),
            ),
        ),
    )


@register_node(PreparationNodes.TEXT_TO_COLUMNS, NodeTypes.PREPARATION)
class TriggerNode_TextToColumns(ShapingNode):
    icon = "node_text_to_columns"
    node_code = PreparationNodes.TEXT_TO_COLUMNS
    node_type = NodeTypes.PREPARATION
    node_title = "Text to Columns"
    content_class = TextToColumnsContent
    content_label_objname = "trigger_node_text_to_columns"
