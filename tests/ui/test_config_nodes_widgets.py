#!/usr/bin/env python3
"""ConfigDock and NodesDock are plain widgets, not QDockWidgets.

The QtAds host wraps each panel in its own dock, so these panels must stand
alone: they are QWidgets, they keep their window title (the host listens to
``windowTitleChanged`` to rename the tab), and they lay their content out
with zero margins.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy.QtWidgets import (
    QApplication,
    QDockWidget,
    QSizePolicy,
    QTabWidget,
    QWidget,
)

from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.docks.nodes_list import NodesDock

_APP = QApplication.instance() or QApplication([])


def test_config_dock_is_plain_widget() -> None:
    dock = ConfigDock()
    assert not isinstance(dock, QDockWidget)
    assert isinstance(dock, QWidget)


def test_config_dock_default_title() -> None:
    assert ConfigDock().windowTitle() == "Node Configuration"


def test_config_dock_update_config_empty_keeps_base_title() -> None:
    dock = ConfigDock()
    dock.updateConfig([])
    assert dock.windowTitle() == ConfigDock.BASE_TITLE


def test_config_dock_window_title_change_emits_signal() -> None:
    dock = ConfigDock()
    seen: list[str] = []
    dock.windowTitleChanged.connect(seen.append)
    dock.setWindowTitle("Node Configuration (Filter)")
    assert seen == ["Node Configuration (Filter)"]


def test_config_dock_widget_is_parented_to_dock() -> None:
    dock = ConfigDock()
    assert dock.dock_widget.parentWidget() is dock


def test_nodes_dock_is_plain_widget() -> None:
    dock = NodesDock()
    assert not isinstance(dock, QDockWidget)
    assert isinstance(dock, QWidget)


def test_nodes_dock_has_tab_widget_and_fixed_vertical_policy() -> None:
    dock = NodesDock()
    assert dock.findChild(QTabWidget) is not None
    assert dock.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
