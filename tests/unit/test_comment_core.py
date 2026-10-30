"""Comment node: label rule, readers, generated code and node identity."""

from __future__ import annotations

import subprocess
import sys

import polars as pl
import pytest

from trigger_designer.core.node_configuration import (
    NodeTypes,
    ReportNodes,
    get_class_from_op,
    get_class_from_opcode,
)
from trigger_designer.core.shaping import comments
from trigger_designer.core.shaping.comments import (
    COMMENT_OP,
    LABEL_MAX,
    NOT_EXECUTABLE_OPS,
    CommentRecord,
    comments_from_nodes,
    comments_from_scene_dict,
    label_for,
)
from trigger_designer.qt.design_window import TriggerSubWindow


def _node_dict(node_id, op, text, x=0.0, y=0.0):
    return {
        "id": node_id,
        "op": op,
        "pos_x": x,
        "pos_y": y,
        "content": {"settings": {"text": text}},
    }


def test_no_qt_import_in_core() -> None:
    code = (
        "import sys, trigger_designer.core.shaping.comments;"
        "print(any(m.split('.')[0] in ('PySide6','PyQt5','PyQt6','qtpy') for m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip().endswith("False")


def test_constants() -> None:
    assert COMMENT_OP == "report.comment"
    assert NOT_EXECUTABLE_OPS == frozenset({"report.comment"})
    assert comments.DEFAULTS == {"text": ""}


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("", ""),
        (None, ""),
        ("   \n  ", ""),
        ("Check cut-off", "Check cut-off"),
        ("  First  \nSecond", "First"),
        ("\n\nafter blanks\nnext", "after blanks"),
        ("x" * 200, "x" * LABEL_MAX),
        ("short\n" + "y" * 200, "short"),
    ],
)
def test_label_for(text, label) -> None:
    assert label_for(text) == label


def test_scene_dict_reading_order_trimmed_blank_and_other_ops_skipped() -> None:
    scene = {
        "nodes": [
            _node_dict(2, COMMENT_OP, "Second", y=100),
            _node_dict(1, COMMENT_OP, " First ", y=10),
            _node_dict(3, COMMENT_OP, "   ", y=50),
            _node_dict(4, "preparation.record_id", "not a comment", y=0),
        ]
    }
    found = comments_from_scene_dict(scene)
    assert [(c.node_id, c.text) for c in found] == [(1, "First"), (2, "Second")]
    assert found[0] == CommentRecord(1, "First", 0.0, 10.0)


def test_scene_dict_same_row_orders_by_x_then_id() -> None:
    scene = {
        "nodes": [
            _node_dict(5, COMMENT_OP, "c", x=30, y=1),
            _node_dict(4, COMMENT_OP, "b", x=20, y=1),
            _node_dict(3, COMMENT_OP, "a", x=20, y=1),
        ]
    }
    assert [c.node_id for c in comments_from_scene_dict(scene)] == [3, 4, 5]


def test_scene_dict_tolerates_missing_content() -> None:
    scene = {
        "nodes": [
            {"id": 1, "op": COMMENT_OP},
            {"id": 2, "op": COMMENT_OP, "content": None},
        ]
    }
    assert comments_from_scene_dict(scene) == []
    assert comments_from_scene_dict({}) == []


def test_registry_identity() -> None:
    cls = get_class_from_opcode(ReportNodes.COMMENT, NodeTypes.REPORT)
    assert cls.node_title == "Comment"
    assert cls.icon == "node_comment"
    assert cls.node_code == ReportNodes.COMMENT
    assert get_class_from_op(COMMENT_OP) is cls


def _comment(window):
    cls = get_class_from_opcode(ReportNodes.COMMENT, NodeTypes.REPORT)
    return cls(window.scene)


def test_node_has_no_sockets_and_no_outputs() -> None:
    node = _comment(TriggerSubWindow())
    assert node.inputs == []
    assert node.outputs == []
    assert node.content.output_variables == []
    assert node.content.ready() is True


def test_eval_returns_empty_list_and_is_valid() -> None:
    node = _comment(TriggerSubWindow())
    assert node.eval() == []
    assert not node.isInvalid()
    assert node.content.compute() == []


def test_get_code_is_a_successful_noop() -> None:
    node = _comment(TriggerSubWindow())
    node.content.settings["text"] = 'quote " and \n newline\nimport os; os.system("x")'
    code = node.get_code()
    assert code == "# Comment (not executed)\n"
    namespace: dict = {}
    exec(code, {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    assert namespace == {}


def test_unwired_defines_every_output_variable() -> None:
    node = _comment(TriggerSubWindow())
    namespace: dict = {}
    exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    for variable in node.content.output_variables:
        assert variable in namespace


def test_label_follows_text_and_empty_text_clears_it() -> None:
    node = _comment(TriggerSubWindow())
    content = node.content
    content.set_setting("text", "Check cut-off\nsecond line", "Comment Text Changed")
    assert node.getNodeLabel() == "Check cut-off"
    long_text = "z" * 150
    content.set_setting("text", long_text, "Comment Text Changed")
    assert node.getNodeLabel() == "z" * LABEL_MAX
    assert content.settings["text"] == long_text  # stored whole
    content.set_setting("text", "", "Comment Text Changed")
    assert node.getNodeLabel() == ""


def test_manual_label_is_overwritten_by_next_text_change() -> None:
    node = _comment(TriggerSubWindow())
    node.setNodeLabel("manual", store_history=False)
    node.content.set_setting("text", "From text", "Comment Text Changed")
    assert node.getNodeLabel() == "From text"


def test_serialize_round_trip_keeps_op_text_and_label() -> None:
    window = TriggerSubWindow()
    node = _comment(window)
    node.content.set_setting("text", "Check cut-off", "Comment Text Changed")
    data = node.serialize()
    assert data["op"] == COMMENT_OP
    assert data["content"]["settings"]["text"] == "Check cut-off"

    other = TriggerSubWindow()
    clone = _comment(other)
    clone.deserialize(data, {})
    assert clone.content.settings["text"] == "Check cut-off"
    assert clone.getNodeLabel() == "Check cut-off"


def test_comments_from_nodes_matches_scene_dict() -> None:
    window = TriggerSubWindow()
    first = _comment(window)
    second = _comment(window)
    blank = _comment(window)
    first.content.set_setting("text", " Later ", "t")
    second.content.set_setting("text", "Earlier", "t")
    first.setPos(0, 200)
    second.setPos(0, 20)
    assert blank.content.settings["text"] == ""
    live = comments_from_nodes(window.getAllNodes())
    assert [c.text for c in live] == ["Earlier", "Later"]
    saved = comments_from_scene_dict(window.scene.serialize())
    assert [(c.node_id, c.text) for c in saved] == [(c.node_id, c.text) for c in live]


def test_comment_never_a_sink_requirement() -> None:
    """Loading a scene with a lone Comment evaluates without error."""
    window = TriggerSubWindow()
    node = _comment(window)
    node.content.set_setting("text", "note", "t")
    window.scene.history.storeHistory("baseline")
    assert node.eval() == []
