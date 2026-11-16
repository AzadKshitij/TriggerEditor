#!/usr/bin/env python3
"""Bottom panels are plain QWidgets: the QtAds host wraps them in docks.

Each panel keeps its title through ``setWindowTitle`` (the host listens to
``windowTitleChanged``) and its main child stays reachable under the panel.
"""

from qtpy.QtWidgets import QApplication, QDockWidget, QWidget

from trigger_designer.qt.docks.data_preview import DataPreviewDock
from trigger_designer.qt.docks.logging_dock import LoggingDock
from trigger_designer.qt.docks.run_history_dock import RunHistoryDock

_APP = QApplication.instance() or QApplication([])


def _is_under(widget: QWidget, ancestor: QWidget) -> bool:
    node = widget.parentWidget()
    while node is not None:
        if node is ancestor:
            return True
        node = node.parentWidget()
    return False


def _assert_plain_widget(panel: QWidget, title: str) -> None:
    assert not isinstance(panel, QDockWidget)
    assert isinstance(panel, QWidget)
    assert panel.windowTitle() == title


def _assert_title_signal(panel: QWidget) -> None:
    seen: list[str] = []
    panel.windowTitleChanged.connect(seen.append)
    panel.setWindowTitle("Renamed")
    assert seen == ["Renamed"]
    panel.setWindowTitle("Renamed")  # no change, no signal
    assert seen == ["Renamed"]


def test_logging_dock_is_plain_widget() -> None:
    dock = LoggingDock()
    _assert_plain_widget(dock, "Logs")
    _assert_title_signal(dock)
    assert _is_under(dock.tree, dock)


def test_run_history_dock_is_plain_widget() -> None:
    dock = RunHistoryDock()
    _assert_plain_widget(dock, "Run History")
    _assert_title_signal(dock)
    assert _is_under(dock.run_table, dock)


def test_data_preview_dock_is_plain_widget() -> None:
    dock = DataPreviewDock()
    _assert_plain_widget(dock, "Data Preview")
    _assert_title_signal(dock)
    assert _is_under(dock.panel, dock)
