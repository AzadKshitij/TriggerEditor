"""Window, dock and session layout persistence.

One auto-saved layout, no named presets:

* ``layout/geometry`` / ``layout/window_state`` - window geometry and
  ``QMainWindow.saveState`` blob **and the dock objectName map**.
* ``layout/session_files`` / ``layout/session_active`` - the files that were
  open at last close. They are only reopened when ``layout/session`` is on.
* ``layout/restore`` - whether the saved layout is applied at startup.

The old single-purpose ``data_preview_dock/visible`` flag is only consulted
when no dock state exists yet (migration), then never written again.
"""

from __future__ import annotations

import os
from typing import Any

from loguru import logger
from qtpy.QtCore import QPoint, QSize
from qtpy.QtGui import QGuiApplication
from qtpy.QtWidgets import QMainWindow, QWidget

from trigger_designer.qt.preferences import Preferences, get_preferences

STATE_VERSION = 1
DEFAULT_WINDOW_SIZE = QSize(1280, 800)

GEOMETRY_KEY = "layout/geometry"
WINDOW_STATE_KEY = "layout/window_state"
STATE_VERSION_KEY = "layout/state_version"
SESSION_FILES_KEY = "layout/session_files"
SESSION_ACTIVE_KEY = "layout/session_active"


def _to_point(value: Any) -> QPoint | None:
    if isinstance(value, QPoint):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return QPoint(int(value[0]), int(value[1]))
        except TypeError, ValueError:
            return None
    if isinstance(value, str) and "," in value:
        try:
            x, y = value.strip("()").split(",")[:2]
            return QPoint(int(float(x)), int(float(y)))
        except ValueError:
            return None
    return None


def _to_size(value: Any) -> QSize | None:
    if isinstance(value, QSize):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return QSize(int(value[0]), int(value[1]))
        except TypeError, ValueError:
            return None
    if isinstance(value, str) and "," in value:
        try:
            w, h = value.strip("()").split(",")[:2]
            return QSize(int(float(w)), int(float(h)))
        except ValueError:
            return None
    return None


class LayoutState:
    """Read and write the persisted layout for one main window."""

    def __init__(self, preferences: Preferences | None = None) -> None:
        self._prefs = preferences or get_preferences()

    @property
    def preferences(self) -> Preferences:
        return self._prefs

    # -- window geometry --------------------------------------------------
    def _default_size(self) -> QSize:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return QSize(DEFAULT_WINDOW_SIZE)
        available = screen.availableGeometry()
        width = min(DEFAULT_WINDOW_SIZE.width(), int(available.width() * 0.9))
        height = min(DEFAULT_WINDOW_SIZE.height(), int(available.height() * 0.85))
        return QSize(max(640, width), max(480, height))

    def _center_default(self, window: QMainWindow) -> None:
        size = self._default_size()
        window.resize(size)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            center = screen.availableGeometry().center()
            window.move(
                center.x() - size.width() // 2,
                center.y() - size.height() // 2,
            )

    def _on_screen(self, window: QMainWindow) -> bool:
        rect = window.frameGeometry()
        if rect.width() <= 0 or rect.height() <= 0:
            return False
        screen = QGuiApplication.screenAt(rect.center())
        return screen is not None

    def restore(self, window: QMainWindow) -> None:
        """Apply the saved layout, or a sane default on first launch."""
        restore_enabled = bool(self._prefs.get("layout/restore", True))
        settings = self._prefs.settings

        geometry = settings.value(GEOMETRY_KEY, None)
        state = settings.value(WINDOW_STATE_KEY, None)
        version = int(settings.value(STATE_VERSION_KEY, 0) or 0)

        geometry_restored = False
        if restore_enabled and geometry is not None:
            try:
                geometry_restored = bool(window.restoreGeometry(geometry))
            except TypeError:
                geometry_restored = False
            if geometry_restored and not self._on_screen(window):
                logger.debug("Saved window position was off-screen; re-centering")
                geometry_restored = False

        if not geometry_restored:
            self._restore_legacy_geometry(window)
            if not self._on_screen(window):
                self._center_default(window)

        state_restored = False
        if restore_enabled and state is not None and version == STATE_VERSION:
            try:
                state_restored = bool(window.restoreState(state, STATE_VERSION))
            except TypeError:
                state_restored = False

        if not state_restored:
            self._restore_preview_fallback(window)

    def _restore_legacy_geometry(self, window: QMainWindow) -> None:
        if not bool(self._prefs.get("layout/restore", True)):
            return
        pos = _to_point(self._prefs.get("layout/legacy_pos", None))
        size = _to_size(self._prefs.get("layout/legacy_size", None))
        if size is not None:
            window.resize(size)
        if pos is not None:
            window.move(pos)

    def _restore_preview_fallback(self, window: QMainWindow) -> None:
        """First run after upgrade: honour the old preview visibility flag."""
        dock = getattr(window, "dataPreviewDock", None)
        if dock is None:
            return
        if bool(self._prefs.get("layout/legacy_preview_visible", False)):
            dock.show()
            dock.raise_()

    def save(self, window: QMainWindow) -> None:
        """Persist geometry, dock state and the session file list."""
        try:
            self._prefs.set(GEOMETRY_KEY, window.saveGeometry(), sync=False)
            self._prefs.set(
                WINDOW_STATE_KEY, window.saveState(STATE_VERSION), sync=False
            )
            self._prefs.set(STATE_VERSION_KEY, STATE_VERSION, sync=False)
        except Exception as exc:  # noqa: BLE001 - defensive
            logger.warning(f"Unable to save window layout: {exc}")
        self._prefs.sync()

    # -- session ----------------------------------------------------------
    def save_session(self, window: QMainWindow, files: list[str] | None = None) -> None:
        if files is None:
            files = self.open_files(window)
        active = self.active_file(window)
        self._prefs.set(SESSION_FILES_KEY, [str(path) for path in files], sync=False)
        self._prefs.set(SESSION_ACTIVE_KEY, active or "", sync=True)

    def open_files(self, window: QMainWindow) -> list[str]:
        files: list[str] = []
        mdi = getattr(window, "mdiArea", None)
        if mdi is None:
            return files
        for sub in mdi.subWindowList():
            filename = getattr(sub.widget(), "filename", None)
            if filename:
                files.append(str(filename))
        return files

    def active_file(self, window: QMainWindow) -> str | None:
        mdi = getattr(window, "mdiArea", None)
        if mdi is None:
            return None
        sub = mdi.activeSubWindow()
        if sub is None:
            return None
        filename = getattr(sub.widget(), "filename", None)
        return str(filename) if filename else None

    def session_to_restore(self) -> tuple[list[str], str | None]:
        """Files to reopen (only when enabled and still on disk)."""
        if not bool(self._prefs.get("layout/session", False)):
            return [], None
        raw = self._prefs.get(SESSION_FILES_KEY, [])
        files = [str(path) for path in raw if path]
        existing = [path for path in files if os.path.isfile(path)]
        active = self._prefs.get(SESSION_ACTIVE_KEY, "") or None
        if active not in existing:
            active = None
        return existing, active

    # -- reset ------------------------------------------------------------
    def clear(self) -> None:
        """Forget the saved layout (used by Reset Layout)."""
        self._prefs.reset("layout")


def apply_default_layout(window: QMainWindow) -> None:
    """Restore the built-in dock arrangement (Nodes top, Config left, Logs+Preview bottom)."""
    from qtpy.QtCore import Qt

    default_areas = (
        ("nodesDock", Qt.DockWidgetArea.TopDockWidgetArea),
        ("configDock", Qt.DockWidgetArea.LeftDockWidgetArea),
        ("loggingDock", Qt.DockWidgetArea.BottomDockWidgetArea),
        ("dataPreviewDock", Qt.DockWidgetArea.BottomDockWidgetArea),
        ("problemsDock", Qt.DockWidgetArea.BottomDockWidgetArea),
        ("runHistoryDock", Qt.DockWidgetArea.BottomDockWidgetArea),
    )
    logging: QWidget | None = None
    preview: QWidget | None = None
    problems: QWidget | None = None
    history: QWidget | None = None
    for attribute, area in default_areas:
        dock = getattr(window, attribute, None)
        if dock is None:
            continue
        dock.setFloating(False)
        dock.show()
        window.addDockWidget(area, dock)
        if attribute == "loggingDock":
            logging = dock
        elif attribute == "dataPreviewDock":
            preview = dock
        elif attribute == "problemsDock":
            problems = dock
        elif attribute == "runHistoryDock":
            history = dock
    if logging is not None and preview is not None:
        window.tabifyDockWidget(logging, preview)
    if logging is not None and problems is not None:
        window.tabifyDockWidget(logging, problems)
    if logging is not None and history is not None:
        window.tabifyDockWidget(logging, history)
    if logging is not None:
        logging.raise_()
