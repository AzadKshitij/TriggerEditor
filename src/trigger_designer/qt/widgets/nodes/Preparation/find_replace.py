"""Find and Replace node: Qt wrapper around core/shaping/find_replace.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import find_replace as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    ShapingContent,
    ShapingNode,
)


class FindReplaceContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.find_replace"
    OUTPUT_KINDS = ("find_replace",)
    HISTORY = "Find and Replace"
    FORM = (
        ("Columns", (Field("columns", "Columns", "columns", filter="text"),)),
        (
            "Rules",
            (
                Field(
                    "rules",
                    "Rule",
                    "list",
                    max_items=50,
                    item_default={
                        "find": "",
                        "replace": "",
                        "mode": "literal",
                        "case_sensitive": False,
                        "whole_cell": False,
                        "enabled": True,
                    },
                    items=(
                        Field("find", "Find", "text"),
                        Field("replace", "Replace", "text"),
                        Field(
                            "mode",
                            "Mode",
                            "combo",
                            options=(("literal", "Literal"), ("regex", "Regex")),
                        ),
                        Field("case_sensitive", "Match case", "check"),
                        Field("whole_cell", "Whole cell", "check"),
                        Field("enabled", "On", "check"),
                    ),
                ),
                Field(
                    "suffix",
                    "New column suffix",
                    "text",
                    placeholder="blank = replace in place",
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
