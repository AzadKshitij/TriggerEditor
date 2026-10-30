"""Window dock: controls, op-dependent visibility, undo/redo, .tds round trip."""

from __future__ import annotations

import orjson
import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QCheckBox, QSpinBox

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


FRAME = pl.DataFrame(
    {"acct": ["A", "A", "B"], "d": [2, 1, 1], "amt": ["10", "5", "7"]}
).lazy()


def _node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, FRAME)
    cls = get_class_from_opcode(TransformNodes.WINDOW, NodeTypes.TRANSFORM)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, dock


def test_dock_builds_both_sections_and_buttons_are_labelled(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    assert isinstance(content._widgets["partition_by"], ColumnPicker)
    assert content._widgets["partition_by"].column_names() == ["acct", "d", "amt"]
    assert set(content._stacks) == {"order_by", "ops"}
    for stack in content._stacks.values():
        assert stack.add_button.toolTip()
        assert stack.add_button.accessibleName()


def test_unconfigured_op_is_invalid_then_live_output_follows_edits(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")

    content._stacks["ops"].add_button.click()
    assert len(content.settings["ops"]) == 1
    assert content.settings["ops"][0]["op"] == "lag"
    content.commit_pending_dock_edits()
    assert node.isInvalid()  # "Pick a source column"

    widgets = content._card_widgets["ops"][0]
    widgets["source"].set_selected(["amt"], emit=True)
    assert content.settings["ops"][0]["source"] == "amt"
    content._widgets["partition_by"].set_selected(["acct"], emit=True)
    content.commit_pending_dock_edits()
    assert not node.isInvalid()
    live = node.value[0]["data"].collect()
    assert live.columns == ["acct", "d", "amt", "amt_lag1"]
    assert live["amt_lag1"].to_list() == [None, "10", None]

    history.undo()
    assert content.settings["partition_by"] == []
    history.redo()
    assert content.settings["partition_by"] == ["acct"]


def test_fields_follow_the_chosen_calculation(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    content._stacks["ops"].add_button.click()

    def visible(key: str) -> bool:
        widgets = content._card_widgets["ops"][0]
        return widgets[key].isVisibleTo(content._stacks["ops"])

    assert visible("offset") and not visible("window") and not visible("nulls")
    combo = content._card_widgets["ops"][0]["op"]
    combo.setCurrentIndex(combo.findData("rolling_sum"))
    assert content.settings["ops"][0]["op"] == "rolling_sum"
    assert visible("window") and visible("partial") and visible("nulls")
    assert not visible("offset")
    assert isinstance(content._card_widgets["ops"][0]["window"], QSpinBox)
    assert isinstance(content._card_widgets["ops"][0]["partial"], QCheckBox)

    combo = content._card_widgets["ops"][0]["op"]
    combo.setCurrentIndex(combo.findData("rank"))
    assert visible("descending") and not visible("window")
    combo = content._card_widgets["ops"][0]["op"]
    combo.setCurrentIndex(combo.findData("row_number"))
    assert not visible("source")

    window.scene.history.undo()
    assert content.settings["ops"][0]["op"] == "rank"


def test_order_by_card_add_pick_undo(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    content._stacks["order_by"].add_button.click()
    assert content.settings["order_by"] == [{"column": "", "descending": False}]
    content._card_widgets["order_by"][0]["column"].set_selected(["d"], emit=True)
    assert content.settings["order_by"][0]["column"] == "d"
    history.undo()
    assert content.settings["order_by"][0]["column"] == ""
    history.undo()
    assert content.settings["order_by"] == []
    history.redo()
    assert len(content.settings["order_by"]) == 1


def test_add_remove_op_is_undoable_and_move_buttons_work(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    stack = content._stacks["ops"]
    stack.add_button.click()
    stack.add_button.click()
    assert len(content.settings["ops"]) == 2
    content.settings["ops"][1]["op"] = "row_number"
    content._list_change(content.FORM[1].fields[0], "move", 1, -1)
    assert content.settings["ops"][0]["op"] == "row_number"
    history.undo()
    assert content.settings["ops"][1]["op"] == "row_number"
    history.undo()
    history.undo()
    assert content.settings["ops"] == []


def test_row_number_live_output_needs_no_source(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    content.settings.update(
        {
            "partition_by": ["acct"],
            "order_by": [{"column": "d", "descending": False}],
            "ops": [{"op": "row_number", "name": "n"}],
        }
    )
    node.markDirty(True)
    node.eval()
    assert not node.isInvalid()
    assert node.value[0]["data"].collect()["n"].to_list() == [2, 1, 1]


def test_tds_round_trip_keeps_op_id_and_settings(qtbot, tmp_path) -> None:
    window, node, _dock = _node(qtbot)
    node.content.settings.update(
        {
            "partition_by": ["acct"],
            "order_by": [{"column": "d", "descending": True}],
            "ops": [
                {
                    "op": "rolling_sum",
                    "source": "amt",
                    "name": "r",
                    "offset": 1,
                    "window": 2,
                    "partial": True,
                    "descending": False,
                    "nulls": "zero",
                }
            ],
        }
    )
    path = tmp_path / "window.tds"
    window.scene.saveToFile(str(path))
    saved = orjson.loads(path.read_bytes())
    assert "transform.window" in [item.get("op") for item in saved["nodes"]]

    other = TriggerSubWindow()
    qtbot.addWidget(other)
    other.scene.loadFromFile(str(path))
    (loaded,) = [n for n in other.getAllNodes() if n.title == "Window"]
    for key, value in node.content.settings.items():
        assert loaded.content.settings[key] == value, key
    assert type(loaded).node_code is TransformNodes.WINDOW


def test_generated_code_matches_live_and_unwired_defines_output(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    node.content.settings.update(
        {
            "partition_by": ["acct"],
            "order_by": [{"column": "d", "descending": False}],
            "ops": [
                {"op": "cum_sum", "source": "amt", "name": "cs"},
                {"op": "row_number", "name": "n"},
            ],
        }
    )
    node.markDirty(True)
    node.eval()
    live = node.value[0]["data"].collect()
    namespace = {"var_src": FRAME}
    code = node.get_code()
    assert "core.shaping.window" in code and "_run_node" in code
    exec(code, {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    generated = namespace[node.content.variable_name].collect()
    assert generated.equals(live)
    assert live["cs"].to_list() == [15.0, 5.0, 7.0]

    bare = TriggerSubWindow()
    qtbot.addWidget(bare)
    lonely = get_class_from_opcode(TransformNodes.WINDOW, NodeTypes.TRANSFORM)(
        bare.scene
    )
    namespace = {}
    exec(lonely.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    for name in lonely.content.output_variables:
        assert name in namespace
