"""The Duplicates node's Config Dock: controls, undo/redo, Count and persistence."""

from __future__ import annotations

import datetime as dt

import orjson
import polars as pl
from qtpy.QtWidgets import QVBoxLayout, QWidget

from tests.support.audit_demo import demo_graph
from trigger_designer.core.audit.duplicates import DuplicatesParams
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.widgets.common import (
    ColumnChecklist,
    ColumnPicker,
    ConfigSection,
    IconButton,
    TextButton,
)
from trigger_designer.qt.widgets.nodes.Audit._base import COUNT_TOOLTIP
from trigger_designer.qt.widgets.nodes.Audit.duplicates import TriggerNode_Duplicates

KEYS = ["vendor", "inv"]
FRAME = pl.DataFrame(
    {
        "vendor": ["A", "A", "A", "B", "B", "A", None, None, "a ", "C"],
        "inv": [1, 1, 1, 7, 7, 2, 9, 9, 1, 5],
        "amt": [
            "100.00",
            "100.00",
            "100.40",
            "50",
            "50.00",
            "(25)",
            "5",
            "5",
            "100",
            "x",
        ],
        "date": [dt.date(2024, 1, d) for d in (1, 2, 20, 1, 1, 1, 1, 1, 1, 1)],
    }
).lazy()


def _dock(qtbot, **settings):
    window, source, node = demo_graph(FRAME, TriggerNode_Duplicates)
    qtbot.addWidget(window)
    for name, value in settings.items():
        setattr(node.content, name, value)
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    node.scene.history.storeHistory("Baseline")
    return window, source, node, dock


def _height(node, socket: int = 0) -> int:
    return node.value[socket]["data"].collect().height


def test_dock_builds_with_every_section_owning_its_undo(qtbot) -> None:
    _window, _source, node, dock = _dock(qtbot, key_columns=KEYS)
    content = node.content
    sections = dock.dock_widget.findChildren(ConfigSection)
    titles = [s._title.text() for s in sections if s._title is not None]
    assert titles == ["MATCH ON", "MATCH TYPE", "NEAR MATCH", "VALUE", "RESULT"]
    assert all(s._undo_composite for s in sections)
    assert isinstance(content.keys_list, ColumnChecklist)
    assert content.keys_list.checked() == KEYS
    assert list(content.keys_list.checkboxes) == ["vendor", "inv", "amt", "date"]
    pickers = dock.dock_widget.findChildren(ColumnPicker)
    assert [p.accessibleName().split(":")[0] for p in pickers] == [
        "Amount",
        "Date",
        "Value",
    ]
    assert content.format_combo.count() == 5
    assert content.window_spin.suffix() == " days"
    assert content.mode_control.toolTip().startswith("Near matching also groups")
    assert content.dock_context() == (
        [("2 key columns", "accent"), ("exact", "muted")],
        "",
    )


def test_dock_builds_without_input(qtbot) -> None:
    window, _source, _node, _unused = _dock(qtbot)
    fresh = TriggerNode_Duplicates(window.scene)
    holder = QWidget()
    layout = QVBoxLayout(holder)
    fresh.content.create_layout(layout)
    assert layout.count() == 1
    assert layout.itemAt(0).widget().objectName() == "EmptyStateLabel"


def test_the_dock_uses_icon_buttons_and_only_the_bulk_text_buttons(qtbot) -> None:
    _window, _source, node, dock = _dock(qtbot, key_columns=KEYS)
    assert dock.dock_widget.findChildren(IconButton)
    texts = dock.dock_widget.findChildren(TextButton)
    assert sorted(b.text() for b in texts) == ["All", "None"]
    assert all(b.objectName() == "BulkButton" and b.toolTip() for b in texts)
    assert node.content.all_btn.accessibleName()


def test_ticking_keys_reevaluates_and_each_click_is_one_undo_step(qtbot) -> None:
    window, _source, node, _unused = _dock(qtbot)
    content = node.content
    history = window.scene.history
    assert node.isInvalid() and node.current_error.code == "TD-AUDIT-001"

    content.keys_list.checkboxes["vendor"].setChecked(True)
    assert content.key_columns == ["vendor"]
    assert history.controller.count == 1
    assert history.currentText() == "Duplicate Keys Changed"
    content.keys_list.checkboxes["inv"].setChecked(True)
    assert content.key_columns == ["vendor", "inv"]
    assert history.controller.count == 2
    assert not node.isInvalid()
    assert _height(node) == 5 and _height(node, 1) == 5

    history.undo()
    assert content.key_columns == ["vendor"]
    assert content.keys_list.checked() == ["vendor"]
    history.undo()
    assert content.key_columns == []
    assert content.keys_list.checked() == []
    assert node.isInvalid() and "TD-AUDIT-001" in node._node_tooltip()
    history.redo()
    history.redo()
    assert content.key_columns == ["vendor", "inv"] and _height(node) == 5
    assert content.keys_list.checked() == ["vendor", "inv"]


def test_all_and_none_buttons_are_one_step_each(qtbot) -> None:
    window, _source, node, _unused = _dock(qtbot)
    content = node.content
    history = window.scene.history
    content.all_btn.click()
    assert content.key_columns == ["vendor", "inv", "amt", "date"]
    assert history.controller.count == 1
    content.none_btn.click()
    assert content.key_columns == [] and history.controller.count == 2
    history.undo()
    assert content.keys_list.checked() == ["vendor", "inv", "amt", "date"]


def test_trim_and_case_checks_are_discrete_undo_steps(qtbot) -> None:
    window, _source, node, _unused = _dock(qtbot, key_columns=KEYS)
    content = node.content
    history = window.scene.history
    assert content.trim_check.isChecked() and not content.case_check.isChecked()
    content.case_check.setChecked(True)
    assert content.ignore_case is True and _height(node) == 6
    assert history.currentText() == "Duplicate Case Changed"
    content.trim_check.setChecked(False)
    assert content.trim_text is False and history.controller.count == 2
    assert history.currentText() == "Duplicate Trim Changed"
    history.undo()
    assert content.trim_text is True and content.trim_check.isChecked()
    history.undo()
    assert content.ignore_case is False and not content.case_check.isChecked()
    assert _height(node) == 5


def test_mode_switch_shows_the_near_section_and_undo_hides_it(qtbot) -> None:
    window, _source, node, _unused = _dock(qtbot, key_columns=KEYS)
    content = node.content
    history = window.scene.history
    assert content.near_section.isHidden()
    content.mode_control._buttons["Near"].click()
    assert content.mode == "near"
    assert not content.near_section.isHidden()
    assert history.currentText() == "Duplicate Match Type Changed"
    # Near with neither amount nor date chosen is a configuration error.
    assert node.isInvalid() and node.current_error.code == "TD-AUDIT-001"
    history.undo()
    assert content.mode == "exact" and content.mode_control.value() == "Exact"
    assert content.near_section.isHidden()
    assert not node.isInvalid()
    history.redo()
    assert content.mode == "near" and not content.near_section.isHidden()


def test_near_controls_commit_and_evaluate(qtbot) -> None:
    window, _source, node, _unused = _dock(qtbot, key_columns=KEYS, mode="near")
    content = node.content
    history = window.scene.history
    content.amount_picker._toggle_name("amt")
    assert content.amount_column == "amt"
    assert history.currentText() == "Duplicate Amount Changed"
    content.tolerance_spin.setValue(0.5)
    assert content.tolerance == 0.5
    content.date_picker._toggle_name("date")
    assert content.date_column == "date"
    content.window_spin.setValue(3)
    assert content.window_days == 3
    assert not node.isInvalid()
    assert _height(node) == 4  # rows 0, 1 (A,1) and 3, 4 (B,7)

    content.tolerance_kind_control._buttons["Percent"].click()
    assert content.tolerance_kind == "percent"
    assert history.currentText() == "Duplicate Tolerance Kind Changed"
    content.format_combo.setCurrentIndex(1)
    assert content.date_format == "%d/%m/%Y"
    assert history.currentText() == "Duplicate Date Format Changed"
    history.undo()
    assert content.date_format == "%Y-%m-%d"
    assert content.format_combo.currentData() == "%Y-%m-%d"
    history.undo()
    assert content.tolerance_kind == "absolute"
    assert content.tolerance_kind_control.value() == "Amount"


def test_tolerance_and_window_spin_bursts_merge_into_one_step(qtbot) -> None:
    window, _source, node, _unused = _dock(
        qtbot, key_columns=KEYS, mode="near", amount_column="amt", date_column="date"
    )
    content = node.content
    history = window.scene.history
    before = history.controller.count
    for value in (0.1, 0.2, 0.5):
        content.tolerance_spin.setValue(value)
    assert history.controller.count == before + 1
    for value in (1, 2, 3):
        content.window_spin.setValue(value)
    assert history.controller.count == before + 2
    history.undo()
    assert content.window_days == 0 and content.window_spin.value() == 0
    history.undo()
    assert content.tolerance == 0.0 and content.tolerance_spin.value() == 0.0
    history.redo()
    assert content.tolerance == 0.5


def test_value_column_picker_is_blank_able_and_undoable(qtbot) -> None:
    window, _source, node, _unused = _dock(qtbot, key_columns=["vendor"])
    content = node.content
    content.value_picker._toggle_name("amt")
    assert content.value_column == "amt"
    summary = node.value[2]["data"].collect().row(0, named=True)
    assert summary["population_value"] == 535.4
    assert (
        summary["exception_value"] == 425.4
    )  # A x4 (100, 100, 100.4, 25), B x2 (50, 50)
    assert window.scene.history.currentText() == "Duplicate Value Column Changed"
    window.scene.history.undo()
    assert content.value_column == "" and content.value_picker.checked() == []


def test_a_saved_key_the_input_lost_stays_visible_and_errors(qtbot) -> None:
    _window, _source, node, _unused = _dock(qtbot, key_columns=["vendor", "gone"])
    assert node.current_error.code == "TD-AUDIT-002"
    assert "gone" in node.content.keys_list.checkboxes
    assert node.content.keys_list.checked() == ["vendor", "gone"]


def test_count_button_sets_test_summary_and_leaves_history_alone(qtbot) -> None:
    window, _source, node, dock = _dock(qtbot, key_columns=KEYS)
    content = node.content
    history = window.scene.history
    button = next(
        b
        for b in dock.dock_widget.findChildren(IconButton)
        if b.accessibleName() == COUNT_TOOLTIP
    )
    assert "Not counted" in content.summary_label.text()
    steps = history.controller.count
    button.click()
    assert content.test_summary.exception_rows == 5
    assert (
        content.summary_label.text() == "FAIL: 5 of 10 rows are in 2 duplicate groups."
    )
    assert history.controller.count == steps
    content.case_check.setChecked(True)  # an edit makes the count stale
    assert content.test_summary is None
    assert "Not counted" in content.summary_label.text()


def test_undo_does_not_record_its_own_write_back(qtbot) -> None:
    window, _source, node, _unused = _dock(qtbot, key_columns=KEYS)
    history = window.scene.history
    node.content.case_check.setChecked(True)
    count = history.controller.count
    history.undo()
    history.redo()
    assert history.controller.count == count
    assert node.content.ignore_case is True


def test_dock_rebuild_after_restore_keeps_the_model(qtbot) -> None:
    _window, _source, node, dock = _dock(qtbot, key_columns=KEYS)
    content = node.content
    content.mode_control._buttons["Near"].click()
    old = content.keys_list
    dock.updateConfig([node.grNode], force=True)
    assert content.keys_list is not old
    assert content.keys_list.checked() == KEYS
    assert content.mode_control.value() == "Near"
    assert not content.near_section.isHidden()


def test_registered_node_survives_save_and_reload(qtbot, tmp_path) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = TriggerNode_Duplicates(window.scene)
    settings = {
        "key_columns": ["vendor", "inv"],
        "mode": "near",
        "trim_text": False,
        "ignore_case": True,
        "amount_column": "amt",
        "tolerance_kind": "percent",
        "tolerance": 2.5,
        "date_column": "date",
        "date_format": "%d/%m/%Y",
        "window_days": 5,
        "value_column": "amt",
    }
    for name, value in settings.items():
        setattr(node.content, name, value)
    tds = tmp_path / "dup.tds"
    window.scene.saveToFile(str(tds))

    saved = orjson.loads(tds.read_bytes())
    ops = [n.get("op") for n in saved["nodes"]]
    assert ops == ["audit.duplicates"]
    for name, value in settings.items():
        assert saved["nodes"][0]["content"][name] == value

    other = TriggerSubWindow()
    qtbot.addWidget(other)
    assert other.fileLoad(str(tds)) is True
    (loaded,) = other.getAllNodes()
    assert isinstance(loaded, TriggerNode_Duplicates)
    assert loaded.title == "Duplicates"
    assert loaded.content.params() == DuplicatesParams(**settings)
    assert [s.socket_type for s in loaded.outputs] == [3, 3, 1]
