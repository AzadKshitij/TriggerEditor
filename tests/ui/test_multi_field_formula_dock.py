"""Multi-Field Formula dock: controls, undo/redo, errors and .tds round trip."""

from __future__ import annotations

import orjson
import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QLineEdit, QPlainTextEdit

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.common import ColumnPicker
from trigger_designer.qt.widgets.nodes.Preparation.multi_field_formula import (
    TriggerNode_MultiFieldFormula,
)

FRAME = pl.DataFrame({"a": [" x", "y "], "b": ["1", "2"], "n": [1, 2]}).lazy()


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
    source = Source(window.scene, FRAME)
    cls = get_class_from_opcode(
        PreparationNodes.MULTI_FIELD_FORMULA, NodeTypes.PREPARATION
    )
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, dock


def _result(node) -> pl.DataFrame:
    return node.value[0]["data"].collect()


def test_dock_has_the_documented_controls(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    widgets = node.content._widgets
    assert isinstance(widgets["columns"], ColumnPicker)
    assert isinstance(widgets["template"], QPlainTextEdit)
    assert isinstance(widgets["suffix"], QLineEdit)
    assert widgets["mode"].currentData() == "in_place"
    assert node.content._rows["suffix"].isHidden() is True


def test_node_is_registered_with_the_op_id(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = get_class_from_opcode(
        PreparationNodes.MULTI_FIELD_FORMULA, NodeTypes.PREPARATION
    )(window.scene)
    assert isinstance(node, TriggerNode_MultiFieldFormula)
    assert node.title == "Multi-Field Formula"
    assert node.serialize()["op"] == "preparation.multi_field_formula"
    assert len(node.inputs) == 1 and len(node.outputs) == 1


def test_formula_edit_is_live_and_one_undo_step(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    content.settings["columns"] = ["a"]
    history.storeHistory("Baseline")

    editor = content._widgets["template"]
    editor.setPlainText("UPPER(TRIM({col}))")
    qtbot.wait(350)
    assert content.settings["template"] == "UPPER(TRIM({col}))"
    assert node.content._pending_evaluate is True
    content.commit_pending_dock_edits()
    assert _result(node)["a"].to_list() == ["X", "Y"]
    assert content._widgets["template"] is editor

    history.undo()
    assert content.settings["template"] == ""
    assert editor.toPlainText() == ""
    history.redo()
    assert content.settings["template"] == "UPPER(TRIM({col}))"
    assert editor.toPlainText() == "UPPER(TRIM({col}))"


def test_typing_bursts_collapse_into_one_undo_step(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    editor = content._widgets["template"]
    for text in ("{col", "{col}", "{col} || 'x'"):
        editor.setPlainText(text)
        qtbot.wait(40)
    qtbot.wait(350)
    assert content.settings["template"] == "{col} || 'x'"
    history.undo()
    assert content.settings["template"] == ""


def test_column_picker_updates_in_place_and_undoes(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    picker = content._widgets["columns"]
    picker.set_selected(["a", "b"], emit=True)
    assert content.settings["columns"] == ["a", "b"]
    assert content._widgets["columns"] is picker
    history.undo()
    assert content.settings["columns"] == []
    history.redo()
    assert content.settings["columns"] == ["a", "b"]


def test_mode_switch_shows_suffix_and_adds_columns(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    content.settings["columns"] = ["n"]
    content.settings["template"] = "{col} * 2"
    history.storeHistory("Baseline")

    combo = content._widgets["mode"]
    combo.setCurrentIndex(combo.findData("suffix"))
    assert content.settings["mode"] == "suffix"
    assert content._rows["suffix"].isHidden() is False
    content.commit_pending_dock_edits()
    assert _result(node).columns == ["a", "b", "n", "n_new"]

    content._widgets["suffix"].setText("_x2")
    qtbot.wait(350)
    content.commit_pending_dock_edits()
    assert _result(node).columns == ["a", "b", "n", "n_x2"]
    assert _result(node)["n_x2"].to_list() == [2, 4]

    history.undo()
    history.undo()
    assert content.settings["mode"] == "in_place"
    assert content._rows["suffix"].isHidden() is True
    content.commit_pending_dock_edits()
    assert _result(node).columns == ["a", "b", "n"]


def test_invalid_template_marks_the_node_with_the_error_code(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    content.settings.update(
        {"columns": ["a"], "template": "{col}) FROM read_csv('x') --"}
    )
    node.markDirty(True)
    node.eval()
    assert node.isInvalid()
    content.settings["template"] = "UPPER({col})"
    node.markDirty(True)
    node.eval()
    assert not node.isInvalid()


def test_save_and_reload_round_trip(qtbot, tmp_path) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    cls = get_class_from_opcode(
        PreparationNodes.MULTI_FIELD_FORMULA, NodeTypes.PREPARATION
    )
    node = cls(window.scene)
    settings = {
        "columns": ["a", "b"],
        "template": "TRIM({col}) || '\"'",
        "mode": "suffix",
        "suffix": "_clean",
    }
    node.content.settings.update(settings)
    tds = tmp_path / "mff.tds"
    window.scene.saveToFile(str(tds))

    saved = orjson.loads(tds.read_bytes())
    assert [n.get("op") for n in saved["nodes"]] == ["preparation.multi_field_formula"]

    other = TriggerSubWindow()
    qtbot.addWidget(other)
    assert other.fileLoad(str(tds)) is True
    (loaded,) = other.getAllNodes()
    assert isinstance(loaded, TriggerNode_MultiFieldFormula)
    assert loaded.content.settings == settings
