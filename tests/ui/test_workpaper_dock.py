"""Workpaper Output dock: sections, debounce, undo, restore (offscreen)."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QCheckBox, QFileDialog, QLineEdit, QPlainTextEdit, QSpinBox

from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.common import EmptyStateLabel, NoWheelComboBox
from trigger_designer.qt.widgets.common.column_picker import ColumnPicker


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


def _node(qtbot, wired=True):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    frame = pl.DataFrame({"Invoice": ["a"], "Amount": [1.5], "Note": ["x"]}).lazy()
    node = get_class_from_opcode(IONodes.WORKPAPER_OUTPUT, NodeTypes.IO)(window.scene)
    if wired:
        source = Source(window.scene, frame)
        Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, dock


def test_dock_empty_state_without_exceptions_input(qtbot):
    _window, node, dock = _node(qtbot, wired=False)
    assert dock.findChildren(EmptyStateLabel)
    assert node.content._widgets == {}


def test_dock_sections_and_controls_exist(qtbot):
    _window, node, _dock = _node(qtbot)
    widgets = node.content._widgets
    assert isinstance(widgets["output_path"], QLineEdit)
    assert isinstance(widgets["if_exists"], NoWheelComboBox)
    assert isinstance(widgets["amount_column"], ColumnPicker)
    assert isinstance(widgets["objective"], QPlainTextEdit)
    assert isinstance(widgets["value_decimals"], QSpinBox)
    assert isinstance(widgets["include_run_log"], QCheckBox)
    assert isinstance(widgets["logo_path"], QLineEdit)
    assert widgets["output_path"].minimumHeight() >= 30
    assert node.content.dock_context()[0][0] == ("xlsx", "accent")


def test_text_edit_is_debounced_and_recorded_once(qtbot):
    window, node, _dock = _node(qtbot)
    history = window.scene.history
    history.storeHistory("Baseline")
    before = history.controller.count
    edit = node.content._widgets["client"]
    for text in ("A", "Ac", "Acm", "Acme"):
        edit.setText(text)
    qtbot.wait(450)
    assert node.content.settings["client"] == "Acme"
    assert history.controller.count - before == 1
    assert history.controller.undo_text().startswith("Workpaper Client")
    history.undo()
    assert node.content.settings["client"] == ""
    assert node.content._widgets["client"].text() == ""
    history.redo()
    assert node.content.settings["client"] == "Acme"


def test_if_exists_combo_maps_labels_to_values(qtbot):
    _window, node, _dock = _node(qtbot)
    combo = node.content._widgets["if_exists"]
    labels = [combo.itemText(i) for i in range(combo.count())]
    assert labels == ["New version", "Replace", "Stop with error"]
    combo.setCurrentIndex(combo.findData("replace"))
    assert node.content.settings["if_exists"] == "replace"
    assert node.content.dock_context()[0][2][0] == "replace"


def test_amount_column_picker_lists_exceptions_columns(qtbot):
    _window, node, _dock = _node(qtbot)
    picker = node.content._widgets["amount_column"]
    assert picker.column_names() == ["Invoice", "Amount", "Note"]
    node.content.set_setting(
        "amount_column", "Amount", "Workpaper Amount column Changed"
    )
    assert node.content.effective_spec().amount_column == "Amount"


def test_row_limit_spin_range_and_step(qtbot):
    _window, node, _dock = _node(qtbot)
    spin = node.content._widgets["row_limit"]
    assert (spin.minimum(), spin.maximum(), spin.singleStep()) == (1, 1_048_574, 10_000)
    spin.setValue(5_000_000)
    assert spin.value() == 1_048_574


def test_undo_does_not_rerecord_and_restores_widgets(qtbot):
    window, node, _dock = _node(qtbot)
    history = window.scene.history
    history.storeHistory("Baseline")
    node.content.set_setting("period", "FY25", "Workpaper Period Changed")
    depth = history.controller.count
    history.undo()
    assert node.content.settings["period"] == ""
    assert node.content._widgets["period"].text() == ""
    history.redo()
    assert node.content._widgets["period"].text() == "FY25"
    assert history.controller.count == depth


def test_dock_survives_force_rebuild_after_restore(qtbot):
    window, node, dock = _node(qtbot)
    window.scene.history.storeHistory("Baseline")
    node.content.set_setting("client", "Acme", "Workpaper Client Changed")
    window.scene.history.undo()
    dock.updateConfig([node.grNode], force=True)
    assert node.content._widgets["client"].text() == ""


def test_create_layout_direct_call_has_no_exception(qtbot):
    from qtpy.QtWidgets import QVBoxLayout, QWidget

    _window, node, _dock = _node(qtbot)
    host = QWidget()
    qtbot.addWidget(host)
    node.content.create_layout(QVBoxLayout(host))
    assert "output_path" in node.content._widgets


def test_browse_stores_the_chosen_path(qtbot, monkeypatch, clean_preferences, tmp_path):
    _window, node, _dock = _node(qtbot)
    target = str(tmp_path / "wp")
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (target, "Excel workbook (*.xlsx)"),
    )
    assert node.content.browse("output_path") == target + ".xlsx"
    qtbot.wait(450)
    assert node.content.settings["output_path"] == target + ".xlsx"
    assert clean_preferences.get("export/workpaper_dir") == str(tmp_path)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    assert node.content.browse("output_path") == ""
    assert node.content.settings["output_path"] == target + ".xlsx"


def test_placeholders_show_inherited_engagement_values(qtbot, clean_preferences):
    clean_preferences.set("engagement/client_name", "Pref Client")
    _window, node, _dock = _node(qtbot)
    assert node.content._widgets["client"].placeholderText() == "Pref Client"


def test_editing_never_writes_a_file(qtbot, tmp_path):
    _window, node, _dock = _node(qtbot)
    target = tmp_path / "never.xlsx"
    node.content.set_setting("output_path", str(target), "Workpaper File Changed")
    qtbot.wait(100)
    assert not target.exists()
