"""Rows uses the shaping core; type-dependent editors and undo stay in sync."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QDoubleSpinBox, QLineEdit, QSpinBox

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


def _node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, pl.DataFrame({"a": list(range(10))}).lazy())
    cls = get_class_from_opcode(
        PreparationNodes.DYNAMIC_ROW_BUILDER, NodeTypes.PREPARATION
    )
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


def test_dock_builds_typed_editors(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    assert isinstance(content.name_edit, QLineEdit)
    assert isinstance(content._value_widgets["initial_value"], QSpinBox)
    assert isinstance(content._value_widgets["increment_value"], QSpinBox)
    assert isinstance(content._value_widgets["max_value"], QSpinBox)
    assert content.type_combo.currentData() == "int"


def test_changing_values_changes_output(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content._value_widgets["initial_value"].setValue(2)
    content._value_widgets["max_value"].setValue(11)
    assert content.settings["initial_value"] == 2
    assert _output(node)["counter"].to_list() == list(range(2, 12))


def test_type_change_rebuilds_editors_and_undoes(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    content.type_combo.setCurrentIndex(content.type_combo.findData("float"))
    assert content.settings["field_type"] == "float"
    assert isinstance(content._value_widgets["initial_value"], QDoubleSpinBox)

    history.undo()
    assert content.settings["field_type"] == "int"
    assert isinstance(content._value_widgets["initial_value"], QSpinBox)


def test_maximum_hides_for_text_and_strings_are_generated(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    # Batch without evaluating the intermediate mixed-type states.
    content._suspend_node_evaluation = True
    try:
        content.set_setting("initial_value", "A", "Rows Start Changed")
        content.set_setting("increment_value", "", "Rows Increment Changed")
        content.set_setting("max_value", "Z", "Rows End Changed")
        content.set_setting("field_type", "string", "Rows Field type Changed")
    finally:
        content._suspend_node_evaluation = False

    assert isinstance(content._value_widgets["initial_value"], QLineEdit)
    assert content._value_rows["max_value"].isHidden() is True
    assert content.settings["field_type"] == "string"


def test_generated_code_matches_live(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("field_name", "item", "Rows Field name Changed")
    live = _output(node)

    namespace = {"var_src": pl.DataFrame({"a": list(range(10))}).lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = namespace[content.output_variables[0]].collect()
    assert generated.equals(live)


def test_serialize_round_trip(qtbot) -> None:
    window, source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("field_name", "item", "Rows Field name Changed")
    state = content.serialize()
    assert state["settings"]["field_name"] == "item"

    cls = get_class_from_opcode(
        PreparationNodes.DYNAMIC_ROW_BUILDER, NodeTypes.PREPARATION
    )
    fresh = cls(window.scene)
    Edge(window.scene, source.outputs[0], fresh.inputs[0])
    assert fresh.content.deserialize(state) is not False
    fresh.markDirty(True)
    out = fresh.eval()
    assert out is not None and not fresh.isInvalid()
    assert out[0]["data"].collect().equals(live_value(node)[0]["data"].collect())
