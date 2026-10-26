"""Transpose uses the shaping form; pickers, undo and codegen stay in sync."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge

from trigger_designer.core.node_configuration import (
    NodeTypes,
    TransformNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.common import ColumnPicker, NoWheelComboBox


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


def _frame() -> pl.DataFrame:
    return pl.DataFrame({"id": [1, 2], "a": [10, 20], "b": [30, 40]})


def _node(qtbot, frame=None):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, (frame or _frame()).lazy())
    cls = get_class_from_opcode(TransformNodes.TRANSPOSE, NodeTypes.TRANSFORM)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, source, node, dock


def _output(node) -> pl.DataFrame:
    return node.value[0]["data"].collect()


def test_dock_shows_key_data_and_policy(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    keys = content._widgets["key_columns"]
    data = content._widgets["data_columns"]
    policy = content._widgets["missing_action"]
    assert isinstance(keys, ColumnPicker)
    assert isinstance(data, ColumnPicker)
    assert isinstance(policy, NoWheelComboBox)
    assert keys.column_names() == ["id", "a", "b"]
    assert data.column_names() == ["id", "a", "b"]
    assert policy.currentData() == "warn"

    # Unconfigured data columns pass the input through.
    assert _output(node).equals(_frame())


def test_editing_key_and_data_reshapes_the_output(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content._widgets["key_columns"].set_selected(["id"], emit=True)
    content._widgets["data_columns"].set_selected(["a", "b"], emit=True)
    assert content.settings["key_columns"] == ["id"]
    assert content.settings["data_columns"] == ["a", "b"]

    out = _output(node)
    assert out.columns == ["id", "Name", "Value"]
    assert out.rows() == [
        (1, "a", 10),
        (2, "a", 20),
        (1, "b", 30),
        (2, "b", 40),
    ]


def test_missing_policy_combo_updates_the_model(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    combo = content._widgets["missing_action"]
    combo.setCurrentIndex(combo.findData("error"))
    assert content.settings["missing_action"] == "error"

    content.set_setting("data_columns", ["gone"], "Transpose Data columns Changed")
    node.markDirty(True)
    assert node.eval() is None
    assert node.isInvalid()


def test_undo_redo_restores_the_selection(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    picker = content._widgets["data_columns"]

    picker.set_selected(["a"], emit=True)
    assert content.settings["data_columns"] == ["a"]

    history.undo()
    assert content.settings["data_columns"] == []
    assert content._widgets["data_columns"].checked() == []
    assert _output(node).equals(_frame())

    history.redo()
    assert content.settings["data_columns"] == ["a"]
    assert content._widgets["data_columns"].checked() == ["a"]


def test_generated_code_matches_live(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("key_columns", ["id"], "Transpose Key columns Changed")
    content.set_setting("data_columns", ["a", "b"], "Transpose Data columns Changed")
    live = _output(node)

    namespace = {"var_src": _frame().lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = namespace[content.output_variables[0]].collect()
    assert generated.equals(live)


def test_serialize_round_trip(qtbot) -> None:
    window, source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("key_columns", ["id"], "Transpose Key columns Changed")
    content.set_setting("data_columns", ["a"], "Transpose Data columns Changed")
    state = content.serialize()
    assert state["settings"]["data_columns"] == ["a"]

    cls = get_class_from_opcode(TransformNodes.TRANSPOSE, NodeTypes.TRANSFORM)
    fresh = cls(window.scene)
    Edge(window.scene, source.outputs[0], fresh.inputs[0])
    assert fresh.content.deserialize(state) is not False
    fresh.markDirty(True)
    out = fresh.eval()
    assert out is not None and not fresh.isInvalid()
    assert out[0]["data"].collect().equals(node.value[0]["data"].collect())
