#!/usr/bin/env python3

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from qtpy.QtCore import QSettings
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.helpers.recent_files import RecentFilesManager

app = QApplication.instance() or QApplication([])


def _manager(max_items=10):
    QSettings("TestRecentOrg", "TestRecentApp").clear()
    settings = QSettings("TestRecentOrg", "TestRecentApp")
    return RecentFilesManager(settings=settings, max_items=max_items)


def test_add_moves_to_front_and_dedupes() -> None:
    manager = _manager()
    manager.add_recent("/tmp/b.tds")
    manager.add_recent("/tmp/a.tds")
    manager.add_recent("/tmp/b.tds")
    assert manager.recents()[0].endswith("b.tds")
    assert len(manager.recents()) == 2


def test_caps_at_max_items() -> None:
    manager = _manager(max_items=3)
    for name in ["a", "b", "c", "d"]:
        manager.add_recent(f"/tmp/{name}.tds")
    recents = manager.recents()
    assert len(recents) == 3
    assert recents[0].endswith("d.tds")
    assert not any(p.endswith("a.tds") for p in recents)


def test_normalizes_to_absolute() -> None:
    manager = _manager()
    added = manager.add_recent("relative.tds")
    assert os.path.isabs(added[0])


def test_remove_and_clear() -> None:
    manager = _manager()
    manager.add_recent("/tmp/a.tds")
    manager.add_recent("/tmp/b.tds")
    manager.remove_recent("/tmp/a.tds")
    assert len(manager.recents()) == 1
    manager.clear()
    assert manager.recents() == []


def test_welcome_flag_defaults_true_and_persists() -> None:
    manager = _manager()
    assert manager.is_welcome_enabled() is True
    manager.set_welcome_enabled(False)
    assert manager.is_welcome_enabled() is False
    manager.set_welcome_enabled(True)
    assert manager.is_welcome_enabled() is True


def test_reads_legacy_single_string() -> None:
    settings = QSettings("TestRecentOrg", "TestRecentApp")
    settings.clear()
    settings.setValue("recentFiles", "/tmp/only.tds")
    manager = RecentFilesManager(settings=settings)
    assert manager.recents() == ["/tmp/only.tds"]
    settings.clear()
