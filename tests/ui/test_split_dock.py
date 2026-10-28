"""Split uses the shaping form; mode, percent, undo and codegen stay in sync."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QSpinBox

from tests.support.flush import live_value
from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.common import NoWheelComboBox


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
    return pl.DataFrame({"v": list(range(10))})


def _node(qtbot, frame=None):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, (frame or _frame()).lazy())
    cls = get_class_from_opcode(PreparationNodes.SPLIT, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, source, node, dock


def test_dock_builds_mode_percent_and_seed(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    assert isinstance(content._widgets["is_random"], NoWheelComboBox)
    assert isinstance(content._widgets["estimation_percent"], QSpinBox)
    assert isinstance(content._widgets["random_seed"], QSpinBox)
    assert content.settings == {
        "estimation_percent": 70,
        "random_seed": 42,
        "is_random": True,
    }
    estimation, validation = (entry["data"].collect() for entry in live_value(node))
    assert estimation.height + validation.height == 10


def test_sequential_mode_reorders_and_hides_the_seed(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    combo = content._widgets["is_random"]
    combo.setCurrentIndex(combo.findData(False))
    assert content.settings["is_random"] is False
    assert content._rows["random_seed"].isHidden() is True

    estimation, validation = (entry["data"].collect() for entry in live_value(node))
    assert estimation["v"].to_list() == [0, 1, 2, 3, 4, 5, 6]
    assert validation["v"].to_list() == [7, 8, 9]


def test_percent_change_is_one_undo_step(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    spin = content._widgets["estimation_percent"]

    spin.setValue(50)
    qtbot.wait(350)
    assert content.settings["estimation_percent"] == 50
    assert node.content._widgets["estimation_percent"].value() == 50
    estimation, validation = (entry["data"].collect() for entry in live_value(node))
    assert estimation.height == 5
    assert validation.height == 5

    history.undo()
    assert content.settings["estimation_percent"] == 70
    assert node.content._widgets["estimation_percent"].value() == 70

    history.redo()
    assert content.settings["estimation_percent"] == 50


def test_generated_code_matches_both_live_outputs(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("is_random", False, "Split Method Changed")
    content.set_setting("estimation_percent", 60, "Split Estimation % Changed")
    live = [entry["data"].collect() for entry in live_value(node)]

    namespace = {"var_src": _frame().lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = [namespace[name].collect() for name in content.output_variables]
    assert generated[0].equals(live[0])
    assert generated[1].equals(live[1])


def test_serialize_round_trip(qtbot) -> None:
    window, source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("is_random", False, "Split Method Changed")
    content.set_setting("estimation_percent", 40, "Split Estimation % Changed")
    state = content.serialize()
    assert state["settings"]["estimation_percent"] == 40
    assert state["settings"]["is_random"] is False

    cls = get_class_from_opcode(PreparationNodes.SPLIT, NodeTypes.PREPARATION)
    fresh = cls(window.scene)
    Edge(window.scene, source.outputs[0], fresh.inputs[0])
    assert fresh.content.deserialize(state) is not False
    fresh.markDirty(True)
    out = fresh.eval()
    assert out is not None and not fresh.isInvalid()
    for index in (0, 1):
        assert out[index]["data"].collect().equals(live_value(node)[index]["data"].collect())
