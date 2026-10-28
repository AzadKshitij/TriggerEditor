"""Unique uses the shaping form; picker, undo and codegen stay in sync."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge

from tests.support.flush import live_value
from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.common import ColumnPicker


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
    return pl.DataFrame({"a": [1, 1, 2], "b": ["x", "y", "z"]})


def _node(qtbot, frame=None):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, (frame or _frame()).lazy())
    cls = get_class_from_opcode(PreparationNodes.UNIQUE, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, source, node, dock


def _outputs(node):
    return live_value(node)[0]["data"].collect(), live_value(node)[1]["data"].collect()


def test_dock_shows_schema_columns(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    picker = content._widgets["selected_columns"]
    assert isinstance(picker, ColumnPicker)
    assert picker.column_names() == ["a", "b"]
    assert content.dock_summary() == "0 columns selected"


def test_selection_drives_both_outputs_and_all_none(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    picker = content._widgets["selected_columns"]

    picker.set_selected(["a"], emit=True)
    assert content.settings["selected_columns"] == ["a"]
    unique, duplicates = _outputs(node)
    assert unique.rows() == [(1, "x"), (2, "z")]
    assert duplicates.rows() == [(1, "x"), (1, "y")]
    assert content.dock_summary() == "1 column selected"

    picker.set_selected(["a", "b"], emit=True)
    unique, duplicates = _outputs(node)
    assert unique.height == 3
    assert duplicates.height == 0

    picker.set_selected([], emit=True)
    unique, duplicates = _outputs(node)
    assert unique.height == 3
    assert duplicates.height == 0


def test_undo_redoes_selection_and_outputs(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    picker = content._widgets["selected_columns"]

    history.storeHistory("Baseline")
    picker.set_selected(["a"], emit=True)
    assert content.settings["selected_columns"] == ["a"]
    assert _outputs(node)[1].height == 2

    history.undo()
    assert content.settings["selected_columns"] == []
    assert content._widgets["selected_columns"].checked() == []
    unique, duplicates = _outputs(node)
    assert unique.height == 3
    assert duplicates.height == 0

    history.redo()
    assert content.settings["selected_columns"] == ["a"]
    assert content._widgets["selected_columns"].checked() == ["a"]
    assert _outputs(node)[1].height == 2


def test_generated_code_matches_both_live_outputs(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("selected_columns", ["a"], "Unique Columns Changed")
    live = _outputs(node)

    namespace = {"var_src": _frame().lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = [namespace[name].collect() for name in content.output_variables]
    assert generated[0].equals(live[0])
    assert generated[1].equals(live[1])


def test_serialize_round_trip(qtbot) -> None:
    window, source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("selected_columns", ["a"], "Unique Columns Changed")
    state = content.serialize()
    assert state["settings"]["selected_columns"] == ["a"]

    cls = get_class_from_opcode(PreparationNodes.UNIQUE, NodeTypes.PREPARATION)
    fresh = cls(window.scene)
    Edge(window.scene, source.outputs[0], fresh.inputs[0])
    assert fresh.content.deserialize(state) is not False
    fresh.markDirty(True)
    out = fresh.eval()
    assert out is not None and not fresh.isInvalid()
    for index in (0, 1):
        assert out[index]["data"].collect().equals(live_value(node)[index]["data"].collect())
