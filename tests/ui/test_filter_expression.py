#!/usr/bin/env python3
"""Filter expression editor: caret preservation, aliases and saved state."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QApplication

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode

APP = QApplication.instance() or QApplication([])

FRAME = pl.DataFrame(
    {
        "order_value": [10, 100, 600, 250],
        "status": ["paid", "pending", "paid", "refunded"],
    }
)


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, frame) -> None:
        self._frame = frame
        super().__init__(scene, inputs=[], outputs=[3])
        self.value = [{"data": frame, "variable_name": "var_in"}]
        self.markDirty(False)
        self.markInvalid(False)

    def evalImplementation(self):
        self.value = [{"data": self._frame, "variable_name": "var_in"}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


def _make_content(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, FRAME.lazy())
    cls = get_class_from_opcode(PreparationNodes.FILTER, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node.content


def _cursor_position(widget) -> int:
    return widget.textCursor().position()


def _set_cursor_position(widget, position: int) -> None:
    cursor = widget.textCursor()
    cursor.setPosition(position)
    widget.setTextCursor(cursor)


def _count_compute(monkeypatch, content):
    calls = []
    original = content.compute

    def counted():
        calls.append(1)
        return original()

    monkeypatch.setattr(content, "compute", counted)
    return calls


def test_commit_preserves_caret_position(qtbot) -> None:
    _window, content = _make_content(qtbot)
    content.mode_selector._buttons["Expression"].click()
    editor = content.expression_input.editor
    content.expression_input.set_text("[order_value] > 100")
    _set_cursor_position(editor, 5)
    content._commit_expression()
    assert _cursor_position(editor) == 5
    assert content.settings["expression"] == "[order_value] > 100"

    content.mode_selector._buttons["Simple"].click()
    content.value_input.setText("250")
    qtbot.wait(350)
    content.value_input.setCursorPosition(1)
    content._sync_widgets_from_model()
    assert content.value_input.cursorPosition() == 1


def test_expression_typing_defers_compute_until_focus_out(qtbot, monkeypatch) -> None:
    _window, content = _make_content(qtbot)
    content.mode_selector._buttons["Expression"].click()
    calls = _count_compute(monkeypatch, content)

    content.expression_input.set_text("[order_value] > 100")
    qtbot.wait(350)

    assert calls == []
    assert content.settings["expression"] == "[order_value] > 100"

    monkeypatch.setattr(content, "_sql_editor_has_focus", lambda: False)
    content._on_expression_finished()
    qtbot.wait(20)

    assert calls == [1]
    matched = content.node.value[0]["data"].collect()
    assert matched["order_value"].to_list() == [600, 250]

    content._on_expression_finished()
    qtbot.wait(20)
    assert calls == [1]


def test_expression_pending_text_flushes_without_compute(qtbot, monkeypatch) -> None:
    _window, content = _make_content(qtbot)
    calls = _count_compute(monkeypatch, content)

    content.expression_input.set_text("[order_value] > 100")
    content.commit_pending_dock_edits(evaluate=False)

    assert content.settings["expression"] == "[order_value] > 100"
    assert content._pending_evaluate is False
    assert calls == []


def test_builder_value_still_evaluates_immediately(qtbot, monkeypatch) -> None:
    _window, content = _make_content(qtbot)
    calls = _count_compute(monkeypatch, content)

    content.set_setting("value", "250", "Filter Value Changed")

    assert calls == [1]


def test_strip_alias_filters_like_trim(qtbot) -> None:
    _window, content = _make_content(qtbot)
    content.set_setting("mode", "expression", "Filter Mode Changed")
    content.set_setting(
        "expression", "strip([status]) = 'paid'", "Filter Expression Changed"
    )
    matched = content.compute()[0].collect()
    assert matched["order_value"].to_list() == [10, 600]


def test_serialize_carries_filter_settings(qtbot) -> None:
    window, content = _make_content(qtbot)
    content.set_setting("mode", "expression", "Filter Mode Changed")
    content.set_setting("expression", "[order_value] > 1", "Filter Expression Changed")
    content.set_setting("value2", "7", "Filter Max value Changed")
    data = window.scene.serialize()
    node_data = [
        node for node in data["nodes"] if node.get("op") == "preparation.filter"
    ]
    assert len(node_data) == 1
    settings = node_data[0]["content"]["settings"]
    assert settings["mode"] == "expression"
    assert settings["expression"] == "[order_value] > 1"
    assert settings["value2"] == "7"
