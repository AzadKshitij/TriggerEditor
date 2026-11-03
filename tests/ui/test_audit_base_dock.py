"""The Audit base's Config Dock controls, with the shared ``ColumnPicker`` in particular.

``ColumnPicker`` (``qt/widgets/common/column_picker.py``) already serves single and
multi column choices, so the audit nodes use it through ``add_picker`` rather than a
new widget. These tests drive the demo node's dock end to end: pick -> model ->
re-evaluation -> one undo step -> projection back onto the control.
"""

from __future__ import annotations

import polars as pl
from qtpy.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from tests.support.audit_demo import DemoNode, demo_graph
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.widgets.common import ColumnPicker, IconButton, TextButton
from trigger_designer.qt.widgets.nodes.Audit._base import COUNT_TOOLTIP

FRAME = pl.DataFrame(
    {
        "amount": ["10", "(5)", "7,000.50", "9000"],
        "key": ["a", "b", "c", "d"],
        "other": ["x", "y", "z", "w"],
    }
).lazy()


def _dock(qtbot, **settings):
    window, source, node = demo_graph(FRAME)
    qtbot.addWidget(window)
    for name, value in settings.items():
        setattr(node.content, name, value)
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    node.scene.history.storeHistory("Baseline")  # the first stamp is not a step
    return window, source, node, dock


def test_dock_builds_and_every_section_owns_its_undo(qtbot) -> None:
    _window, _source, node, dock = _dock(qtbot, column="amount")
    content = node.content
    pickers = dock.dock_widget.findChildren(ColumnPicker)
    assert [p.accessibleName().split(":")[0] for p in pickers] == ["Amount", "Keys"]
    sections = dock.dock_widget.findChildren(type(content.section("x")))
    assert sections and all(s._undo_composite for s in sections)


def test_without_input_the_dock_shows_the_empty_state(qtbot) -> None:
    window, _source, _node, _dock_unused = _dock(qtbot)
    fresh = DemoNode(window.scene)
    holder = QWidget()
    layout = QVBoxLayout(holder)
    fresh.content.create_layout(layout)
    assert layout.count() == 1
    assert layout.itemAt(0).widget().objectName() == "EmptyStateLabel"
    assert fresh.content._bindings == {}


def test_single_picker_commits_evaluates_and_undoes_as_one_step(qtbot) -> None:
    window, _source, node, dock = _dock(qtbot)
    content = node.content
    history = window.scene.history
    assert node.isInvalid() and node.current_error.code == "TD-AUDIT-001"

    picker = content.column_picker
    assert picker.checked() == []
    picker._toggle_name("amount")  # what a click in the popup does
    assert content.column == "amount"
    assert not node.isInvalid()
    assert history.controller.count == 1  # exactly one step (baseline is not one)
    assert history.currentText() == "Amount Column Changed"

    history.undo()
    assert content.column == ""
    assert content.column_picker.checked() == []
    assert node.isInvalid()
    history.redo()
    assert content.column == "amount"
    assert content.column_picker.checked() == ["amount"]
    assert not node.isInvalid()

    # force=True is what onHistoryRestored does; the same node rebuilds its widgets.
    dock.updateConfig([node.grNode], force=True)
    assert content.column_picker is not picker  # a fresh widget, same model
    assert content.column_picker.checked() == ["amount"]


def test_multi_picker_round_trips_a_list(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, column="amount")
    content = node.content
    content.keys_picker._toggle_name("key")
    content.keys_picker._toggle_name("other")
    assert content.keys == ["key", "other"]
    window.scene.history.undo()
    assert content.keys == ["key"]
    assert content.keys_picker.checked() == ["key"]
    window.scene.history.undo()
    assert content.keys == [] and content.keys_picker.checked() == []


def test_a_saved_column_the_input_lost_stays_visible(qtbot) -> None:
    _window, _source, node, _dock_unused = _dock(qtbot, column="gone")
    picker = node.content.column_picker
    assert node.current_error.code == "TD-AUDIT-002"
    assert picker.checked() == ["gone"]  # shown, so the error is not a mystery
    assert "gone" in picker.column_names()
    picker._toggle_name("amount")
    assert node.content.column == "amount" and not node.isInvalid()


def test_segment_spin_check_and_combo_write_the_model(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, column="amount", threshold=6.0)
    content = node.content
    history = window.scene.history

    content.mode_control._buttons["Below"].click()
    assert content.mode == "below"
    assert node.value[0]["data"].collect().height == 1  # only (5) is below 6
    history.undo()
    assert content.mode == "above" and content.mode_control.value() == "Above"

    content.strict_check.setChecked(True)
    assert content.strict is True
    history.undo()
    assert content.strict is False and not content.strict_check.isChecked()

    content.kind_combo.setCurrentIndex(1)
    assert content.kind == "y"
    history.undo()
    assert content.kind == "x" and content.kind_combo.currentData() == "x"


def test_spin_bursts_merge_into_one_undo_step(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, column="amount")
    content = node.content
    history = window.scene.history
    before = history.controller.count
    for value in (1.0, 2.0, 3.5):
        content.threshold_spin.setValue(value)
    assert content.threshold == 3.5
    assert history.controller.count == before + 1
    history.undo()
    assert content.threshold == 0.0 and content.threshold_spin.value() == 0.0


def test_optional_int_spin_maps_its_minimum_to_none(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, column="amount")
    content = node.content
    assert content.top is None
    assert content.top_spin.value() == content.top_spin.minimum()
    content.top_spin.setValue(5)
    assert content.top == 5
    window.scene.history.undo()
    assert content.top is None
    assert content.top_spin.value() == content.top_spin.minimum()
    window.scene.history.redo()
    assert content.top == 5 and content.top_spin.value() == 5
    content.top_spin.setValue(content.top_spin.minimum())  # back to "All"
    assert content.top is None


def test_typed_lists_commit_after_the_debounce_and_ignore_half_typed(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, column="amount")
    content = node.content
    history = window.scene.history
    before = history.controller.count

    content.levels_edit.setText("1000, 10000")
    assert content.levels == []  # nothing until the pause
    qtbot.waitUntil(lambda: content.levels == [1000.0, 10000.0], timeout=2000)
    assert history.controller.count == before + 1

    content.levels_edit.setText("1000,")  # half typed: the old value stands
    qtbot.wait(450)
    assert content.levels == [1000.0, 10000.0]

    content.sizes_edit.setText("20, all")
    qtbot.waitUntil(lambda: content.sizes == [20, -1], timeout=2000)
    history.undo()
    assert content.sizes == [] and content.sizes_edit.text() == ""
    history.undo()
    assert content.levels == [] and content.levels_edit.text() == ""


def test_leaving_the_dock_commits_a_pending_text_edit(qtbot) -> None:
    window, _source, node, dock = _dock(qtbot, column="amount")
    content = node.content
    content.note_edit.setText("typed just now")
    assert content.note == ""
    dock.updateConfig([])  # the user clicks the canvas inside the debounce
    assert content.note == "typed just now"
    assert window.scene.history.currentText() == "Demo Note Changed"


def test_lines_and_digit_checklist(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, column="amount")
    content = node.content
    editor = content.lines_edit
    assert isinstance(editor, QPlainTextEdit)
    editor.setPlainText("a\n\n b \n")
    qtbot.waitUntil(lambda: content.lines == ["a", "b"], timeout=2000)

    content.digits_list.setChecked(["1", "5"])
    content.digits_list.changed.emit(["1", "5"])
    assert content.digits == [1, 5]
    window.scene.history.undo()
    assert content.digits == [] and content.digits_list.checked() == []


def test_undo_does_not_record_its_own_write_back(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, column="amount")
    content = node.content
    history = window.scene.history
    content.threshold_spin.setValue(8.0)
    count = history.controller.count
    history.undo()
    history.redo()
    assert history.controller.count == count
    assert content.threshold == 8.0


def test_count_button_collects_the_summary_and_leaves_history_alone(qtbot) -> None:
    window, _source, node, dock = _dock(qtbot, column="amount", threshold=6.0)
    content = node.content
    history = window.scene.history
    button = next(
        b
        for b in dock.dock_widget.findChildren(IconButton)
        if b.accessibleName() == COUNT_TOOLTIP
    )
    assert button.toolTip() == COUNT_TOOLTIP
    assert "Not counted" in content.summary_label.text()
    count = history.controller.count
    button.click()
    assert content.test_summary.exception_rows == 3
    assert content.summary_label.text().startswith("FAIL: 3 of 4 rows")
    assert history.controller.count == count

    content.threshold_spin.setValue(1.0)  # an edit makes the old count stale
    assert content.test_summary is None
    assert "Not counted" in content.summary_label.text()


def test_the_dock_uses_icon_buttons_not_text_buttons(qtbot) -> None:
    _window, _source, _node, dock = _dock(qtbot, column="amount")
    assert dock.dock_widget.findChildren(IconButton)
    assert not dock.dock_widget.findChildren(TextButton)


def test_failed_live_evaluation_clears_result_and_summary(qtbot) -> None:
    """The base drops a stale result after a failed evaluation (hook for nodes)."""
    _window, _source, node, _dock_unused = _dock(qtbot, column="amount")
    content = node.content
    assert content.last_result is not None
    seen: list[bool] = []
    content.on_live_failed = lambda: seen.append(True)  # type: ignore[method-assign]
    content.column = "no_such_column"
    node.markDirty(True)
    node.eval()
    assert seen == [True]
    type(content).on_live_failed(content)
    assert content.last_result is None and content.test_summary is None


def test_add_checklist_binds_a_list_setting(qtbot) -> None:
    _window, _source, node, _dock_unused = _dock(qtbot, column="amount")
    content = node.content
    content.keys = ["key"]
    checklist = content.add_checklist("keys", "Keys Changed")
    assert list(checklist.checkboxes) == ["amount", "key", "other"]
    assert checklist.checked() == ["key"]
