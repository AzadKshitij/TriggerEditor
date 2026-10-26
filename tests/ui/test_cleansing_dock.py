"""Cleansing uses the shaping form; options, fields and undo stay in sync."""

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
    return pl.DataFrame({"name": ["  a  ", "b!c"], "num": [1, 2]})


def _node(qtbot, frame=None):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, (frame or _frame()).lazy())
    cls = get_class_from_opcode(PreparationNodes.CLEANSING, NodeTypes.PREPARATION)
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


def test_dock_builds_all_sections(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    assert isinstance(content._widgets["selected_fields"], ColumnPicker)
    assert isinstance(content._widgets["case_modification"], NoWheelComboBox)
    assert content._widgets["selected_fields"].column_names() == ["name", "num"]
    assert content.settings["strip_whitespace"] is True
    # No fields chosen: the selected-columns null option is disabled.
    assert content._rows["selected_fields"] is not None
    assert (
        content._widgets["remove_null_rows_from_selected_columns"].isEnabled() is False
    )


def test_case_and_fields_change_the_output(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    picker = content._widgets["selected_fields"]
    case = content._widgets["case_modification"]

    picker.set_selected(["name"], emit=True)
    assert content._widgets["remove_null_rows_from_selected_columns"].isEnabled()
    case.setCurrentIndex(case.findData("upper"))
    assert content.settings["case_modification"] == "upper"
    assert _output(node)["name"].to_list() == ["A", "B!C"]

    # Selecting only the numeric column keeps the text untouched.
    picker.set_selected(["num"], emit=True)
    assert _output(node)["name"].to_list() == ["  a  ", "b!c"]


def test_undo_restores_option_and_output(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    picker = content._widgets["selected_fields"]
    picker.set_selected(["name"], emit=True)
    history.storeHistory("Baseline")
    case = content._widgets["case_modification"]

    case.setCurrentIndex(case.findData("upper"))
    assert _output(node)["name"].to_list() == ["A", "B!C"]

    history.undo()
    assert content.settings["case_modification"] == "none"
    assert content._widgets["case_modification"].currentData() == "none"
    assert _output(node)["name"].to_list() == ["a", "b!c"]

    history.redo()
    assert content.settings["case_modification"] == "upper"
    assert _output(node)["name"].to_list() == ["A", "B!C"]


def test_generated_code_matches_live(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("selected_fields", ["name"], "Cleansing Clean Changed")
    content.set_setting("case_modification", "upper", "Cleansing Case Changed")
    content.set_setting(
        "remove_punctuation", True, "Cleansing Remove punctuation Changed"
    )
    live = _output(node)

    namespace = {"var_src": _frame().lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = namespace[content.output_variables[0]].collect()
    assert generated.equals(live)


def test_serialize_round_trip(qtbot) -> None:
    window, source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("selected_fields", ["name"], "Cleansing Clean Changed")
    content.set_setting("case_modification", "upper", "Cleansing Case Changed")
    state = content.serialize()
    assert state["settings"]["case_modification"] == "upper"

    cls = get_class_from_opcode(PreparationNodes.CLEANSING, NodeTypes.PREPARATION)
    fresh = cls(window.scene)
    Edge(window.scene, source.outputs[0], fresh.inputs[0])
    assert fresh.content.deserialize(state) is not False
    fresh.markDirty(True)
    out = fresh.eval()
    assert out is not None and not fresh.isInvalid()
    assert out[0]["data"].collect().equals(node.value[0]["data"].collect())
