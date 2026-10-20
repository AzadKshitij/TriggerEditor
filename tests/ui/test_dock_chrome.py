#!/usr/bin/env python3
"""Tab-only dock chrome: the tab bar is the only header a tabbed dock wears.

A dock that shares a tab group hides its own title bar (name, float and close
buttons) while it is a tab; a floating dock, or a docked dock with no tab bar
beside it, keeps the title bar it is moved and closed by. The main window sets
``GroupedDragging`` so dragging a tab out of the bar pops that panel out.
"""

import os
import sys
from collections.abc import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QDockWidget, QMainWindow, QWidget

from trigger_designer.qt.helpers.dock_chrome import (
    TITLE_BAR_NAME,
    install_tab_only_chrome,
)
from trigger_designer.qt.main_window import TriggerWindow

_APP = QApplication.instance() or QApplication([])

_BUTTONS = ("qt_dockwidget_floatbutton", "qt_dockwidget_closebutton")


def _flush() -> None:
    """Run the pending zero-timer that re-reads a dock's tab state."""
    for _ in range(3):
        _APP.processEvents()


@pytest.fixture
def window() -> Iterator[TriggerWindow]:
    win = TriggerWindow()
    win.show()
    _flush()
    yield win
    win.hide()
    win.deleteLater()


def _tabbed_docks(window: TriggerWindow) -> list[QDockWidget]:
    return [window.loggingDock, window.dataPreviewDock]


def _buttons(dock: QDockWidget) -> list[QWidget]:
    return [
        child for child in dock.findChildren(QWidget) if child.objectName() in _BUTTONS
    ]


def test_window_lets_a_tab_be_dragged_out(window: TriggerWindow) -> None:
    assert window.dockOptions() & QMainWindow.DockOption.GroupedDragging


def test_tabbed_pair_hides_its_title_bars(window: TriggerWindow) -> None:
    for dock in _tabbed_docks(window):
        assert dock.titleBarWidget() is not None
        assert dock.titleBarWidget().objectName() == TITLE_BAR_NAME
        # No title row: the panel content starts at the very top of the dock.
        assert dock.widget().geometry().y() == 0
        assert not any(button.isVisible() for button in _buttons(dock))


def test_floating_dock_gets_its_title_bar_back(window: TriggerWindow) -> None:
    dock = window.loggingDock
    dock.setFloating(True)
    _flush()

    assert dock.isFloating()
    assert dock.titleBarWidget() is None
    # Qt hands a floating dock with the default bar to the window manager, so
    # the popped-out panel keeps a frame to be moved, resized and closed by.
    assert not dock.windowFlags() & Qt.WindowType.FramelessWindowHint


def test_a_permanent_placeholder_would_leave_the_panel_frameless(
    window: TriggerWindow,
) -> None:
    dock = window.loggingDock
    dock.setFloating(True)
    _flush()

    dock.setTitleBarWidget(QWidget())  # what an unconditional placeholder does
    _flush()

    assert dock.windowFlags() & Qt.WindowType.FramelessWindowHint


def test_docking_back_hides_the_bar_again(window: TriggerWindow) -> None:
    dock = window.loggingDock
    dock.setFloating(True)
    _flush()
    dock.setFloating(False)
    _flush()

    assert not dock.isFloating()
    assert dock.titleBarWidget() is not None
    assert window.tabifiedDockWidgets(dock)


def test_the_placeholder_is_reused(window: TriggerWindow) -> None:
    dock = window.loggingDock
    first = dock.titleBarWidget()
    dock.setFloating(True)
    _flush()
    dock.setFloating(False)
    _flush()

    assert dock.titleBarWidget() is first
    assert len(dock.findChildren(QWidget, TITLE_BAR_NAME)) == 1


def test_docked_dock_without_tabs_keeps_its_title_bar() -> None:
    window = QMainWindow()
    dock = QDockWidget("Solo", window)
    dock.setWidget(QWidget())
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    install_tab_only_chrome(dock)

    # No tab bar beside it: the default bar stays, it is the drag handle.
    assert dock.titleBarWidget() is None
    window.deleteLater()
