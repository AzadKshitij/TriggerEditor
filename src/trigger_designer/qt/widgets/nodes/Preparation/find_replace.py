"""Find and Replace node: Qt wrapper around core/shaping/find_replace.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import find_replace as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


def _find_summary(item: dict) -> str:
    find = str(item.get("find") or "").strip()
    replace = str(item.get("replace") or "").strip()
    mode = "regex" if item.get("mode") == "regex" else "literal"
    left = find or "Find..."
    right = replace or "blank"
    return f"{left} \u2192 {right} \u00b7 {mode}"


class FindReplaceContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.find_replace"
    OUTPUT_KINDS = ("find_replace",)
    HISTORY = "Find and Replace"
    SUMMARY = "rows in \u00b7 edited rows out"
    FORM = (
        FormSection(
            "Columns",
            (
                Field(
                    "columns",
                    "Columns",
                    "picker",
                    filter="text",
                    hint="Text columns only. A numeric column is rejected.",
                ),
            ),
        ),
        FormSection(
            "Rules",
            (
                Field(
                    "rules",
                    "Rule",
                    "list",
                    max_items=50,
                    collapsible=True,
                    summary=_find_summary,
                    item_default={
                        "find": "",
                        "replace": "",
                        "mode": "literal",
                        "case_sensitive": False,
                        "whole_cell": False,
                        "enabled": True,
                    },
                    items=(
                        Field(
                            "find_replace",
                            "",
                            "pair",
                            items=(
                                Field("find", "Find", "text"),
                                Field("replace", "Replace", "text"),
                            ),
                        ),
                        Field(
                            "mode_enabled",
                            "",
                            "pair",
                            items=(
                                Field(
                                    "mode",
                                    "Mode",
                                    "segment",
                                    options=(
                                        ("literal", "Literal"),
                                        ("regex", "Regex"),
                                    ),
                                ),
                                Field("enabled", "On", "check"),
                            ),
                        ),
                        Field(
                            "options",
                            "",
                            "pair",
                            items=(
                                Field("case_sensitive", "Match case", "check"),
                                Field("whole_cell", "Whole cell", "check"),
                            ),
                        ),
                    ),
                ),
                Field(
                    "_rule_order",
                    "Rules run top to bottom. Each rule sees the previous result.",
                    "note",
                ),
            ),
        ),
        FormSection(
            "Output",
            (
                Field(
                    "suffix",
                    "Output",
                    "suffix",
                    hint="Keep original writes to a new suffixed column.",
                ),
            ),
        ),
    )


@register_node(PreparationNodes.FIND_REPLACE, NodeTypes.PREPARATION)
class TriggerNode_FindReplace(ShapingNode):
    icon = "node_find_replace"
    node_code = PreparationNodes.FIND_REPLACE
    node_type = NodeTypes.PREPARATION
    node_title = "Find and Replace"
    content_class = FindReplaceContent
    content_label_objname = "trigger_node_find_replace"
