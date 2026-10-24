"""Running Total uses the shaping form; pickers, undo and codegen stay in sync."""

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
    return pl.DataFrame({"a": ["x", "x", "y"], "n": [1, 2, 3], "s": ["p", "q", "r"]})


def _node(qtbot, frame=None):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, (frame or _frame()).lazy())
    cls = get_class_from_opcode(TransformNodes.RUNNING_TOTAL, NodeTypes.TRANSFORM)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, source, node, dock


def test_dock_offers_numeric_sums_and_all_groups(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    sums = content._widgets["sum_columns"]
    groups = content._widgets["group_by_columns"]
    assert isinstance(sums, ColumnPicker)
    assert isinstance(groups, ColumnPicker)
    assert sums.column_names() == ["n"]
    assert groups.column_names() == ["a", "n", "s"]
    assert content.dock_summary() == "0 sums \u00b7 0 groups"


def test_selecting_sums_and_groups_changes_output(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    sums = content._widgets["sum_columns"]
    groups = content._widgets["group_by_columns"]

    sums.set_selected(["n"], emit=True)
    assert content.settings["sum_columns"] == ["n"]
    out = node.value[0]["data"].collect()
    assert out["RunTot_n"].to_list() == [1, 3, 6]
    assert content.dock_summary() == "1 sum \u00b7 0 groups"

    groups.set_selected(["a"], emit=True)
    assert content.settings["group_by_columns"] == ["a"]
    out = node.value[0]["data"].collect()
    assert out["RunTot_n"].to_list() == [1, 3, 3]
    assert content.dock_summary() == "1 sum \u00b7 1 group"


def test_undo_redoes_settings_widgets_and_output(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    picker = content._widgets["sum_columns"]

    history.storeHistory("Baseline")
    picker.set_selected(["n"], emit=True)
    assert "RunTot_n" in node.value[0]["data"].collect().columns

    history.undo()
    assert content.settings["sum_columns"] == []
    assert content._widgets["sum_columns"].checked() == []
    assert "RunTot_n" not in node.value[0]["data"].collect().columns

    history.redo()
    assert content.settings["sum_columns"] == ["n"]
    assert content._widgets["sum_columns"].checked() == ["n"]
    assert "RunTot_n" in node.value[0]["data"].collect().columns


def test_generated_code_matches_live(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("sum_columns", ["n"], "Running Total Sum Columns Changed")
    content.set_setting(
        "group_by_columns", ["a"], "Running Total Group By Columns Changed"
    )
    live = node.value[0]["data"].collect()

    namespace = {"var_src": _frame().lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = namespace[content.output_variables[0]].collect()
    assert generated.equals(live)


def test_serialize_round_trip(qtbot) -> None:
    window, source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("sum_columns", ["n"], "Running Total Sum Columns Changed")
    state = content.serialize()
    assert state["settings"]["sum_columns"] == ["n"]

    cls = get_class_from_opcode(TransformNodes.RUNNING_TOTAL, NodeTypes.TRANSFORM)
    fresh = cls(window.scene)
    Edge(window.scene, source.outputs[0], fresh.inputs[0])
    assert fresh.content.deserialize(state) is not False
    fresh.markDirty(True)
    out = fresh.eval()
    assert out is not None and not fresh.isInvalid()
    assert out[0]["data"].collect().equals(node.value[0]["data"].collect())
