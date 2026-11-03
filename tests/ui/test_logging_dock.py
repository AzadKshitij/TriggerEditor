"""Logs dock: one list for log lines and node problems."""

from __future__ import annotations

from qtpy.QtCore import QItemSelectionModel
from qtpy.QtGui import QGuiApplication
from qtpy.QtWidgets import QStyleOptionViewItem

from trigger_designer.core.errors import ErrorContext, make_error
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.logging_dock import LoggingDock
from trigger_designer.qt.helpers.diagnostic_feed import (
    CATEGORY_ERRORS,
    CATEGORY_MESSAGES,
    KIND_PROBLEM,
)


def _window_with_errors(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.diagnostics.upsert(
        make_error(
            "TD-TYP-001",
            ErrorContext(node_id=1, node_label="Aggregate 'Totals'"),
            column="Amount",
            target="i64",
            target_human="whole numbers",
            value="1,2O0.50",
            row=4210,
            reason="bad value",
        ),
        "live",
    )
    window.diagnostics.upsert(
        make_error(
            "TD-SCH-001",
            ErrorContext(node_id=2, node_label="Select 'Prep'"),
            column="Amnt",
            available="Amount",
            suggestion="Amount",
        ),
        "live",
    )
    dock = LoggingDock()
    qtbot.addWidget(dock)
    dock.switch_to_design_window(window)
    return window, dock


def test_rows_and_no_title_count(qtbot) -> None:
    _window, dock = _window_with_errors(qtbot)
    assert dock.model.rowCount() == 2
    assert dock.windowTitle() == "Logs"
    first = dock.model.record_at(0)
    assert first is not None and first.kind == KIND_PROBLEM
    assert first.error is not None and first.error.code == "TD-TYP-001"


def test_search_filters_rows(qtbot) -> None:
    _window, dock = _window_with_errors(qtbot)
    dock.search.setText("Amnt")
    qtbot.wait(350)
    assert dock.model.rowCount() == 1
    record = dock.model.record_at(0)
    assert record is not None and record.error is not None
    assert "Amnt" in record.searchable


def test_copy_details_contains_code_and_hint(qtbot) -> None:
    _window, dock = _window_with_errors(qtbot)
    dock.tree.setCurrentIndex(dock.model.index(0, 0))
    dock.tree.selectionModel().select(
        dock.model.index(0, 0),
        QItemSelectionModel.SelectionFlag.ClearAndSelect
        | QItemSelectionModel.SelectionFlag.Rows,
    )
    dock._copy_details()
    clipboard = QGuiApplication.clipboard().text()
    assert "TD-TYP-001" in clipboard
    assert "Fix:" in clipboard


def test_technical_toggle_persists_and_expands_rows(qtbot, clean_preferences) -> None:
    _window, dock = _window_with_errors(qtbot)
    assert dock.technical_button.isChecked() is False
    dock.technical_button.setChecked(True)
    assert clean_preferences.get("errors/show_technical", False) is True
    assert dock.delegate._technical is True

    record = dock.model.record_at(0)
    assert record is not None
    dock.model.set_expanded(record.seq, True)
    option = QStyleOptionViewItem()
    height = dock.delegate.sizeHint(option, dock.model.index(0, 0)).height()
    assert height > 22


def test_empty_state(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    dock = LoggingDock()
    qtbot.addWidget(dock)
    dock.switch_to_design_window(window)
    assert dock.model.rowCount() == 0
    assert dock.empty.isHidden() is False


def test_log_lines_and_problems_share_the_list(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.diagnostics.add_log("INFO", "Design window created")
    dock = LoggingDock()
    qtbot.addWidget(dock)
    dock.switch_to_design_window(window)
    assert dock.model.rowCount() == 1

    dock.set_category(CATEGORY_MESSAGES)
    assert dock.model.rowCount() == 1
    dock.set_category(CATEGORY_ERRORS)
    assert dock.model.rowCount() == 0
    assert dock._chips[CATEGORY_MESSAGES].text() == "1 Messages"


def test_last_run_hides_live_problems(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.diagnostics.upsert(
        make_error("TD-SYS-001", ErrorContext(node_id=1, node_label="Filter")), "run"
    )
    window.diagnostics.upsert(
        make_error("TD-SYS-001", ErrorContext(node_id=2, node_label="Join")), "live"
    )
    dock = LoggingDock()
    qtbot.addWidget(dock)
    dock.switch_to_design_window(window)

    assert dock.model.rowCount() == 1  # Configuration: the live problem only
    dock.set_mode("Last Run")
    assert dock.model.rowCount() == 1
    record = dock.model.record_at(0)
    assert record is not None and record.source == "run"


def test_clear_keeps_live_problems(qtbot) -> None:
    _window, dock = _window_with_errors(qtbot)
    dock.clear_logs()
    assert dock.model.rowCount() == 2
