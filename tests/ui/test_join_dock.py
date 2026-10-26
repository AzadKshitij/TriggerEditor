"""Join dock: default mapping, output selection, undo and codegen."""

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
from trigger_designer.qt.widgets.common import ColumnPicker


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
    return pl.DataFrame({"id": [1, 2], "a": ["x", "y"]})


def _right() -> pl.DataFrame:
    return pl.DataFrame({"rid": [2, 3], "b": ["p", "q"]})


def _node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    left = Source(window.scene, _left().lazy(), "var_left")
    right = Source(window.scene, _right().lazy(), "var_right")
    cls = get_class_from_opcode(JoinNodes.JOIN, NodeTypes.JOIN)
    node = cls(window.scene)
    Edge(window.scene, left.outputs[0], node.inputs[0])
    Edge(window.scene, right.outputs[0], node.inputs[1])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, dock


def _outputs(node):
    return [entry["data"].collect() for entry in node.value]


def test_default_mapping_and_output_rows(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    assert content.settings["mapping_data"] == [
        {"left_column": "id", "right_column": "rid"}
    ]
    assert len(content._mapping_rows) == 1
    left_picker = content._mapping_rows[0]["left"]
    right_picker = content._mapping_rows[0]["right"]
    assert isinstance(left_picker, ColumnPicker)
    assert isinstance(right_picker, ColumnPicker)
    assert left_picker.checked() == ["id"]
    assert right_picker.checked() == ["rid"]
    assert isinstance(content.output_picker, ColumnPicker)
    left_only, joined, right_only = _outputs(node)
    assert left_only["id"].to_list() == [1]
    assert joined["id"].to_list() == [2]
    assert right_only["id"].to_list() == [3]


def test_output_selection_changes_the_joined_columns(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    content._on_output_changed(["R: b", "L: id"])
    assert content.settings["selected_columns"] == [
        {"name": "b", "source": "R"},
        {"name": "id", "source": "L"},
    ]
    assert _outputs(node)[1].columns == ["b", "id"]


def test_mapping_add_is_undoable(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")

    content.add_pair_button.click()
    assert len(content.settings["mapping_data"]) == 2
    history.undo()
    assert len(content.settings["mapping_data"]) == 1
    assert len(content._mapping_rows) == 1


def test_generated_code_matches_all_three_outputs(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    live = _outputs(node)

    namespace = {"var_left": _left().lazy(), "var_right": _right().lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = [namespace[name].collect() for name in content.output_variables]
    for actual, expected in zip(generated, live):
        assert actual.equals(expected)
