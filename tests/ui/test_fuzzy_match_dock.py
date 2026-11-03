"""Fuzzy Match dock: controls, undo/redo, generated code and the .tds round trip."""

from __future__ import annotations

import json

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QCheckBox, QDoubleSpinBox, QLabel, QSpinBox

from tests.support.flush import flush, live_value
from trigger_designer.core.node_configuration import (
    JoinNodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.common import ColumnPicker, NoWheelComboBox
from trigger_designer.qt.widgets.nodes.Join.fuzzy_match import TriggerNode_FuzzyMatch

LEFT = pl.DataFrame(
    {
        "Vendor": ["ACME Corp.", "Globex, Inc", "Initech LLC", "Hooli", None],
        "Region": ["N", "S", "N", "S", "N"],
        "id": [1, 2, 3, 4, 5],
    }
)
RIGHT = pl.DataFrame(
    {
        "Supplier": ["Acme Corporation", "GLOBEX INC.", "Initec", "Pied Piper"],
        "Area": ["N", "S", "S", "N"],
        "ref": list("abcd"),
    }
)


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


def _node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    left = Source(window.scene, LEFT.lazy(), "var_left")
    right = Source(window.scene, RIGHT.lazy(), "var_right")
    node = get_class_from_opcode(JoinNodes.FUZZY_MATCH, NodeTypes.JOIN)(window.scene)
    Edge(window.scene, left.outputs[0], node.inputs[0])
    Edge(window.scene, right.outputs[0], node.inputs[1])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, dock


def _pick_columns(node) -> None:
    widgets = node.content._widgets
    widgets["left_column"].set_selected(["Vendor"], emit=True)
    widgets["right_column"].set_selected(["Supplier"], emit=True)


def _outputs(node) -> list[pl.DataFrame]:
    return [entry["data"].collect() for entry in live_value(node)]


def test_node_identity_and_sockets(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    assert isinstance(node, TriggerNode_FuzzyMatch)
    assert node.node_title == "Fuzzy Match"
    assert len(node.inputs) == 2 and len(node.outputs) == 3
    assert node.serialize()["op"] == "join.fuzzy_match"


def test_dock_builds_controls_and_summary(qtbot) -> None:
    _window, node, dock = _node(qtbot)
    widgets = node.content._widgets
    assert isinstance(widgets["left_column"], ColumnPicker)
    assert isinstance(widgets["right_column"], ColumnPicker)
    assert isinstance(widgets["algorithm"], NoWheelComboBox)
    assert isinstance(widgets["threshold"], QDoubleSpinBox)
    assert isinstance(widgets["strip_suffixes"], QCheckBox)
    assert isinstance(widgets["assignment"], NoWheelComboBox)
    assert isinstance(widgets["blocking"], NoWheelComboBox)
    assert isinstance(widgets["prefix_length"], QSpinBox)
    assert "block_columns" in node.content._stacks
    # each side offers only its own input's text columns (id is a number)
    assert widgets["left_column"].column_names() == ["Vendor", "Region"]
    assert widgets["right_column"].column_names() == ["Supplier", "Area", "ref"]
    summary = [
        label
        for label in dock.findChildren(QLabel)
        if label.objectName() == "ConfigSummary"
    ]
    assert summary and "2 inputs" in summary[0].text()
    assert "3 outputs" in summary[0].text()
    assert "M matched" in summary[0].text()
    assert widgets["threshold"].singleStep() == 0.01


def test_unconfigured_node_reports_a_shaping_error(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    assert node.isInvalid()


def test_choosing_columns_produces_three_outputs(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    _pick_columns(node)
    matched, left, right = _outputs(node)
    assert not node.isInvalid()
    assert matched.select("id", "ref").rows() == [(1, "a"), (2, "b"), (3, "c")]
    assert left["id"].to_list() == [4, 5]
    assert right["ref"].to_list() == ["d"]


def test_undo_and_redo_restore_settings_widgets_and_output(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    _pick_columns(node)
    history.storeHistory("Baseline")

    picker = content._widgets["left_column"]
    picker.set_selected(["Region"], emit=True)
    assert content.settings["left_column"] == "Region"
    assert history.canUndo()
    history.undo()
    assert content.settings["left_column"] == "Vendor"
    assert content._widgets["left_column"] is picker
    assert picker.column_names()  # still populated
    assert [entry for entry in picker.selected()] == ["Vendor"]
    history.redo()
    assert content.settings["left_column"] == "Region"


def test_combo_and_check_changes_are_single_undo_steps(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    _pick_columns(node)
    history.storeHistory("Baseline")

    combo = content._widgets["assignment"]
    combo.setCurrentIndex(combo.findData("all_pairs"))
    assert content.settings["assignment"] == "all_pairs"
    history.undo()
    assert content.settings["assignment"] == "one_to_one"
    assert combo.currentData() == "one_to_one"
    history.redo()
    assert content.settings["assignment"] == "all_pairs"

    check = content._widgets["strip_suffixes"]
    check.setChecked(False)
    assert content.settings["strip_suffixes"] is False
    history.undo()
    assert content.settings["strip_suffixes"] is True
    assert check.isChecked() is True


def test_threshold_edit_is_debounced_undoable_and_changes_output(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    _pick_columns(node)
    history.storeHistory("Baseline")

    spin = content._widgets["threshold"]
    spin.setValue(1.0)
    qtbot.wait(350)
    assert content.settings["threshold"] == 1.0
    matched = _outputs(node)[0]
    assert matched["id"].to_list() == [1, 2]  # only the identical names remain
    assert history.canUndo()
    history.undo()
    assert content.settings["threshold"] == 0.85
    assert spin.value() == 0.85
    assert content._widgets["threshold"] is spin
    history.redo()
    assert content.settings["threshold"] == 1.0


def test_blocking_mode_toggles_the_prefix_length_row(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    assert content._rows["prefix_length"].isHidden() is False
    combo = content._widgets["blocking"]
    combo.setCurrentIndex(combo.findData("none"))
    assert content.settings["blocking"] == "none"
    assert content._rows["prefix_length"].isHidden() is True
    combo.setCurrentIndex(combo.findData("prefix"))
    assert content._rows["prefix_length"].isHidden() is False


def test_block_column_pairs_add_pick_and_undo(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    _pick_columns(node)
    history.storeHistory("Baseline")

    stack = content._stacks["block_columns"]
    stack.add_button.click()
    assert content.settings["block_columns"] == [{"left": "", "right": ""}]
    widgets = content._card_widgets["block_columns"][0]
    widgets["left"].set_selected(["Region"], emit=True)
    widgets["right"].set_selected(["Area"], emit=True)
    assert content.settings["block_columns"] == [{"left": "Region", "right": "Area"}]

    matched = _outputs(node)[0]
    # Initech (N) is no longer paired with Initec (S) once regions must match
    assert matched["id"].to_list() == [1, 2]

    history.undo()
    history.undo()
    assert content.settings["block_columns"] == [{"left": "", "right": ""}]
    history.undo()
    assert content.settings["block_columns"] == []
    assert len(content._stacks["block_columns"]._cards) == 0


def test_generated_code_matches_live(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    _pick_columns(node)
    content.set_setting("algorithm", "levenshtein", "Fuzzy Match Algorithm Changed")
    content.set_setting("threshold", 0.7, "Fuzzy Match Minimum score Changed")
    content.set_setting(
        "block_columns",
        [{"left": "Region", "right": "Area"}],
        "Fuzzy Match Must also match Changed",
        structural=True,
    )
    live = _outputs(node)

    namespace = {"var_left": LEFT.lazy(), "var_right": RIGHT.lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = [namespace[name].collect() for name in content.output_variables]
    assert len(generated) == 3
    for mine, theirs in zip(generated, live):
        assert mine.equals(theirs)
    assert generated[0].height >= 1


def test_generated_code_never_interpolates_column_text_raw(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    hostile = 'V"; __import__("os").system("x") #\''
    content.settings["left_column"] = hostile
    content.settings["right_column"] = "Supplier"
    content.input_vars = ["var_left", "var_right"]
    code = content.get_code()
    assert "json.loads(" in code
    assert hostile not in code  # only the json-escaped repr appears
    compile(code, "<generated>", "exec")


def test_unwired_node_defines_every_output_variable(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = get_class_from_opcode(JoinNodes.FUZZY_MATCH, NodeTypes.JOIN)(window.scene)
    namespace: dict = {}
    exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    for variable in node.content.output_variables:
        assert variable in namespace
    assert len(node.content.output_variables) == 3

    # one input wired is still incomplete: both inputs are required
    source = Source(window.scene, LEFT.lazy(), "var_left")
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    namespace = {}
    exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    for variable in node.content.output_variables:
        assert variable in namespace


def test_save_and_reload_keeps_the_op_id_and_settings(qtbot, tmp_path) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = TriggerNode_FuzzyMatch(window.scene)
    node.content.settings.update(
        {
            "left_column": "Vendor",
            "right_column": "Supplier",
            "algorithm": "levenshtein",
            "threshold": 0.7,
            "blocking": "first_token",
            "prefix_length": 4,
            "block_columns": [{"left": "Region", "right": "Area"}],
            "strip_suffixes": False,
            "assignment": "all_pairs",
        }
    )
    expected = dict(node.content.settings)
    path = tmp_path / "fuzzy.tds"
    window.scene.saveToFile(str(path))

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [n.get("op") for n in saved["nodes"]] == ["join.fuzzy_match"]

    reloaded = TriggerSubWindow()
    qtbot.addWidget(reloaded)
    assert reloaded.fileLoad(str(path)) is True
    (loaded,) = reloaded.getAllNodes()
    assert isinstance(loaded, TriggerNode_FuzzyMatch)
    assert loaded.content.settings == expected
    assert loaded.content.output_variables == [
        f"var_fuzzy_matched_{loaded.content.id}",
        f"var_fuzzy_left_{loaded.content.id}",
        f"var_fuzzy_right_{loaded.content.id}",
    ]


def test_one_source_can_feed_both_inputs(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    names = pl.DataFrame({"n": ["acme corp", "globex"], "i": [1, 2]})
    source = Source(window.scene, names.lazy(), "var_names")
    node = get_class_from_opcode(JoinNodes.FUZZY_MATCH, NodeTypes.JOIN)(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    Edge(window.scene, source.outputs[0], node.inputs[1])
    node.content.settings["left_column"] = "n"
    node.content.settings["right_column"] = "n"
    node.markDirty(True)
    node.eval()
    flush(node)
    assert not node.isInvalid()
    matched = node.value[0]["data"].collect()
    assert matched.select("i", "i_right").rows() == [(1, 1), (2, 2)]
