"""Problems dock rows, filter, copy and technical toggle."""

from __future__ import annotations

from trigger_designer.core.errors import ErrorContext, make_error
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.problems_dock import ProblemsDock


def _window_with_errors(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.problems.upsert(
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
        "run",
    )
    window.problems.upsert(
        make_error(
            "TD-SCH-001",
            ErrorContext(node_id=2, node_label="Select 'Prep'"),
            column="Amnt",
            available="Amount",
            suggestion="Amount",
        ),
        "live",
    )
    dock = ProblemsDock()
    qtbot.addWidget(dock)
    dock.switch_to_design_window(window)
    return window, dock


def test_rows_and_title(qtbot) -> None:
    _window, dock = _window_with_errors(qtbot)
    assert dock.tree.topLevelItemCount() == 2
    assert dock.windowTitle() == "Problems (2)"
    assert dock.tree.topLevelItem(0).text(1) == "TD-TYP-001"


def test_search_filters_rows(qtbot) -> None:
    _window, dock = _window_with_errors(qtbot)
    dock.search.setText("Amnt")
    qtbot.wait(350)
    assert dock.tree.topLevelItemCount() == 1
    assert "Amnt" in dock.tree.topLevelItem(0).text(2)


def test_copy_details_contains_code_and_hint(qtbot) -> None:
    _window, dock = _window_with_errors(qtbot)
    dock.tree.setCurrentItem(dock.tree.topLevelItem(0))
    dock.tree.topLevelItem(0).setSelected(True)
    dock._copy_details()
    from qtpy.QtGui import QGuiApplication

    clipboard = QGuiApplication.clipboard().text()
    assert "TD-TYP-001" in clipboard
    assert "Fix:" in clipboard


def test_technical_toggle_persists_and_adds_detail(qtbot, clean_preferences) -> None:
    _window, dock = _window_with_errors(qtbot)
    assert dock.technical_button.isChecked() is False
    dock.technical_button.setChecked(True)
    assert clean_preferences.get("errors/show_technical", False) is True
    top = dock.tree.topLevelItem(0)
    assert top.childCount() >= 1


def test_empty_state(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    dock = ProblemsDock()
    qtbot.addWidget(dock)
    dock.switch_to_design_window(window)
    assert dock.tree.topLevelItemCount() == 0
    assert dock.empty.isHidden() is False
