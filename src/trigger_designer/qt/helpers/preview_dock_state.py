"""Persisted visibility flag for the shared Data Preview dock.

Kept for migration and for tests: the layout state (``qt/layout_state.py``)
now owns dock visibility inside the ``QMainWindow.saveState`` blob. The
flag still round-trips through the preferences store because old installs
only have this value.
"""

from __future__ import annotations

from qtpy.QtCore import QSettings

from trigger_designer.qt.preferences import get_preferences

VISIBLE_KEY = "data_preview_dock/visible"


class DataPreviewDockState:
    """Read and write ``data_preview_dock/visible``."""

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or get_preferences().settings

    def read(self) -> bool:
        """Whether the dock was open when the app last closed."""
        value = self._settings.value(VISIBLE_KEY, False)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes"}

    def write(self, visible: bool) -> None:
        """Remember whether the dock was open (legacy key)."""
        self._settings.setValue(VISIBLE_KEY, bool(visible))
        self._settings.sync()
