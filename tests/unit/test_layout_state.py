"""LayoutState: window geometry, dock state, session list, reset."""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDockWidget, QMainWindow

from trigger_designer.qt.layout_state import LayoutState, apply_default_layout


def _window() -> QMainWindow:
    window = QMainWindow()
    for name, area in (
        ("NodesDock", Qt.DockWidgetArea.TopDockWidgetArea),
        ("ConfigDock", Qt.DockWidgetArea.LeftDockWidgetArea),
        ("LoggingDock", Qt.DockWidgetArea.BottomDockWidgetArea),
    ):
        dock = QDockWidget(name, window)
        dock.setObjectName(name)
        window.addDockWidget(area, dock)
    return window


def test_geometry_round_trip(clean_preferences) -> None:
    state = LayoutState(clean_preferences)
    first = _window()
    # Stay inside the offscreen screen (800x600): the platform clamps a
    # window wider than the screen, which would break the exact comparison.
    first.resize(640, 480)
    first.show()
    state.save(first)

    second = _window()
    state.restore(second)
    assert second.size() == first.size()


def test_first_run_uses_a_usable_default(clean_preferences) -> None:
    state = LayoutState(clean_preferences)
    window = QMainWindow()
    state.restore(window)
    assert window.width() >= 640
    assert window.height() >= 480


def test_restore_can_be_disabled(clean_preferences) -> None:
    state = LayoutState(clean_preferences)
    first = _window()
    first.resize(1024, 700)
    first.show()
    state.save(first)

    clean_preferences.set("layout/restore", False)
    second = _window()
    second.resize(650, 500)
    state.restore(second)
    assert second.size().width() == 650
    assert second.size().height() == 500


def test_dock_state_round_trip(clean_preferences) -> None:
    state = LayoutState(clean_preferences)
    first = _window()
    first.resize(900, 640)
    first.show()
    # Close one dock and float another: restore must reproduce both.
    first.findChild(QDockWidget, "LoggingDock").hide()
    state.save(first)

    second = _window()
    state.restore(second)
    assert not second.findChild(QDockWidget, "LoggingDock").isVisible()


def test_session_round_trip(clean_preferences, tmp_path: Path) -> None:
    state = LayoutState(clean_preferences)
    files = []
    for name in ("a.td", "b.td"):
        path = tmp_path / name
        path.write_text("{}", encoding="utf-8")
        files.append(str(path))

    clean_preferences.set("layout/session", True)
    window = _window()
    state.save_session(window, files)
    restored, active = state.session_to_restore()
    assert restored == files
    assert active is None


def test_session_disabled_returns_nothing(clean_preferences, tmp_path: Path) -> None:
    state = LayoutState(clean_preferences)
    path = tmp_path / "a.td"
    path.write_text("{}", encoding="utf-8")

    clean_preferences.set("layout/session", False)
    state.save_session(_window(), [str(path)])
    assert state.session_to_restore() == ([], None)


def test_session_filters_vanished_files(clean_preferences, tmp_path: Path) -> None:
    state = LayoutState(clean_preferences)
    path = tmp_path / "a.td"
    path.write_text("{}", encoding="utf-8")
    missing = str(tmp_path / "gone.td")

    clean_preferences.set("layout/session", True)
    state.save_session(_window(), [str(path), missing])
    restored, _active = state.session_to_restore()
    assert restored == [str(path)]


def test_clear_removes_layout_keys_only(clean_preferences) -> None:
    state = LayoutState(clean_preferences)
    window = _window()
    window.show()
    state.save(window)
    clean_preferences.set("editor/grid_size", 25)

    state.clear()
    assert clean_preferences.settings.value("layout/geometry") is None
    assert clean_preferences.settings.value("layout/window_state") is None
    assert clean_preferences.get("editor/grid_size") == 25


def test_apply_default_layout_arranges_docks() -> None:
    window = QMainWindow()
    window.nodesDock = QDockWidget("Nodes", window)
    window.configDock = QDockWidget("Config", window)
    window.loggingDock = QDockWidget("Logs", window)
    window.dataPreviewDock = QDockWidget("Preview", window)
    for dock in (
        window.nodesDock,
        window.configDock,
        window.loggingDock,
        window.dataPreviewDock,
    ):
        window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    apply_default_layout(window)

    assert (
        window.dockWidgetArea(window.nodesDock) == Qt.DockWidgetArea.TopDockWidgetArea
    )
    assert (
        window.dockWidgetArea(window.configDock) == Qt.DockWidgetArea.LeftDockWidgetArea
    )
    assert (
        window.dockWidgetArea(window.loggingDock)
        == Qt.DockWidgetArea.BottomDockWidgetArea
    )
    assert window.dataPreviewDock in window.tabifiedDockWidgets(window.loggingDock)
