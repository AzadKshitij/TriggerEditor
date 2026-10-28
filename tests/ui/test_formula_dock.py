"""Formula cards: build from settings, edits, undo, validation and codegen."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QPushButton

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.nodes.Preparation import formula as formula_module


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


def _count_compute(monkeypatch, content):
    calls = []
    original = content.compute

    def counted():
        calls.append(1)
        return original()

    monkeypatch.setattr(content, "compute", counted)
    return calls


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


def test_text_editing_defers_compute_until_focus_out(qtbot, monkeypatch) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("sections", [_section("y", "")], "Baseline")
    calls = _count_compute(monkeypatch, content)
    editor = content.section_widgets[0]["formula_input"]

    editor.set_text("[x] + 1")
    qtbot.wait(350)

    assert calls == []
    assert content.settings["sections"][0]["formula_text"] == "[x] + 1"

    monkeypatch.setattr(content, "_sql_editor_has_focus", lambda: False)
    content._on_editor_finished(0)
    qtbot.wait(20)

    assert calls == [1]
    assert _output(node)["y"].to_list() == [2, 3, 4]

    # A second focus-out with no pending text must not compute again.
    content._on_editor_finished(0)
    qtbot.wait(20)
    assert calls == [1]


def test_formula_editors_coalesce_until_all_lose_focus(qtbot, monkeypatch) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting(
        "sections",
        [_section("y", ""), _section("z", "")],
        "Baseline",
    )
    calls = _count_compute(monkeypatch, content)
    first = content.section_widgets[0]["formula_input"]
    second = content.section_widgets[1]["formula_input"]

    first.set_text("[x] + 1")
    second.set_text("[x] * 2")
    qtbot.wait(350)
    assert calls == []

    monkeypatch.setattr(content, "_sql_editor_has_focus", lambda: True)
    content._on_editor_finished(0)
    qtbot.wait(20)
    assert calls == []

    monkeypatch.setattr(content, "_sql_editor_has_focus", lambda: False)
    content._on_editor_finished(1)
    qtbot.wait(20)

    assert calls == [1]
    output = _output(node)
    assert output["y"].to_list() == [2, 3, 4]
    assert output["z"].to_list() == [2, 4, 6]


def test_typing_marks_the_document_dirty_before_the_debounce(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    window.scene.has_been_modified = False
    editor = node.content.section_widgets[0]["formula_input"]

    editor.set_text("[x] + 1")

    assert window.scene.has_been_modified is True


def test_pending_text_is_flushed_without_evaluating(qtbot, monkeypatch) -> None:
    window, _source, node, dock = _node(qtbot)
    content = node.content
    content.set_setting("sections", [_section("y", "")], "Baseline")
    calls = _count_compute(monkeypatch, content)
    editor = content.section_widgets[0]["formula_input"]
    editor.set_text("[x] + 1")
    monkeypatch.setattr(window, "_find_config_dock", lambda: dock)

    window.commit_pending_config_edits(evaluate=False)

    assert content.settings["sections"][0]["formula_text"] == "[x] + 1"
    assert content.serialize()["settings"]["sections"][0]["formula_text"] == "[x] + 1"
    assert content._pending_evaluate is False
    assert calls == []


def test_new_column_dialog_cancel_keeps_deferred_evaluation(qtbot, monkeypatch) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("sections", [_section("y", "")], "Baseline")
    calls = _count_compute(monkeypatch, content)
    editor = content.section_widgets[0]["formula_input"]
    editor.set_text("[x] + 1")
    qtbot.wait(350)

    monkeypatch.setattr(
        formula_module.QInputDialog,
        "getText",
        staticmethod(lambda *args, **kwargs: ("", False)),
    )
    monkeypatch.setattr(content, "_sql_editor_has_focus", lambda: False)
    rebuilds = []
    monkeypatch.setattr(content, "_rebuild_cards", lambda: rebuilds.append(1))
    selector = content.section_widgets[0]["target_selector"]
    selector.setCurrentText(formula_module.NEW_COLUMN_OPTION)

    content._prompt_new_column(0, selector)
    qtbot.wait(20)

    assert selector.currentText() == "y"
    assert rebuilds == []
    assert content.settings["sections"][0]["formula_text"] == "[x] + 1"
    assert calls == [1]


def test_rebuild_cards_survives_a_deleted_layout(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.sections_layout.deleteLater()
    qtbot.wait(20)

    content._rebuild_cards()

    assert content.sections_layout is None
    assert content.section_widgets == []


def test_new_column_accept_sets_the_target(qtbot, monkeypatch) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    calls = _count_compute(monkeypatch, content)
    monkeypatch.setattr(
        formula_module.QInputDialog,
        "getText",
        staticmethod(lambda *args, **kwargs: ("new_col", True)),
    )
    selector = content.section_widgets[0]["target_selector"]
    selector.setCurrentText(formula_module.NEW_COLUMN_OPTION)

    content._prompt_new_column(0, selector)

    assert content.settings["sections"][0]["target_column"] == "new_col"
    assert content.section_widgets[0]["target_selector"].currentText() == "new_col"
    assert calls == [1]


def test_structural_change_still_evaluates_immediately(qtbot, monkeypatch) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("sections", [_section("y", "")], "Baseline")
    calls = _count_compute(monkeypatch, content)

    content.add_section_button.click()

    assert calls == [1]


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


def test_dtype_change_through_the_real_signal_is_saved(qtbot) -> None:
    """``activated`` carries the picked index; the slot must still be called."""
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("sections", [_section("y", "[x] + 1")], "Baseline")
    selector = content.section_widgets[0]["dtype_selector"]

    index = selector.findText("Float")
    selector.setCurrentIndex(index)
    selector.activated.emit(index)

    assert content.settings["sections"][0]["target_dtype"] == "Float"
    assert content.section_widgets[0]["dtype_selector"].currentText() == "Float"
    assert _output(node)["y"].dtype == pl.Float64


def test_target_change_through_the_real_signal_is_saved(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    selector = content.section_widgets[0]["target_selector"]

    index = selector.findText("x")
    selector.setCurrentIndex(index)
    selector.activated.emit(index)

    assert content.settings["sections"][0]["target_column"] == "x"


def test_remove_button_click_removes_the_card(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting(
        "sections", [_section("a", "[x]"), _section("b", "[x]")], "Baseline"
    )
    assert len(content.section_widgets) == 2

    card = content.section_widgets[1]["card"]
    remove = next(
        button
        for button in card.findChildren(QPushButton)
        if button.toolTip() == "Remove formula"
    )
    remove.click()

    assert len(content.settings["sections"]) == 1


def test_number_plus_empty_string_shows_a_live_error(qtbot) -> None:
    """The card reports the conversion failure while typing, not only on Run."""
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("sections", [_section("x", '[x] + ""')], "Baseline")

    content._refresh_error(0)

    assert 0 in content.section_errors
    assert "Could not convert string" in content.section_errors[0]
    assert not content.section_widgets[0]["error_label"].isHidden()


def test_late_error_enrichment_does_not_resurrect_a_fixed_error(qtbot) -> None:
    """The enrichment job finishes in the background, after the user's fix."""
    from trigger_designer.qt.helpers.error_enricher import EnrichResult

    window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("sections", [_section("y", '[x] + ""')], "Bad")
    error = node.current_error
    assert error is not None
    node.set_error(error, "run")  # what a failed Run records
    result = EnrichResult(root=error, knock_on=None, culprit_node_id=None)

    content.set_setting("sections", [_section("y", "[x] + 1")], "Fixed")
    assert node.current_error is None

    window._apply_enrichment(node, result, error)

    assert node.current_error is None


def test_enrichment_still_applies_while_the_run_error_stands(qtbot) -> None:
    from trigger_designer.qt.helpers.error_enricher import EnrichResult

    window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("sections", [_section("y", '[x] + ""')], "Bad")
    error = node.current_error
    node.set_error(error, "run")
    enriched = error.with_updates(locate_status="timeout")
    result = EnrichResult(root=enriched, knock_on=None, culprit_node_id=None)

    window._apply_enrichment(node, result, error)

    assert node._errors_dict()["run"].locate_status == "timeout"


def test_node_recovers_as_soon_as_the_text_is_valid_again(qtbot) -> None:
    """A red node must not wait for focus-out once the formula is fixed."""
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("sections", [_section("y", '[x] + ""')], "Bad")
    assert node.current_error is not None
    editor = content.section_widgets[0]["formula_input"]

    editor.set_text("[x] + 1")
    content._commit_text(0, evaluate=False)  # what the typing debounce does

    assert node.current_error is None
    assert _output(node)["y"].to_list() == [2, 3, 4]


def test_node_still_defers_while_the_text_stays_invalid(qtbot, monkeypatch) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("sections", [_section("y", '[x] + ""')], "Bad")
    calls = _count_compute(monkeypatch, content)
    editor = content.section_widgets[0]["formula_input"]

    editor.set_text('[x] + "z"')
    content._commit_text(0, evaluate=False)

    assert calls == []
