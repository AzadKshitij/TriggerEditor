"""Sort uses the shaping form; sort-key cards, undo and codegen stay in sync."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
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
    return pl.DataFrame({"a": [2, 1, 3], "b": ["y", "x", "z"]})


def _node(qtbot, frame=None):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, (frame or _frame()).lazy())
    cls = get_class_from_opcode(PreparationNodes.SORT, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, source, node, dock


def test_dock_builds_with_columns_available(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    stack = content._stacks["keys"]
    assert stack is not None
    assert stack.add_button.isEnabled()

    stack.add_button.click()
    assert content.settings["keys"] == [{"column": "", "order": "Ascending"}]
    picker = stack._cards[0].findChildren(ColumnPicker)[0]
    assert picker.column_names() == ["a", "b"]


def test_edit_key_and_order_then_undo(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    stack = content._stacks["keys"]

    history.storeHistory("Baseline")
    stack.add_button.click()
    picker = stack._cards[0].findChildren(ColumnPicker)[0]
    picker.set_selected(["a"], emit=True)
    assert content.settings["keys"][0]["column"] == "a"

    combo = stack._cards[0].findChildren(NoWheelComboBox)[0]
    combo.setCurrentIndex(1)
    assert content.settings["keys"][0]["order"] == "Descending"
    assert node.value[0]["data"].collect()["a"].to_list() == [3, 2, 1]

    history.undo()
    assert content.settings["keys"][0]["order"] == "Ascending"
    assert node.value[0]["data"].collect()["a"].to_list() == [1, 2, 3]

    history.undo()
    assert content.settings["keys"][0]["column"] == ""

    history.undo()
    assert content.settings["keys"] == []

    history.redo()
    assert content.settings["keys"] == [{"column": "", "order": "Ascending"}]


def test_generated_code_matches_live_for_multiple_keys(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting(
        "keys",
        [
            {"column": "b", "order": "Ascending"},
            {"column": "a", "order": "Descending"},
        ],
        "Sort Sort keys Added",
        structural=True,
    )
    live = node.value[0]["data"].collect()

    namespace = {"var_src": _frame().lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = namespace[content.output_variables[0]].collect()
    assert generated.equals(live)


def test_serialize_round_trip(qtbot) -> None:
    window, source, node, _dock = _node(qtbot)
    content = node.content
    keys = [{"column": "a", "order": "Descending"}]
    content.set_setting("keys", keys, "Sort Sort keys Added", structural=True)
    state = content.serialize()
    assert state["settings"]["keys"] == keys

    cls = get_class_from_opcode(PreparationNodes.SORT, NodeTypes.PREPARATION)
    fresh = cls(window.scene)
    Edge(window.scene, source.outputs[0], fresh.inputs[0])
    assert fresh.content.deserialize(state) is not False
    fresh.markDirty(True)
    out = fresh.eval()
    assert out is not None and not fresh.isInvalid()
    assert out[0]["data"].collect().equals(node.value[0]["data"].collect())
