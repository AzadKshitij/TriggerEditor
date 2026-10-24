"""Append uses the shaping form; method edits, undo and codegen stay in sync."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge

from trigger_designer.core.node_configuration import (
    JoinNodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.common import NoWheelComboBox


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, frame, name: str) -> None:
        self._frame = frame
        self._name = name
        super().__init__(scene, inputs=[], outputs=[3])
        self.value = [{"data": frame, "variable_name": name}]
        self.markDirty(False)
        self.markInvalid(False)

    def evalImplementation(self):
        self.value = [{"data": self._frame, "variable_name": self._name}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


def _left() -> pl.DataFrame:
    return pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})


def _right() -> pl.DataFrame:
    return pl.DataFrame({"a": [3], "b": ["z"]})


def _node(qtbot, right=None):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    left = Source(window.scene, _left().lazy(), "var_left")
    right_frame = right if right is not None else _right()
    right_source = Source(window.scene, right_frame.lazy(), "var_right")
    cls = get_class_from_opcode(JoinNodes.APPEND, NodeTypes.JOIN)
    node = cls(window.scene)
    Edge(window.scene, left.outputs[0], node.inputs[0])
    Edge(window.scene, right_source.outputs[0], node.inputs[1])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, dock


def _output(node) -> pl.DataFrame:
    return node.value[0]["data"].collect()


def test_combo_edits_method_and_output(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    combo = content._widgets["how"]
    assert isinstance(combo, NoWheelComboBox)
    assert content.settings["how"] == "diagonal_relaxed"
    assert _output(node).height == 3

    combo.setCurrentIndex(combo.findData("vertical"))
    assert content.settings["how"] == "vertical"
    assert _output(node).rows() == [(1, "x"), (2, "y"), (3, "z")]


def test_undo_restores_the_method(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    combo = content._widgets["how"]

    combo.setCurrentIndex(combo.findData("horizontal"))
    assert content.settings["how"] == "horizontal"
    history.undo()
    assert content.settings["how"] == "diagonal_relaxed"
    assert content._widgets["how"].currentData() == "diagonal_relaxed"
    history.redo()
    assert content.settings["how"] == "horizontal"


def test_generated_code_matches_live(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("how", "vertical", "Append Method Changed")
    live = _output(node)

    namespace = {"var_left": _left().lazy(), "var_right": _right().lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = namespace[content.output_variables[0]].collect()
    assert generated.equals(live)


def test_vertical_mismatch_invalidates_the_node(qtbot) -> None:
    _window, node, _dock = _node(qtbot, right=pl.DataFrame({"a": [3], "c": [9]}))
    content = node.content
    content.set_setting("how", "vertical", "Append Method Changed")
    node.markDirty(True)
    assert node.eval() is None
    assert node.isInvalid()


def test_serialize_round_trip(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("how", "diagonal", "Append Method Changed")
    state = content.serialize()
    assert state["settings"]["how"] == "diagonal"

    left = Source(window.scene, _left().lazy(), "var_left")
    right = Source(window.scene, _right().lazy(), "var_right")
    cls = get_class_from_opcode(JoinNodes.APPEND, NodeTypes.JOIN)
    fresh = cls(window.scene)
    Edge(window.scene, left.outputs[0], fresh.inputs[0])
    Edge(window.scene, right.outputs[0], fresh.inputs[1])
    assert fresh.content.deserialize(state) is not False
    fresh.markDirty(True)
    out = fresh.eval()
    assert out is not None and not fresh.isInvalid()
    assert out[0]["data"].collect().equals(node.value[0]["data"].collect())
