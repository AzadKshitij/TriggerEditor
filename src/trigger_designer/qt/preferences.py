"""Single owner for persisted user preferences.

Everything that survives a restart - theme, accent, layout, editor settings,
node-editor colours - lives in one INI file so there is exactly one scope and
one place to migrate from the legacy registry scopes:

* ``Trigger / Trigger Designer`` - the scope ``main.py`` used for the theme
* ``Blue Octa / Trigger Designer`` - the scope the old Settings dialog wrote
* ``Trigger / NodeEditor`` - the stock ``nodeeditor`` fallback

No module outside this one may construct a ``QSettings`` for user
preferences. ``preferences.settings`` (a ``QSettings`` in INI format) exists
for the few helpers that were originally written against a ``QSettings``
object and are still injected one in tests.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from loguru import logger
from qtpy.QtCore import QObject, QSettings, Signal

APP_DIR_NAME = "Trigger Designer"
ENV_DATA_DIR = "TRIGGER_DESIGNER_DATA_DIR"
PREFERENCES_FILENAME = "preferences.ini"
SCHEMA_VERSION = 2

LEGACY_SCOPES: tuple[tuple[str, str], ...] = (
    ("Blue Octa", "Trigger Designer"),
    ("Trigger", "Trigger Designer"),
    ("Trigger", "NodeEditor"),
)

DEFAULTS: dict[str, Any] = {
    "general/schema_version": SCHEMA_VERSION,
    "appearance/theme": "dark",
    "appearance/accent": "",
    # Application font size in points; 0 keeps the system default.
    "appearance/font_size": 0,
    "layout/restore": True,
    "layout/session": False,
    "editor/grid_size": 20,
    "editor/show_grid": True,
    "editor/snap_to_grid": True,
    # JSON object of command id -> key sequence. Kept as text because the INI
    # backend only stores scalars; see qt/helpers/shortcuts.py.
    "editor/shortcuts": "{}",
    "editor/render_detail_threshold": 50,
    "editor/render_detail_card": "auto",
    "editor/render_detail_sockets": "auto",
    "editor/render_detail_label": "always",
    "editor/render_detail_indicator": "auto",
    "errors/continue_past_failure": True,
    "errors/redact_values": False,
    "errors/locate_rows": True,
    "errors/locate_row_cap": 5_000_000,
    "errors/show_technical": False,
    # Audit trail (docs/plan/02-audit-trail.md 3.14): one sealed record per Run.
    "audit/record_runs": True,
    "audit/run_log_dir": "",
    "audit/record_identity": True,
    "audit/hash_inputs": True,
    "audit/hash_outputs": True,
    "audit/hash_max_mb": 2048,
    # auto / all / sink / off (see core/audit/counting.py)
    "audit/row_counts": "auto",
    "audit/exact_counts_max_mb": 256,
    "audit/embed_code": True,
    "audit/warn_on_input_change": True,
}

_MISSING = object()


def app_data_dir() -> Path:
    """Directory that holds preferences and user themes.

    ``TRIGGER_DESIGNER_DATA_DIR`` overrides it (tests, portable installs).
    """
    override = os.getenv(ENV_DATA_DIR)
    if override:
        return Path(override)
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / APP_DIR_NAME
    return Path.home() / ".trigger_designer"


def preferences_path() -> Path:
    return app_data_dir() / PREFERENCES_FILENAME


def user_themes_dir() -> Path:
    return app_data_dir() / "themes"


def bundle_base() -> Path:
    """Read-only resources root (``_MEIPASS`` when frozen)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "trigger_designer"
    return Path(__file__).parents[1]


def _coerce(raw: Any, default: Any) -> Any:
    if raw is None:
        return default
    if isinstance(default, bool):
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(default, int) and not isinstance(default, bool):
        try:
            return int(raw)
        except TypeError, ValueError:
            return default
    if isinstance(default, list):
        if isinstance(raw, str):
            return [raw] if raw.strip() else []
        try:
            return [str(item) for item in list(raw)]
        except TypeError:
            return default
    return raw


class Preferences(QObject):
    """Typed view over one INI file, with one-shot legacy migration."""

    #: Emitted with ``(key, new_value)`` after every successful write.
    changed = Signal(str, object)

    def __init__(
        self,
        path: Path | None = None,
        *,
        migrate: bool = True,
        legacy_sources: Iterable[QSettings] | None = None,
    ) -> None:
        super().__init__()
        self._path = Path(path) if path is not None else preferences_path()
        fresh = not self._path.exists()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = QSettings(str(self._path), QSettings.Format.IniFormat)
        if migrate and fresh:
            try:
                self.migrate_legacy(legacy_sources)
            except Exception as exc:  # noqa: BLE001 - defensive
                logger.warning(f"Preference migration skipped: {exc}")
        if self.settings.value("general/schema_version", None) is None:
            self.settings.setValue("general/schema_version", SCHEMA_VERSION)
            self.settings.sync()

    @property
    def path(self) -> Path:
        return self._path

    # -- typed access -----------------------------------------------------
    def get(self, key: str, default: Any = _MISSING) -> Any:
        if default is _MISSING:
            default = DEFAULTS.get(key)
        raw = self.settings.value(key, None)
        return _coerce(raw, default)

    def set(self, key: str, value: Any, *, sync: bool = True) -> None:
        self.settings.setValue(key, value)
        if sync:
            self.settings.sync()
        self.changed.emit(key, value)

    def contains(self, key: str) -> bool:
        return self.settings.contains(key)

    def remove(self, key: str, *, sync: bool = True) -> None:
        self.settings.remove(key)
        if sync:
            self.settings.sync()
        self.changed.emit(key, None)

    def reset(self, prefix: str | None = None) -> None:
        """Drop every value (or every value under ``prefix/``) back to default."""
        if prefix:
            normalized = prefix.rstrip("/") + "/"
            for key in list(self.settings.allKeys()):
                if key.startswith(normalized):
                    self.settings.remove(key)
        else:
            for key in list(self.settings.allKeys()):
                self.settings.remove(key)
        self.settings.setValue("general/schema_version", SCHEMA_VERSION)
        self.settings.sync()
        self.changed.emit(prefix or "", None)

    def sync(self) -> None:
        self.settings.sync()

    def as_dict(self) -> dict[str, Any]:
        return {key: self.settings.value(key) for key in self.settings.allKeys()}

    # -- migration --------------------------------------------------------
    def migrate_legacy(
        self, sources: Iterable[QSettings] | None = None
    ) -> dict[str, Any]:
        """Copy the first value found in the legacy scopes into the INI.

        Returns the migrated mapping (useful in tests). Existing INI values
        always win; this runs before any user write.
        """
        scopes = list(sources) if sources is not None else _legacy_scopes()
        found: dict[str, Any] = {}

        def first(key: str) -> Any:
            for scope in scopes:
                value = scope.value(key, None)
                if value is not None and str(value) != "":
                    return value
            return None

        def put(target: str, value: Any) -> None:
            if value is None or self.settings.contains(target):
                return
            self.settings.setValue(target, value)
            found[target] = value

        theme = first("theme")
        if theme and str(theme).strip().lower() not in {"", "system"}:
            put("appearance/theme", str(theme))

        grid_size = first("grid_size")
        if grid_size is not None:
            try:
                put("editor/grid_size", int(grid_size))
            except TypeError, ValueError:
                pass

        show_grid = first("show_grid")
        if show_grid is not None:
            put("editor/show_grid", _coerce(show_grid, True))

        welcome = first("show_welcome_dialog")
        if welcome is not None:
            put("show_welcome_dialog", _coerce(welcome, True))

        recents = first("recentFiles")
        if recents is not None:
            put("recentFiles", _coerce(recents, []))

        preview_visible = first("data_preview_dock/visible")
        if preview_visible is not None:
            put("layout/legacy_preview_visible", _coerce(preview_visible, False))

        # Window pos/size written by the stock nodeeditor window.
        for key in ("pos", "size", "geometry", "windowState"):
            value = first(key)
            if value is not None:
                put(f"layout/legacy_{key}", value)

        # Edge/socket colours. Legacy scopes keep them nested under
        # ``node_editor_colors`` (``.../edges/default``), so scan the raw keys
        # instead of ``childKeys()``, which stops at the first group.
        colors_prefix = "node_editor_colors/"
        for scope in scopes:
            for key in scope.allKeys():
                if key.startswith(colors_prefix):
                    put(key, scope.value(key))

        self.settings.setValue("general/schema_version", SCHEMA_VERSION)
        self.settings.sync()
        if found:
            logger.info(f"Migrated {len(found)} preference(s) into {self._path}")
        return found


def _legacy_scopes() -> list[QSettings]:
    return [QSettings(org, app) for org, app in LEGACY_SCOPES]


_instance: Preferences | None = None


def get_preferences() -> Preferences:
    """Process-wide preferences store (created on first use)."""
    global _instance
    if _instance is None:
        _instance = Preferences()
    return _instance
