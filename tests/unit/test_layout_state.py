"""LayoutState: window geometry, dock state, session list, reset."""

from __future__ import annotations

from pathlib import Path

from qtpy.QtWidgets import QApplication, QLabel, QMainWindow, QMdiArea, QTextEdit

from trigger_designer.qt.docking import (
    PANEL_CONFIG,
    PANEL_HISTORY,
    PANEL_LOGS,
    PANEL_PREVIEW,
    Panel,
)
from trigger_designer.qt.docking.ads_host import AdsDockHost
from trigger_designer.qt.layout_state import (
    STATE_VERSION,
    STATE_VERSION_KEY,
    WINDOW_STATE_KEY,
    LayoutState,
    apply_default_layout,
)


def _flush() -> None:
    app = QApplication.instance()
    for _ in range(3):
        app.processEvents()


def _panels() -> list[Panel]:
    return [
        Panel(PANEL_CONFIG, "Node Configuration", QLabel("config")),
        Panel(PANEL_LOGS, "Logs", QTextEdit("logs")),
        Panel(PANEL_PREVIEW, "Data Preview", QTextEdit("preview")),
        Panel(PANEL_HISTORY, "Run History", QTextEdit("history")),
    ]


def _window() -> QMainWindow:
    window = QMainWindow()
    host = AdsDockHost(window)
    host.set_central(QMdiArea())
    for panel in _panels():
        host.register(panel)
    window.setCentralWidget(host.widget())
    window.dockHost = host
    window.resize(1000, 700)
    return window


def test_geometry_round_trip(clean_preferences) -> None:
    state = LayoutState(clean_preferences)
    first = _window()
    # Stay inside the offscreen screen (800x600): the platform clamps a window
    # wider than the screen, which would break the exact comparison.
    first.resize(640, 480)
    first.show()
    _flush()
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
    first.resize(640, 480)
    first.show()
    _flush()
    state.save(first)

    clean_preferences.set("layout/restore", False)
    second = _window()
    second.resize(650, 500)
    state.restore(second)
    # Geometry is not applied ...
    assert second.size().width() == 650
    assert second.size().height() == 500
    # ... and the default arrangement is.
    host = second.dockHost
    assert host.is_visible(PANEL_CONFIG)
    assert host.is_visible(PANEL_LOGS)
    assert host.area_widget(PANEL_PREVIEW) is host.area_widget(PANEL_LOGS)


def test_dock_state_round_trip(clean_preferences) -> None:
    state = LayoutState(clean_preferences)
    first = _window()
    first.resize(640, 480)
    first.show()
    apply_default_layout(first)
    _flush()
    # Hide one dock: restore must reproduce it.
    first.dockHost.hide_panel(PANEL_LOGS)
    _flush()
    state.save(first)

    second = _window()
    state.restore(second)
    _flush()
    assert not second.dockHost.is_visible(PANEL_LOGS)
    assert second.dockHost.is_visible(PANEL_CONFIG)


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
    window = _window()
    window.show()
    _flush()

    apply_default_layout(window)
    _flush()

    host = window.dockHost
    config_area = host.area_widget(PANEL_CONFIG)
    logs_area = host.area_widget(PANEL_LOGS)
    assert config_area is not None and logs_area is not None
    # Config is a full-height column; Logs sits under the canvas only.
    assert config_area.height() > logs_area.height()
    assert host.area_widget(PANEL_PREVIEW) is logs_area
    assert host.area_widget(PANEL_HISTORY) is logs_area


def test_version_2_dock_state_is_ignored(clean_preferences) -> None:
    state = LayoutState(clean_preferences)
    first = _window()
    first.resize(640, 480)
    first.show()
    apply_default_layout(first)
    _flush()
    # Save an arrangement that differs from the default (Logs hidden), then
    # stamp it with the old version: restore must not apply it.
    first.dockHost.hide_panel(PANEL_LOGS)
    _flush()
    state.save(first)
    clean_preferences.set(STATE_VERSION_KEY, 2)

    second = _window()
    state.restore(second)
    _flush()
    host = second.dockHost
    assert host.is_visible(PANEL_LOGS)
    assert host.area_widget(PANEL_PREVIEW) is host.area_widget(PANEL_LOGS)


def test_corrupt_blob_with_current_version_applies_default(clean_preferences) -> None:
    clean_preferences.set(WINDOW_STATE_KEY, b"junk")
    clean_preferences.set(STATE_VERSION_KEY, STATE_VERSION)
    window = _window()

    LayoutState(clean_preferences).restore(window)
    _flush()

    host = window.dockHost
    assert host.is_visible(PANEL_LOGS)
    assert host.area_widget(PANEL_PREVIEW) is host.area_widget(PANEL_LOGS)


def test_no_saved_state_applies_default(clean_preferences) -> None:
    window = _window()

    LayoutState(clean_preferences).restore(window)
    _flush()

    host = window.dockHost
    assert host.is_visible(PANEL_CONFIG)
    assert host.is_visible(PANEL_LOGS)
    assert host.area_widget(PANEL_PREVIEW) is host.area_widget(PANEL_LOGS)


def test_bare_window_without_dock_host_does_not_raise(clean_preferences) -> None:
    state = LayoutState(clean_preferences)
    window = QMainWindow()
    state.restore(window)
    state.save(window)
    apply_default_layout(window)
    assert window.width() >= 640


def test_corrupt_state_version_does_not_stop_the_window_opening(
    clean_preferences,
) -> None:
    clean_preferences.settings.setValue(STATE_VERSION_KEY, "not-a-number")
    window = QMainWindow()
    LayoutState(clean_preferences).restore(window)
    assert window.width() >= 640
