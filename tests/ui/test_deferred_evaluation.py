"""Edits reach the model at once; the node runs when the user leaves it."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge

from tests.support.flush import flush
from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, frame) -> None:
        self._frame = frame
        super().__init__(scene, inputs=[], outputs=[3])
        self.value = [{"data": frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)

    def evalImplementation(self):
        self.value = [{"data": self._frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


def _select(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    frame = pl.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]}).lazy()
    source = Source(window.scene, frame)
    cls = get_class_from_opcode(PreparationNodes.SELECT, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, dock


def _uncheck_first_column(content) -> None:
    rows = content.table_widget.rows()
    rows[0].checked = False
    content._on_table_data()


def _count_evals(node):
    calls = []
    original = node.eval

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    node.eval = counted
    return calls


def _columns(node) -> list[str]:
    return node.value[0]["data"].collect_schema().names()


def test_a_checkbox_change_updates_the_model_but_does_not_run(qtbot) -> None:
    _window, node, _dock = _select(qtbot)
    content = node.content
    calls = _count_evals(node)

    _uncheck_first_column(content)
    qtbot.wait(50)

    assert content.settings["columns"][0]["selected"] is False
    assert calls == []
    assert _columns(node) == ["a", "b", "c"]  # still the previous result
    assert content._pending_evaluate is True


def test_the_node_shows_the_yellow_mark_while_changes_are_pending(qtbot) -> None:
    _window, node, _dock = _select(qtbot)
    assert node.grNode._error_badge == ""

    _uncheck_first_column(node.content)

    assert node.grNode._error_badge == "pending"
    assert "pending" in node.grNode.toolTip().lower()


def test_clicking_empty_canvas_runs_the_node_once(qtbot) -> None:
    _window, node, dock = _select(qtbot)
    calls = _count_evals(node)
    _uncheck_first_column(node.content)

    dock.updateConfig([])  # an empty selection: the canvas was clicked
    qtbot.wait(50)

    assert len(calls) == 1
    assert _columns(node) == ["b", "c"]
    assert node.grNode._error_badge == ""


def test_selecting_another_node_runs_the_node_it_leaves(qtbot) -> None:
    window, node, dock = _select(qtbot)
    other = get_class_from_opcode(PreparationNodes.SORT, NodeTypes.PREPARATION)(
        window.scene
    )
    _uncheck_first_column(node.content)

    dock.updateConfig([other.grNode])
    qtbot.wait(50)

    assert _columns(node) == ["b", "c"]
    assert node.grNode._error_badge == ""


def test_many_edits_run_once(qtbot) -> None:
    _window, node, dock = _select(qtbot)
    calls = _count_evals(node)
    content = node.content

    for index in range(3):
        rows = content.table_widget.rows()
        rows[index].checked = False
        content._on_table_data()
    dock.updateConfig([])
    qtbot.wait(50)

    assert len(calls) == 1


def test_save_and_run_keep_the_pending_run(qtbot, monkeypatch) -> None:
    window, node, dock = _select(qtbot)
    monkeypatch.setattr(window, "_find_config_dock", lambda: dock)
    _uncheck_first_column(node.content)

    window.commit_pending_config_edits(evaluate=False)

    assert node.content._pending_evaluate is True
    assert node.content.serialize()["settings"]["columns"][0]["selected"] is False


def test_an_error_badge_wins_over_the_pending_mark(qtbot) -> None:
    _window, node, _dock = _select(qtbot)
    _uncheck_first_column(node.content)
    assert node.grNode._error_badge == "pending"
    from trigger_designer.core.errors import ErrorContext, make_error

    node.set_error(
        make_error("TD-SYS-001", ErrorContext.from_node(node, "live"), message="x"),
        "live",
    )

    assert node.grNode._error_badge == "error"


def test_undo_stays_pending_until_the_node_is_left(qtbot) -> None:
    window, node, dock = _select(qtbot)
    _uncheck_first_column(node.content)
    flush(node)
    assert _columns(node) == ["b", "c"]

    window.scene.history.undo()
    qtbot.wait(50)
    assert node.content.settings["columns"][0]["selected"] is True

    dock.updateConfig([])
    qtbot.wait(50)
    assert _columns(node) == ["a", "b", "c"]
