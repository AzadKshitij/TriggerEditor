"""Formula cards: build from settings, edits, undo, validation and codegen."""

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
    return pl.DataFrame({"x": [1, 2, 3], "s": ["a", "b", "c"]})


def _node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, _frame().lazy())
    cls = get_class_from_opcode(PreparationNodes.FORMULA, NodeTypes.PREPARATION)
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


def _section(target: str, formula: str, dtype: str = "") -> dict:
    return {
        "target_column": target,
        "formula_text": formula,
        "editor_height": 120,
        "target_dtype": dtype,
    }


def test_cards_build_from_settings(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    assert len(content.section_widgets) == 1
    assert content.section_widgets[0]["formula_input"].height() == 120
    assert content.section_widgets[0]["target_selector"].count() >= 2


def test_target_and_text_edits_change_output(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    widgets = content.section_widgets[0]
    selector = widgets["target_selector"]
    selector.setCurrentText("x")
    content._on_target_selected(0, selector)
    assert content.settings["sections"][0]["target_column"] == "x"

    widgets = content.section_widgets[0]
    widgets["formula_input"].set_text("[x] + 1")
    content._commit_text(0)
    assert content.settings["sections"][0]["formula_text"] == "[x] + 1"
    assert _output(node)["x"].to_list() == [2, 3, 4]


def test_add_and_remove_cards(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")

    content.add_section_button.click()
    assert len(content.settings["sections"]) == 2
    assert len(content.section_widgets) == 2

    history.undo()
    assert len(content.settings["sections"]) == 1
    assert len(content.section_widgets) == 1

    history.redo()
    content._remove_section(1)
    assert len(content.settings["sections"]) == 1


def test_validation_callback_reports_bad_formula(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("sections", [_section("y", "[x] * 2")], "Formula Text Changed")
    assert content._validate_section(0, "[x] * 2") == []
    errors = content._validate_section(0, "(((")
    assert errors and errors[0]["message"]


def test_undo_text_burst_restores_editor(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    editor = content.section_widgets[0]["formula_input"]

    editor.set_text("[x] + 1")
    content._commit_text(0)
    assert content.settings["sections"][0]["formula_text"] == "[x] + 1"

    history.undo()
    assert content.settings["sections"][0]["formula_text"] == ""
    assert content.section_widgets[0]["formula_input"].get_text() == ""


def test_generated_code_matches_live(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("sections", [_section("y", "[x] * 2")], "Formula Text Changed")
    live = _output(node)

    namespace = {"var_src": _frame().lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = namespace[content.output_variables[0]].collect()
    assert generated.equals(live)


def test_serialize_round_trip(qtbot) -> None:
    window, source, node, _dock = _node(qtbot)
    content = node.content
    sections = [_section("y", "[x] * 2")]
    content.set_setting("sections", sections, "Formula Text Changed")
    state = content.serialize()
    assert state["settings"]["sections"] == sections

    cls = get_class_from_opcode(PreparationNodes.FORMULA, NodeTypes.PREPARATION)
    fresh = cls(window.scene)
    Edge(window.scene, source.outputs[0], fresh.inputs[0])
    assert fresh.content.deserialize(state) is not False
    fresh.markDirty(True)
    out = fresh.eval()
    assert out is not None and not fresh.isInvalid()
    assert out[0]["data"].collect().equals(node.value[0]["data"].collect())
