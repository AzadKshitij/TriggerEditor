"""Window, dock and session layout persistence.

One auto-saved layout, no named presets:

* ``layout/geometry`` - window geometry.
* ``layout/window_state`` / ``layout/state_version`` - the ``window.dockHost``
  arrangement and its format version (``STATE_VERSION``). Blobs of other
  versions, such as the old QMainWindow state, are ignored.
* ``layout/session_files`` / ``layout/session_active`` - the files that were
  open at last close. They are only reopened when ``layout/session`` is on.
* ``layout/restore`` - whether the saved layout is applied at startup.

After ``restore`` a window with a dock host is always arranged: the saved
state when it is usable, otherwise the default layout.
"""

from __future__ import annotations

import os
from typing import Any

from loguru import logger
from qtpy.QtCore import QPoint, QSize
from qtpy.QtGui import QGuiApplication
from qtpy.QtWidgets import QMainWindow

from trigger_designer.qt.docking.layouts import DEFAULT_LAYOUT, LayoutSpec
from trigger_designer.qt.preferences import Preferences, get_preferences

# 3: dock host (QtAds) blobs. Version 2 was QMainWindow.saveState and is ignored.
STATE_VERSION = 3
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
        try:
            version = int(settings.value(STATE_VERSION_KEY, 0) or 0)
        except TypeError, ValueError:
            version = 0

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

        self._restore_dock_state(window, restore_enabled, version)

    def _restore_dock_state(
        self, window: QMainWindow, restore_enabled: bool, version: int
    ) -> None:
        """Arrange the docks: the default first, the saved layout over it.

        QtAds ``restoreState`` into a host whose panels were never placed
        reports success yet places nothing, so the default always goes in
        first. A saved layout that fails to restore then leaves a usable
        window instead of an empty dock area.
        """
        host = getattr(window, "dockHost", None)
        if host is None:
            return
        try:
            apply_default_layout(window)
        except Exception as exc:  # noqa: BLE001 - the window must still open
            logger.warning(f"Unable to apply default dock layout: {exc}")
        blob = self._prefs.settings.value(WINDOW_STATE_KEY, None)
        if restore_enabled and blob is not None and version == STATE_VERSION:
            try:
                if not host.restore_state(bytes(blob)):
                    logger.warning("Saved dock layout was rejected; using the default")
            except Exception as exc:  # noqa: BLE001 - a bad blob must not block startup
                logger.warning(f"Unable to restore dock layout: {exc}")

    def _restore_legacy_geometry(self, window: QMainWindow) -> None:
        if not bool(self._prefs.get("layout/restore", True)):
            return
        pos = _to_point(self._prefs.get("layout/legacy_pos", None))
        size = _to_size(self._prefs.get("layout/legacy_size", None))
        if size is not None:
            window.resize(size)
        if pos is not None:
            window.move(pos)

    def save(self, window: QMainWindow) -> None:
        """Persist geometry, dock state and the session file list."""
        try:
            self._prefs.set(GEOMETRY_KEY, window.saveGeometry(), sync=False)
            host = getattr(window, "dockHost", None)
            if host is not None:
                self._prefs.set(WINDOW_STATE_KEY, host.save_state(), sync=False)
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


def apply_default_layout(window: QMainWindow, spec: LayoutSpec | None = None) -> None:
    """Arrange the docks as ``spec`` (the built-in default when omitted).

    A window without a ``dockHost`` attribute has no dock arrangement to set,
    so this does nothing for it.
    """
    host = getattr(window, "dockHost", None)
    if host is None:
        return
    host.apply_layout(spec if spec is not None else DEFAULT_LAYOUT)
