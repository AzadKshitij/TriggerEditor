"""Persisted visibility flag for the shared Data Preview dock.

QSettings scope is ``Blue Octa / Trigger Designer`` to match the settings
dialog and the recent-files manager (``main.py`` uses a different scope for
theme only).
"""

from __future__ import annotations

from qtpy.QtCore import QSettings

ORG_NAME = "Blue Octa"
APP_NAME = "Trigger Designer"
VISIBLE_KEY = "data_preview_dock/visible"


class DataPreviewDockState:
    """Read and write ``data_preview_dock/visible``."""

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings(ORG_NAME, APP_NAME)

    def read(self) -> bool:
        """Whether the dock was open when the app last closed."""
        value = self._settings.value(VISIBLE_KEY, False)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes"}

    def write(self, visible: bool) -> None:
        """Remember whether the dock was open."""
        self._settings.setValue(VISIBLE_KEY, bool(visible))
        self._settings.sync()
