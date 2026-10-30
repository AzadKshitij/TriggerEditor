"""Comment dock: text edit -> label, undo/redo, .tds round trip."""

from __future__ import annotations

import orjson
from qtpy.QtWidgets import QPlainTextEdit

from trigger_designer.core.node_configuration import (
    NodeTypes,
    ReportNodes,
    get_class_from_opcode,
)
from trigger_designer.core.shaping.comments import comments_from_scene_dict
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock


def _node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    cls = get_class_from_opcode(ReportNodes.COMMENT, NodeTypes.REPORT)
    node = cls(window.scene)
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, dock


def test_dock_builds_a_textarea_with_placeholder(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    widget = node.content._widgets["text"]
    assert isinstance(widget, QPlainTextEdit)
    assert widget.placeholderText() == "Note for the reviewer"
    assert widget.toPlainText() == ""


def test_typing_updates_model_and_label_with_one_step(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    history = window.scene.history
    history.storeHistory("Baseline")
    widget = node.content._widgets["text"]
    widget.setPlainText("C")
    widget.setPlainText("Check")
    widget.setPlainText("Check cut-off\nsecond line")
    qtbot.wait(400)
    assert node.content.settings["text"] == "Check cut-off\nsecond line"
    assert node.getNodeLabel() == "Check cut-off"
    # The typing burst collapses to one undo step back to the empty note.
    history.undo()
    assert node.content.settings["text"] == ""
    assert node.getNodeLabel() == ""
    assert widget.toPlainText() == ""


def test_undo_redo_restore_text_widget_and_label(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    history = window.scene.history
    history.storeHistory("Baseline")
    widget = node.content._widgets["text"]
    widget.setPlainText("Check cut-off")
    qtbot.wait(400)
    assert node.getNodeLabel() == "Check cut-off"

    history.undo()
    assert node.getNodeLabel() == ""
    assert widget.toPlainText() == ""
    history.redo()
    assert node.content.settings["text"] == "Check cut-off"
    assert node.getNodeLabel() == "Check cut-off"
    assert widget.toPlainText() == "Check cut-off"


def test_restore_does_not_record_a_new_step(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    history = window.scene.history
    history.storeHistory("Baseline")
    node.content._widgets["text"].setPlainText("note")
    qtbot.wait(400)
    history.undo()
    qtbot.wait(400)
    history.redo()
    qtbot.wait(400)
    assert node.content.settings["text"] == "note"
    history.undo()
    assert node.content.settings["text"] == ""


def test_dock_shows_no_empty_state_and_no_inputs_summary(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    assert node.content.dock_summary().startswith("0 inputs")
    assert node.content.ready() is True


def test_tds_round_trip_keeps_op_text_and_label(qtbot, tmp_path) -> None:
    window, node, _dock = _node(qtbot)
    node.content._widgets["text"].setPlainText("Check cut-off\nsecond")
    qtbot.wait(400)
    path = tmp_path / "comment.tds"
    window.scene.saveToFile(str(path))

    saved = orjson.loads(path.read_bytes())
    ops = [n["op"] for n in saved["nodes"]]
    assert ops == ["report.comment"]
    assert comments_from_scene_dict(saved)[0].text == "Check cut-off\nsecond"

    reloaded = TriggerSubWindow()
    qtbot.addWidget(reloaded)
    assert reloaded.fileLoad(str(path)) is True
    (loaded,) = reloaded.getAllNodes()
    assert loaded.content.settings["text"] == "Check cut-off\nsecond"
    assert loaded.getNodeLabel() == "Check cut-off"
    assert loaded.node_title == "Comment"
