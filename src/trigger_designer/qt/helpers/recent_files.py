"""Recent project tracking backed by QSettings.

Single owner for the ``recentFiles`` list and the ``show_welcome_dialog``
flag. Both the File > Open Recent menu and the startup welcome dialog
read from this manager so they can never drift apart.

QSettings scope is ``Blue Octa / Trigger Designer`` to match the settings
dialog (``qt/models/settings_panel.py``). ``main.py`` uses a different
scope for theme only; recents intentionally stay on the Blue Octa scope.
"""

from __future__ import annotations

import os

from qtpy.QtCore import QSettings

ORG_NAME = "Blue Octa"
APP_NAME = "Trigger Designer"
RECENTS_KEY = "recentFiles"
WELCOME_KEY = "show_welcome_dialog"
DEFAULT_MAX_ITEMS = 10


class RecentFilesManager:
    """Load, store and prune the recent-project list."""

    def __init__(
        self,
        settings: QSettings | None = None,
        max_items: int = DEFAULT_MAX_ITEMS,
    ) -> None:
        self._settings = settings or QSettings(ORG_NAME, APP_NAME)
        self._max_items = max(1, max_items)

    @property
    def max_items(self) -> int:
        return self._max_items

    def recents(self) -> list[str]:
        """Return stored paths, newest first, deduplicated."""
        seen: set[str] = set()
        cleaned: list[str] = []
        for entry in self._read_raw():
            path = str(entry).strip()
            if not path or path in seen:
                continue
            seen.add(path)
            cleaned.append(path)
        return cleaned[: self._max_items]

    def add_recent(self, path: str | os.PathLike[str] | None) -> list[str]:
        """Move *path* to the front, cap the list, persist, return it."""
        if path is None:
            return self.recents()
        normalized = os.path.abspath(os.path.normpath(os.fspath(path))).strip()
        if not normalized:
            return self.recents()
        existing = self.recents()
        norm_key = os.path.normcase(normalized)
        existing = [p for p in existing if os.path.normcase(p) != norm_key]
        updated = [normalized, *existing][: self._max_items]
        self._settings.setValue(RECENTS_KEY, updated)
        self._settings.sync()
        return updated

    def remove_recent(self, path: str | os.PathLike[str]) -> list[str]:
        """Drop *path* from the list (used for missing files)."""
        target = os.path.normcase(os.path.abspath(os.path.normpath(os.fspath(path))))
        updated = [p for p in self.recents() if os.path.normcase(p) != target]
        self._settings.setValue(RECENTS_KEY, updated)
        self._settings.sync()
        return updated

    def clear(self) -> None:
        self._settings.setValue(RECENTS_KEY, [])
        self._settings.sync()

    def is_welcome_enabled(self) -> bool:
        value = self._settings.value(WELCOME_KEY, True)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "off"}
        if isinstance(value, (int, float)):
            return bool(value)
        return True if value is None else bool(value)

    def set_welcome_enabled(self, enabled: bool) -> None:
        self._settings.setValue(WELCOME_KEY, bool(enabled))
        self._settings.sync()

    def _read_raw(self) -> list[str]:
        raw = self._settings.value(RECENTS_KEY, [])
        if raw is None:
            return []
        if isinstance(raw, str):
            return [raw] if raw.strip() else []
        try:
            return [str(item) for item in list(raw)]
        except TypeError:
            return [str(raw)] if str(raw).strip() else []
