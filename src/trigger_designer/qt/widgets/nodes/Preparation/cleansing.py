"""Cleansing node: Qt wrapper only; the logic is core/shaping/cleansing.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import cleansing as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


class CleansingContent(ShapingContent):
    """Null handling and text cleanup, applied in a fixed order."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.cleansing"
    OUTPUT_KINDS = ("cleansing",)
    INPUTS = 1
    HISTORY = "Cleansing"
    SUMMARY = "nulls and text cleanup"
    FORM = (
        FormSection(
            "Fields",
            (
                Field(
                    "selected_fields",
                    "Clean",
                    "columns",
                    hint="Text rules apply only to these columns.",
                ),
            ),
            info="Order: remove nulls, replace nulls, whitespace, characters, case.",
        ),
        FormSection(
            "Nulls",
            (
                Field("remove_null_rows", "Remove all-null rows", "check"),
                Field(
                    "remove_null_rows_from_selected_columns",
                    "Remove rows null in selected",
                    "check",
                    hint="Needs at least one field above.",
                ),
                Field("remove_null_columns", "Remove all-null columns", "check"),
                Field("replace_null_strings", "Replace null text with ''", "check"),
                Field("replace_null_numbers", "Replace null numbers with 0", "check"),
            ),
        ),
        FormSection(
            "Whitespace and characters",
            (
                Field("strip_whitespace", "Trim whitespace", "check"),
                Field(
                    "normalize_spaces",
                    "Collapse inner spaces",
                    "check",
                ),
                Field("remove_all_whitespace", "Remove all whitespace", "check"),
                Field("remove_letters", "Remove letters", "check"),
                Field("remove_numbers", "Remove numbers", "check"),
                Field("remove_punctuation", "Remove punctuation", "check"),
            ),
            info="Remove-all-whitespace wins over collapsing.",
        ),
        FormSection(
            "Case",
            (
                Field(
                    "case_modification",
                    "Case",
                    "combo",
                    options=(
                        ("none", "None"),
                        ("lower", "Lower Case"),
                        ("upper", "Upper Case"),
                        ("title", "Title Case"),
                    ),
                ),
            ),
        ),
    )

    def create_layout(self, dock_layout) -> None:
        super().create_layout(dock_layout)
        self.after_change()

    def after_change(self) -> None:
        widget = self._widgets.get("remove_null_rows_from_selected_columns")
        if widget is not None:
            widget.setEnabled(bool(self.settings.get("selected_fields")))


@register_node(PreparationNodes.CLEANSING, NodeTypes.PREPARATION)
class TriggerNode_Cleansing(ShapingNode):
    icon = "node_cleanser"
    node_code = PreparationNodes.CLEANSING
    node_title = "Cleansing"
    node_type = NodeTypes.PREPARATION
    content_class = CleansingContent
    output_text = ("Out",)
    content_label_objname = "trigger_node_node_title"
    style = {}  # noqa: RUF012 - shared empty node style
