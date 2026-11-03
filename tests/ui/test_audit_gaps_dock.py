"""The Gaps node's Config Dock: controls -> model -> evaluation -> one undo step."""

from __future__ import annotations

import json

import polars as pl
from qtpy.QtWidgets import QVBoxLayout, QWidget

from tests.support.audit_demo import demo_graph
from trigger_designer.core.audit.gaps import GapsParams
from trigger_designer.core.node_configuration import (
    NODE_REGISTRIES,
    AuditNodes,
    NodeTypes,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.widgets.common import IconButton, TextButton
from trigger_designer.qt.widgets.nodes.Audit._base import COUNT_TOOLTIP
from trigger_designer.qt.widgets.nodes.Audit.gaps import TriggerNode_Gaps

FRAME = pl.DataFrame(
    {
        "je": ["JE-001", "JE-002", "JE-005", "JE-005", "JE-004", "X-1"],
        "led": ["A", "A", "A", "A", "A", "B"],
        "d": [
            "2024-03-01",
            "2024-03-04",
            "2024-03-05",
            "2024-03-09",
            "2024-03-15",
            "2024-03-15",
        ],
    }
).lazy()


def _dock(qtbot, **settings):
    window, source, node = demo_graph(FRAME, TriggerNode_Gaps)
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


def _found(node) -> pl.DataFrame:
    return node.value[0]["data"].collect()


def test_dock_builds_every_section_and_owns_its_undo(qtbot) -> None:
    _window, _source, node, dock = _dock(qtbot, sequence_column="je")
    content = node.content
    sections = dock.dock_widget.findChildren(type(content.section("x")))
    assert len(sections) >= 6 and all(s._undo_composite for s in sections)
    assert set(content._bindings) == {
        "sequence_column",
        "mode",
        "group_columns",
        "report_duplicates",
        "report_out_of_order",
        "range_start",
        "range_end",
        "date_format",
        "min_gap_days",
        "business_days_only",
        "holidays",
    }
    assert set(content.group_list.checkboxes) == {"je", "led", "d"}
    # Icon-first: the only text buttons are the paired All / None.
    assert {b.text() for b in dock.dock_widget.findChildren(TextButton)} == {
        "All",
        "None",
    }
    assert dock.dock_widget.findChildren(IconButton)


def test_without_input_the_dock_shows_the_empty_state(qtbot) -> None:
    window, _source, _node, _dock_unused = _dock(qtbot)
    fresh = TriggerNode_Gaps(window.scene)
    holder = QWidget()
    layout = QVBoxLayout(holder)
    fresh.content.create_layout(layout)
    assert layout.count() == 1
    assert layout.itemAt(0).widget().objectName() == "EmptyStateLabel"


def test_column_pick_evaluates_and_undoes_as_one_step(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot)
    content = node.content
    history = window.scene.history
    assert node.isInvalid() and node.current_error.code == "TD-AUDIT-001"

    content.column_picker._toggle_name("je")
    assert content.sequence_column == "je" and not node.isInvalid()
    assert history.controller.count == 1
    assert history.currentText() == "Gaps Column Changed"
    assert set(_found(node)["finding"]) == {"gap", "duplicate", "out_of_order"}

    history.undo()
    assert content.sequence_column == "" and content.column_picker.checked() == []
    assert node.isInvalid()
    history.redo()
    assert content.column_picker.checked() == ["je"] and not node.isInvalid()


def test_mode_switch_shows_and_hides_sections_and_undoes(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, sequence_column="d")
    content = node.content
    history = window.scene.history
    assert not content.report_section.isHidden()
    assert not content.range_section.isHidden()
    assert content.dates_section.isHidden()

    content.mode_control._buttons["Date"].click()
    assert content.mode == "date"
    assert content.report_section.isHidden() and content.range_section.isHidden()
    assert history.currentText() == "Gaps Type Changed"
    assert set(_found(node)["finding"]) == {"date_gap"}
    assert not content.dates_section.isHidden()

    history.undo()
    assert content.mode == "prefixed" and content.mode_control.value() == "Prefixed"
    assert content.dates_section.isHidden() and not content.report_section.isHidden()
    history.redo()
    assert content.mode == "date" and content.report_section.isHidden()


def test_holidays_row_follows_skip_weekends(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, sequence_column="d", mode="date")
    content = node.content
    assert content.holidays_row.isHidden()
    content.weekend_check.setChecked(True)
    assert content.business_days_only is True and not content.holidays_row.isHidden()
    assert window.scene.history.currentText() == "Gaps Weekends Changed"
    window.scene.history.undo()
    assert content.business_days_only is False and content.holidays_row.isHidden()
    assert not content.weekend_check.isChecked()


def test_group_checklist_all_none_and_undo(qtbot) -> None:
    window, _source, node, dock = _dock(qtbot, sequence_column="je")
    content = node.content
    history = window.scene.history
    buttons = {b.text(): b for b in dock.dock_widget.findChildren(TextButton)}
    before = history.controller.count

    content.group_list.checkboxes["led"].setChecked(True)
    assert content.group_columns == ["led"]
    assert "led" in _found(node).columns
    assert history.controller.count == before + 1
    assert history.currentText() == "Gaps Groups Changed"

    buttons["All"].click()
    assert sorted(content.group_columns) == ["d", "je", "led"]
    assert history.controller.count == before + 2  # one step for the bulk click
    buttons["None"].click()
    assert content.group_columns == []
    assert history.controller.count == before + 3

    history.undo()
    assert sorted(content.group_columns) == ["d", "je", "led"]
    history.undo()
    assert content.group_columns == ["led"]
    assert content.group_list.checked() == ["led"]
    history.undo()
    assert content.group_columns == [] and content.group_list.checked() == []


def test_report_checks_write_the_model_and_the_findings(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, sequence_column="je")
    content = node.content
    history = window.scene.history
    content.duplicates_check.setChecked(False)
    assert content.report_duplicates is False
    assert "duplicate" not in set(_found(node)["finding"])
    assert history.currentText() == "Gaps Repeats Changed"
    content.order_check.setChecked(False)
    assert history.currentText() == "Gaps Order Changed"
    assert set(_found(node)["finding"]) == {"gap"}
    history.undo()
    history.undo()
    assert content.duplicates_check.isChecked() and content.order_check.isChecked()


def test_expected_range_spins_map_the_special_value_to_none(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, sequence_column="je")
    content = node.content
    history = window.scene.history
    assert content.range_start is None
    assert content.start_spin.specialValueText() == "Lowest seen"
    assert content.end_spin.specialValueText() == "Highest seen"
    assert content.start_spin.value() == content.start_spin.minimum()

    before = history.controller.count
    for value in (1, 12, 120):  # one burst while spinning
        content.start_spin.setValue(value)
    assert content.range_start == 120
    assert history.controller.count == before + 1
    content.end_spin.setValue(130)
    assert content.range_end == 130

    history.undo()
    assert content.range_end is None
    assert content.end_spin.value() == content.end_spin.minimum()
    history.undo()
    assert content.range_start is None
    content.start_spin.setValue(3)
    content.start_spin.setValue(content.start_spin.minimum())
    assert content.range_start is None


def test_date_controls_commit_and_undo(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, sequence_column="d", mode="date")
    content = node.content
    history = window.scene.history

    content.format_combo.setCurrentIndex(1)
    assert content.date_format == "%d/%m/%Y"
    assert history.currentText() == "Gaps Date Format Changed"
    assert node.value is not None  # a different reading still evaluates
    history.undo()
    assert content.date_format == "%Y-%m-%d"
    assert content.format_combo.currentData() == "%Y-%m-%d"

    content.min_gap_spin.setValue(3)
    assert content.min_gap_days == 3 and content.min_gap_spin.suffix() == " days"
    assert _found(node)["count"].to_list() == [3, 5]
    assert history.currentText() == "Gaps Smallest Gap Changed"
    history.undo()
    assert content.min_gap_days == 1 and content.min_gap_spin.value() == 1


def test_holidays_commit_after_the_debounce_and_a_bad_one_fails_live(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(
        qtbot, sequence_column="d", mode="date", business_days_only=True
    )
    content = node.content
    history = window.scene.history
    content.holidays_edit.setPlainText("2024-03-06\n\n 2024-03-07 \n")
    assert content.holidays == []  # nothing until the pause
    qtbot.waitUntil(
        lambda: content.holidays == ["2024-03-06", "2024-03-07"], timeout=2000
    )
    assert history.currentText() == "Gaps Holidays Changed"

    content.holidays_edit.setPlainText("soon")
    qtbot.waitUntil(lambda: content.holidays == ["soon"], timeout=2000)
    assert node.isInvalid() and node.current_error.code == "TD-AUDIT-004"
    # Typing in one burst is one step, so undo returns to where the burst began.
    assert history.controller.count == 1
    history.undo()
    assert content.holidays == [] and not node.isInvalid()
    assert content.holidays_edit.toPlainText() == ""


def test_count_button_collects_the_summary_and_leaves_history_alone(qtbot) -> None:
    window, _source, node, dock = _dock(qtbot, sequence_column="je")
    content = node.content
    history = window.scene.history
    button = next(
        b
        for b in dock.dock_widget.findChildren(IconButton)
        if b.accessibleName() == COUNT_TOOLTIP
    )
    assert "Not counted" in content.summary_label.text()
    count = history.controller.count
    button.click()
    assert content.test_summary.exception_rows == 3
    assert content.summary_label.text().startswith("FAIL: 1 gap ranges covering 1")
    assert history.controller.count == count
    content.duplicates_check.setChecked(False)  # an edit makes the count stale
    assert content.test_summary is None


def test_dock_survives_a_forced_rebuild_after_undo(qtbot) -> None:
    window, _source, node, dock = _dock(qtbot, sequence_column="je")
    content = node.content
    content.group_list.checkboxes["led"].setChecked(True)
    window.scene.history.undo()
    dock.updateConfig([node.grNode], force=True)
    assert content.group_columns == [] and content.group_list.checked() == []
    content.mode_control._buttons["Number"].click()
    assert content.mode == "number"


# ---- registration and persistence ------------------------------------------------------
def test_node_is_in_the_audit_palette() -> None:
    registry = NODE_REGISTRIES[NodeTypes.AUDIT]
    assert AuditNodes.GAPS in registry
    assert registry[AuditNodes.GAPS].node_title == "Gaps"
    assert registry[AuditNodes.GAPS].icon == "node_gaps"


def test_save_and_reload_keeps_the_op_id_and_settings(qtbot, tmp_path) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = TriggerNode_Gaps(window.scene)
    content = node.content
    content.sequence_column = "je"
    content.mode = "number"
    content.group_columns = ["led", "d"]
    content.report_duplicates = False
    content.range_start = 4
    content.range_end = 99
    content.min_gap_days = 5
    content.business_days_only = True
    content.holidays = ["2024-03-29"]
    expected = content.params()
    path = tmp_path / "gaps.tds"
    window.scene.saveToFile(str(path))

    saved = json.loads(path.read_text(encoding="utf-8"))
    ops = [n.get("op") for n in saved["nodes"]]
    assert ops == ["audit.gaps"]

    reloaded = TriggerSubWindow()
    qtbot.addWidget(reloaded)
    assert reloaded.fileLoad(str(path)) is True
    (loaded,) = reloaded.getAllNodes()
    assert isinstance(loaded, TriggerNode_Gaps)
    assert loaded.content.params() == expected
    assert GapsParams.from_dict(loaded.content.params_dict()) == expected
    assert loaded.content.output_variable_names() == [
        f"var_gaps_{loaded.content.id}",
        f"var_gapsum_{loaded.content.id}",
    ]
