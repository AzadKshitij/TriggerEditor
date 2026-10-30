"""Comment node: a canvas note that never executes (no sockets, no data).

Logic lives in ``core/shaping/comments.py``. The text is ``settings["text"]``;
the floating canvas label is its first line, so the model stays the only truth.
"""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    ReportNodes,
    register_node,
)
from trigger_designer.core.shaping import comments as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


class CommentContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.comments"
    INPUTS = 0
    OUTPUT_KINDS = ()
    HISTORY = "Comment"
    SUMMARY = "never runs"
    #: Nothing to run: an edit must not mark the node pending or re-evaluate.
    DEFER_EVALUATION = False
    FORM = (
        FormSection(
            "",
            (
                Field(
                    "text",
                    "",
                    "textarea",
                    placeholder="Note for the reviewer",
                    tip="The first line is shown above the node.",
                    label_above=True,
                ),
            ),
        ),
    )

    def ready(self) -> bool:
        return True  # no input to wait for

    def compute(self) -> list:
        self.outputs = []
        return []

    def get_code(self) -> str:
        return core.CODE

    def request_evaluation(self) -> None:
        """Nothing downstream depends on a note; skip the evaluation entirely."""

    def after_change(self) -> None:
        node = getattr(self, "node", None)
        if node is None:
            return
        label = core.label_for(self.settings.get("text"))
        if node.getNodeLabel() != label:
            node.setNodeLabel(label, store_history=False)


@register_node(ReportNodes.COMMENT, NodeTypes.REPORT)
class TriggerNode_Comment(ShapingNode):
    icon = "node_comment"
    node_code = ReportNodes.COMMENT
    node_type = NodeTypes.REPORT
    node_title = "Comment"
    content_class = CommentContent
    content_label_objname = "trigger_node_comment"
    output_text = ()
