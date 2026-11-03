"""Aggregate table: add/remove, actions, aliases, undo and codegen."""

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
    return pl.DataFrame({"g": ["a", "a", "b"], "x": [1, 2, 3], "s": ["p", "q", "r"]})


def _node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, _frame().lazy())
    cls = get_class_from_opcode(PreparationNodes.GROUPBY, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, source, node, dock


def _output(node) -> pl.DataFrame:
    return live_value(node)[0]["data"].collect()


def _add_field(content, field: str) -> None:
    picker = content.field_picker
    picker.setCurrentIndex(picker.findData(field))
    content.add_btn.click()


def test_table_builds_and_adds_group_keys(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    assert content.actions_table.rowCount() == 0

    _add_field(content, "g")
    assert content.settings["actions"] == [
        {"field": "g", "action": "GroupBy", "output_name": "g"}
    ]
    assert content.actions_table.rowCount() == 1
    assert _output(node).columns == ["g", "count"]


def test_action_change_and_alias_update_output(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    _add_field(content, "g")
    _add_field(content, "x")

    combo = content.actions_table.cellWidget(1, 1)
    combo.setCurrentIndex(combo.findData("Sum"))
    assert content.settings["actions"][1]["action"] == "Sum"
    assert content.settings["actions"][1]["output_name"] == "Sum_x"
    assert _output(node).sort("g").rows() == [("a", 3), ("b", 3)]

    content.actions_table.item(1, 2).setText("Total")
    assert content.settings["actions"][1]["output_name"] == "Total"
    assert _output(node).columns == ["g", "Total"]


def test_remove_and_undo(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    _add_field(content, "g")
    assert content.settings["actions"]

    history.undo()
    assert content.settings["actions"] == []
    assert content.actions_table.rowCount() == 0

    history.redo()
    assert content.settings["actions"][0]["field"] == "g"

    content.actions_table.selectRow(0)
    content.remove_btn.click()
    assert content.settings["actions"] == []
    assert content.actions_table.rowCount() == 0


def test_generated_code_matches_live(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting(
        "actions",
        [
            {"field": "g", "action": "GroupBy", "output_name": "g"},
            {"field": "x", "action": "Sum", "output_name": "Total"},
        ],
        "Aggregate Field Added",
        structural=True,
    )
    live = _output(node)

    namespace = {"var_src": _frame().lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = namespace[content.output_variables[0]].collect()
    assert generated.sort("g").equals(live.sort("g"))


def test_serialize_round_trip(qtbot) -> None:
    window, source, node, _dock = _node(qtbot)
    content = node.content
    actions = [
        {"field": "g", "action": "GroupBy", "output_name": "g"},
        {"field": "x", "action": "Mean", "output_name": "Avg"},
    ]
    content.set_setting("actions", actions, "Aggregate Field Added", structural=True)
    state = content.serialize()
    assert state["settings"]["actions"] == actions

    cls = get_class_from_opcode(PreparationNodes.GROUPBY, NodeTypes.PREPARATION)
    fresh = cls(window.scene)
    Edge(window.scene, source.outputs[0], fresh.inputs[0])
    assert fresh.content.deserialize(state) is not False
    fresh.markDirty(True)
    out = fresh.eval()
    assert out is not None and not fresh.isInvalid()
    assert (
        out[0]["data"]
        .collect()
        .sort("g")
        .equals(live_value(node)[0]["data"].collect().sort("g"))
    )
