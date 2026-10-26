"""Normalize node: Qt wrapper only; the logic is core/shaping/normalize.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import normalize as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


class NormalizeContent(ShapingContent):
    """Column-name rules, applied in the order trim, whitespace, case."""

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.normalize"
    OUTPUT_KINDS = ("normalize",)
    INPUTS = 1
    HISTORY = "Normalize"
    SUMMARY = "column name rules"
    FORM = (
        FormSection(
            "Name rules",
            (
                Field("trim_whitespace", "Trim spaces", "check"),
                Field("spaces_to_underscore", "Spaces to underscores", "check"),
                Field("remove_all_whitespace", "Remove all whitespace", "check"),
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
            info="Applied in order: trim, whitespace, case. "
            "Remove-all wins over underscores.",
        ),
        FormSection(
            "Columns",
            (
                Field(
                    "selected_columns",
                    "Normalize",
                    "columns",
                    hint="Empty means every column.",
                ),
            ),
        ),
    )

    def _current_mapping(self) -> dict:
        """Rename map for the live schema; the upstream-rename hook."""
        return core.build_rename_mapping(
            list(self.schema(0)),
            list(self.settings.get("selected_columns") or []),
            trim_whitespace=bool(self.settings.get("trim_whitespace", True)),
            spaces_to_underscore=bool(self.settings.get("spaces_to_underscore", True)),
            remove_all_whitespace=bool(
                self.settings.get("remove_all_whitespace", False)
            ),
            case_modification=str(self.settings.get("case_modification", "none")),
        )


@register_node(PreparationNodes.NORMALIZE_COLUMNS, NodeTypes.PREPARATION)
class TriggerNode_Normalize(ShapingNode):
    icon = "node_select"
    node_code = PreparationNodes.NORMALIZE_COLUMNS
    node_type = NodeTypes.PREPARATION
    node_title = "Normalize"
    content_class = NormalizeContent
    output_text = ("Out",)
    content_label_objname = "trigger_node_normalize_columns"
    style = {}  # noqa: RUF012 - shared empty node style
