"""Theme repository, validation and application.

A theme is a JSON document:

.. code-block:: json

    {"schema": 2, "id": "midnight", "name": "Midnight",
     "appearance": "dark", "extends": "dark", "tokens": {...}}

``base.qss`` is a ``str.format`` template; a theme's ``tokens`` are the
substitutions. Built-ins ship read-only in ``resources/qt/themes``; user
themes live in ``%APPDATA%/Trigger Designer/themes`` and may ``extends`` a
built-in (or another user theme) to inherit tokens.

The old flat schema (``{"name": "dark", "background_primary": ...}``) is
still accepted and treated as ``tokens``, so a not-yet-migrated file keeps
working.

This module is the only place that calls ``QApplication.setStyleSheet``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import orjson as json
from loguru import logger
from qtpy.QtCore import QObject, Qt, Signal
from qtpy.QtGui import QColor, QGuiApplication, QPalette
from qtpy.QtWidgets import QApplication, QWidget

from trigger_designer.qt.checkbox_icons import TOKENS as _CHECKBOX_TOKENS
from trigger_designer.qt.checkbox_icons import checkbox_tokens
from trigger_designer.qt.preferences import (
    Preferences,
    bundle_base,
    get_preferences,
    user_themes_dir,
)

SCHEMA_VERSION = 2
SYSTEM_THEME_ID = "system"
DEFAULT_THEME_ID = "dark"

_META_KEYS = {"schema", "id", "name", "appearance", "extends", "tokens"}
_BRACES_RE = re.compile(r"[{}]")
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_FUNC_COLOR_RE = re.compile(r"^(?:rgb|rgba|hsl|hsla)\(", re.IGNORECASE)

#: Colour tokens grouped for the theme editor. Every painted token must
#: appear here so the editor exposes it; geometry tokens stay design-system
#: owned and are deliberately absent.
TOKEN_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Surfaces",
        (
            ("background_primary", "Base"),
            ("background_secondary", "Raised"),
            ("background_tertiary", "Overlay"),
            ("background_hover", "Hover"),
            ("background_pressed", "Pressed"),
            ("background_disabled", "Disabled"),
            ("background_alternate", "Alternate"),
            ("card_background", "Card"),
            ("editor_background", "Inset / editor"),
            ("statusbar_background", "Status bar"),
            ("separator_background", "Separator"),
            ("scroll_background", "Scroll track"),
        ),
    ),
    (
        "Text",
        (
            ("text_primary", "Primary"),
            ("text_secondary", "Secondary"),
            ("text_tertiary", "Tertiary"),
            ("text_inactive", "Meta"),
            ("text_disabled", "Disabled"),
        ),
    ),
    (
        "Accent",
        (
            ("accent_primary", "Accent"),
            ("accent_secondary", "Hover"),
            ("accent_tertiary", "Pressed"),
            ("accent_disabled", "Disabled"),
        ),
    ),
    (
        "Status",
        (
            ("success", "Success"),
            ("warning", "Warning"),
            ("danger", "Danger"),
            ("info", "Info"),
            ("activity", "Running"),
            ("error_text", "Error text"),
            ("background_warning", "Warning surface"),
        ),
    ),
    (
        "Borders",
        (
            ("border_primary", "Subtle"),
            ("border_subtle", "Hairline"),
            ("border_default", "Default"),
            ("border_strong", "Strong"),
            ("border_light", "Light"),
            ("border_dark", "Dark"),
            ("border_accent", "Accent"),
            ("card_border", "Card"),
        ),
    ),
    (
        "Controls",
        (
            ("button_bg", "Button"),
            ("button_hover", "Button hover"),
            ("button_pressed", "Button pressed"),
            ("menu_background", "Menu"),
            ("menu_separator", "Menu separator"),
            ("control_scrollbar_bg", "Scrollbar"),
            ("control_scrollbar_handle", "Scrollbar handle"),
            ("control_menu_bg", "Control menu"),
            ("control_toolbar_bg", "Toolbar"),
        ),
    ),
    (
        "Canvas",
        (
            ("canvas_background", "Canvas"),
            ("canvas_grid_light", "Grid minor"),
            ("canvas_grid_dark", "Grid major"),
        ),
    ),
    (
        "Code",
        (
            ("editor_line_number_background", "Gutter"),
            ("editor_line_number_text", "Gutter text"),
            ("editor_current_line", "Current line"),
            ("syntax_keyword", "Keyword"),
            ("syntax_string", "String"),
            ("syntax_number", "Number"),
            ("syntax_column", "Column"),
            ("syntax_function", "Function"),
            ("syntax_operator", "Operator"),
            ("syntax_comment", "Comment"),
        ),
    ),
    (
        "Nodes",
        (
            ("node_input", "Input"),
            ("node_prepare", "Prepare"),
            ("node_join", "Join"),
            ("node_transform", "Transform"),
            ("node_report", "Report"),
            ("node_selection", "Selection ring"),
            ("selection_color", "Selection text"),
        ),
    ),
)

#: All colour keys the editor validates.
COLOR_KEYS: frozenset[str] = frozenset(
    key for _group, rows in TOKEN_GROUPS for key, _label in rows
)

#: base.qss tokens computed at format time, so theme JSONs need not define them.
DERIVED_TOKENS = frozenset({"text_on_accent"}) | _CHECKBOX_TOKENS


def _text_on(background: str) -> str:
    """Black or white, whichever reads better on ``background``."""
    c = QColor(background)
    luminance = 0.2126 * c.redF() + 0.7152 * c.greenF() + 0.0722 * c.blueF()
    return "#10151a" if luminance > 0.6 else "#ffffff"



class ThemeError(Exception):
    """Raised when a theme cannot be parsed or formatted into QSS."""


@dataclass
class Theme:
    id: str
    name: str
    appearance: str  # "dark" | "light"
    tokens: dict[str, Any]
    source: Path | None = None
    builtin: bool = False
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def is_dark(self) -> bool:
        return self.appearance == "dark"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "custom-theme"


def _looks_like_color(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped:
        return False
    return bool(_HEX_RE.match(stripped) or _FUNC_COLOR_RE.match(stripped))


def _is_valid_color(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return QColor(value).isValid()


class ThemeManager(QObject):
    """Loads, resolves, validates, previews and applies themes."""

    #: Emitted with the active :class:`Theme` after a theme is applied.
    themeChanged = Signal(object)
    #: Emitted when the set of available themes changes (save/import/delete).
    themesChanged = Signal()

    def __init__(
        self,
        preferences: Preferences | None = None,
        builtin_dir: Path | None = None,
        themes_dir: Path | None = None,
        app: QApplication | None = None,
    ) -> None:
        super().__init__()
        self._prefs = preferences or get_preferences()
        self._builtin_dir = (
            Path(builtin_dir)
            if builtin_dir
            else (bundle_base() / "resources" / "qt" / "themes")
        )
        self._themes_dir = Path(themes_dir) if themes_dir else user_themes_dir()
        # ``QApplication.instance()`` is typed as ``QCoreApplication``; the
        # subclass cast keeps the style-sheet and window APIs visible.
        self._app = (
            app
            if app is not None
            else cast("QApplication | None", QApplication.instance())
        )
        self._preview_id: str | None = None
        self._cache: dict[str, Theme] = {}
        self._color_cache: dict[tuple[str, str], QColor] = {}
        # ``base.qss`` and the default theme's tokens are read-only at runtime,
        # so read them once per manager instead of on every stylesheet build.
        self._qss_text: str | None = None
        self._fallback_cache: dict[str, Any] | None = None
        self._active_key: tuple[str, str] | None = None
        self._active_cached: Theme | None = None
        self._system_following = False
        self._connect_system_scheme()

    # -- paths ------------------------------------------------------------
    @property
    def preferences(self) -> Preferences:
        return self._prefs

    @property
    def builtin_dir(self) -> Path:
        return self._builtin_dir

    @property
    def user_dir(self) -> Path:
        return self._themes_dir

    def _candidate_files(self, theme_id: str) -> list[Path]:
        return [
            self._themes_dir / f"{theme_id}.json",
            self._builtin_dir / f"{theme_id}.json",
        ]

    def _find_file(self, theme_id: str) -> Path | None:
        for candidate in self._candidate_files(theme_id):
            if candidate.is_file():
                return candidate
        return None

    # -- loading ----------------------------------------------------------
    def _read_data(self, path: Path) -> dict[str, Any]:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ThemeError(f"Unable to read {path.name}: {exc}") from exc
        try:
            data = json.loads(raw)
        except Exception as exc:
            raise ThemeError(f"Invalid JSON in {path.name}: {exc}") from exc
        if not isinstance(data, dict):
            raise ThemeError(f"{path.name} must contain a JSON object")
        return data

    @staticmethod
    def _extract_tokens(data: Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(data.get("tokens"), Mapping):
            return dict(data["tokens"])
        return {key: value for key, value in data.items() if key not in _META_KEYS}

    def _resolve_tokens(
        self,
        theme_id: str,
        data: Mapping[str, Any],
        *,
        seen: set[str] | None = None,
    ) -> tuple[dict[str, Any], list[str], list[str]]:
        warnings: list[str] = []
        errors: list[str] = []
        ancestors = set(seen or ())
        chain: list[str] = [theme_id]
        tokens = self._extract_tokens(data)
        parent_id = data.get("extends")
        cursor = str(parent_id) if parent_id else None
        while cursor:
            if cursor in ancestors or cursor in chain:
                errors.append(f"Circular theme inheritance via '{cursor}'")
                break
            chain.append(cursor)
            parent_path = self._find_file(cursor)
            if parent_path is None:
                warnings.append(f"Inherited theme '{cursor}' was not found")
                break
            parent_data = self._read_data(parent_path)
            parent_tokens = self._extract_tokens(parent_data)
            tokens = {**parent_tokens, **tokens}
            cursor = parent_data.get("extends")
            cursor = str(cursor) if cursor else None
        return (
            self._validate_tokens(tokens, warnings=warnings),
            warnings,
            errors,
        )

    def _validate_tokens(
        self, tokens: dict[str, Any], *, warnings: list[str]
    ) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        for key, value in tokens.items():
            if _BRACES_RE.search(str(value)):
                warnings.append(f"Token '{key}' contained braces and was dropped")
                continue
            if (key in COLOR_KEYS or _looks_like_color(value)) and not _is_valid_color(
                value
            ):
                warnings.append(f"Token '{key}' is not a valid colour ({value!r})")
                continue
            clean[key] = value
        return clean

    def _fallback_tokens(self) -> dict[str, Any]:
        if self._fallback_cache is None:
            path = self._builtin_dir / f"{DEFAULT_THEME_ID}.json"
            try:
                self._fallback_cache = self._extract_tokens(self._read_data(path))
            except ThemeError:
                self._fallback_cache = {}
        # A copy: callers may fold these into a theme's own token map.
        return dict(self._fallback_cache)

    def _base_qss(self) -> str:
        """The ``base.qss`` template text, read once per manager."""
        if self._qss_text is None:
            qss_path = self._builtin_dir / "base.qss"
            try:
                self._qss_text = qss_path.read_text(encoding="utf-8")
            except OSError as exc:
                raise ThemeError(f"Unable to read base.qss: {exc}") from exc
        return self._qss_text

    def theme(self, theme_id: str, *, force: bool = False) -> Theme:
        """A raw theme (no accent override) by id, with fallback on error."""
        if not force and theme_id in self._cache:
            return self._cache[theme_id]

        if theme_id == SYSTEM_THEME_ID:
            theme = self._system_theme()
            self._cache[theme_id] = theme
            return theme

        path = self._find_file(theme_id)
        if path is None:
            fallback = self._fallback_tokens()
            theme = Theme(
                id=theme_id,
                name=theme_id,
                appearance="dark",
                tokens=fallback,
                builtin=False,
                error=f"Theme '{theme_id}' not found",
            )
            self._cache[theme_id] = theme
            return theme

        builtin = path.parent == self._builtin_dir
        try:
            data = self._read_data(path)
            tokens, warnings, errors = self._resolve_tokens(theme_id, data)
            if errors:
                raise ThemeError("; ".join(errors))
            if not tokens and not data.get("extends"):
                raise ThemeError("Theme defines no tokens")
            # A user theme may omit tokens added since it was written; fill
            # from the built-in default instead of crashing at format time.
            missing = self._fallback_tokens()
            for key, value in missing.items():
                if key not in tokens:
                    tokens[key] = value
            name = str(data.get("name") or theme_id)
            appearance = str(data.get("appearance") or "dark").lower()
            if appearance not in {"dark", "light"}:
                warnings.append(f"Unknown appearance '{appearance}'; using dark")
                appearance = "dark"
            theme = Theme(
                id=theme_id,
                name=name,
                appearance=appearance,
                tokens=tokens,
                source=path,
                builtin=builtin,
                warnings=warnings,
            )
            if warnings:
                logger.warning(f"Theme '{theme_id}': {'; '.join(warnings)}")
        except ThemeError as exc:
            fallback = self._fallback_tokens()
            theme = Theme(
                id=theme_id,
                name=theme_id,
                appearance="dark",
                tokens=fallback,
                source=path,
                builtin=builtin,
                error=str(exc),
            )
            logger.error(f"Theme '{theme_id}' failed to load: {exc}")
        self._cache[theme_id] = theme
        return theme

    def available_themes(self) -> list[Theme]:
        """Every concrete theme (built-ins first, then user themes)."""
        ids: list[str] = []
        for folder in (self._builtin_dir, self._themes_dir):
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                if path.stem not in ids:
                    ids.append(path.stem)
        return [self.theme(theme_id) for theme_id in ids]

    def invalidate(self, theme_id: str | None = None) -> None:
        if theme_id:
            self._cache.pop(theme_id, None)
        else:
            self._cache.clear()
        # The default theme's tokens back the fallback fill; drop them too so a
        # changed file is re-read. ``base.qss`` ships fixed, so it stays cached.
        self._fallback_cache = None
        self._color_cache.clear()
        self._active_cached = None

    # -- system appearance ------------------------------------------------
    def _system_appearance(self) -> str:
        try:
            hints = QGuiApplication.styleHints()
            scheme = hints.colorScheme() if hints is not None else None
            if scheme == Qt.ColorScheme.Light:
                return "light"
            if scheme == Qt.ColorScheme.Dark:
                return "dark"
        except Exception as exc:  # noqa: BLE001 - older Qt without colourScheme
            logger.debug(f"Colour scheme unavailable: {exc}")
        app = self._app
        if app is not None:
            window = app.activeWindow()
            if (
                window is not None
                and window.palette().color(QPalette.ColorRole.Window).lightness() > 160
            ):
                return "light"
        return "dark"

    def system_appearance(self) -> str:
        """Public: the appearance System mode currently resolves to."""
        return self._system_appearance()

    def _system_theme(self) -> Theme:
        target = self._system_appearance()
        base = self.theme(target if target in {"dark", "light"} else "dark")
        theme = Theme(
            id=SYSTEM_THEME_ID,
            name="System",
            appearance=target,
            tokens=dict(base.tokens),
            source=None,
            builtin=True,
            error=base.error,
            warnings=list(base.warnings),
        )
        return theme

    def _connect_system_scheme(self) -> None:
        if self._system_following:
            return
        app = self._app
        if app is None:
            return
        try:
            hints = app.styleHints()
            if hints is not None:
                hints.colorSchemeChanged.connect(self._on_system_scheme_changed)
                self._system_following = True
        except Exception as exc:  # noqa: BLE001 - signal not present on older Qt
            logger.debug(f"System colour scheme signal unavailable: {exc}")

    def _on_system_scheme_changed(self, *_args: Any) -> None:
        if self.requested_theme_id() == SYSTEM_THEME_ID:
            self.invalidate(SYSTEM_THEME_ID)
            self.apply(persist=False)

    # -- request / accent -------------------------------------------------
    def requested_theme_id(self) -> str:
        value = self._prefs.get("appearance/theme", DEFAULT_THEME_ID)
        return str(value) if value else DEFAULT_THEME_ID

    def requested_accent(self) -> str:
        value = self._prefs.get("appearance/accent", "")
        return str(value).strip() if value else ""

    def _apply_accent(self, theme: Theme) -> dict[str, Any]:
        accent = self.requested_accent()
        tokens = dict(theme.tokens)
        if not accent:
            return tokens
        base = QColor(accent)
        if not base.isValid():
            return tokens
        if theme.is_dark:
            hover = base.lighter(118)
            pressed = base.darker(120)
        else:
            hover = base.lighter(112)
            pressed = base.darker(112)
        surface = QColor(tokens.get("background_primary", "#000000"))
        if not surface.isValid():
            surface = QColor("#000000")
        disabled = QColor(
            round(base.red() * 0.45 + surface.red() * 0.55),
            round(base.green() * 0.45 + surface.green() * 0.55),
            round(base.blue() * 0.45 + surface.blue() * 0.55),
        )
        tokens["accent_primary"] = base.name()
        tokens["accent_secondary"] = hover.name()
        tokens["accent_tertiary"] = pressed.name()
        tokens["accent_disabled"] = disabled.name()
        tokens["border_accent"] = hover.name()
        return tokens

    def active_theme(self) -> Theme:
        """The theme currently applied, preview included and accent resolved."""
        requested = self._preview_id or self.requested_theme_id()
        accent = self.requested_accent()
        key = (requested, accent)
        if self._active_cached is not None and self._active_key == key:
            return self._active_cached
        theme = self.resolved_theme(requested)
        self._active_key = key
        self._active_cached = theme
        return theme

    def resolved_theme(self, theme_id: str) -> Theme:
        """``theme_id`` with the user accent applied (if any)."""
        theme = self.theme(theme_id)
        return Theme(
            id=theme.id,
            name=theme.name,
            appearance=theme.appearance,
            tokens=self._apply_accent(theme),
            source=theme.source,
            builtin=theme.builtin,
            error=theme.error,
            warnings=list(theme.warnings),
        )

    def stylesheet_for(self, theme_id: str) -> str:
        """Build QSS for an arbitrary theme id without applying it."""
        return self.stylesheet(self.resolved_theme(theme_id))

    def color(self, token: str, default: Any = None) -> QColor:
        """Resolve one token against the active theme (Python-painted surfaces)."""
        theme = self.active_theme()
        cache_key = (theme.id, token)
        cached = self._color_cache.get(cache_key)
        if cached is not None:
            return QColor(cached)
        value = theme.tokens.get(token, default)
        color = QColor(value) if value is not None else QColor()
        if not color.isValid() and default is not None:
            color = QColor(default)
        self._color_cache[cache_key] = QColor(color)
        return color

    def token(self, token: str, default: Any = None) -> Any:
        return self.active_theme().tokens.get(token, default)

    def is_dark(self) -> bool:
        return self.active_theme().is_dark

    # -- stylesheet + application ----------------------------------------
    def stylesheet(self, theme: Theme | None = None) -> str:
        theme = theme or self.active_theme()
        qss = self._base_qss()
        tokens = dict(self._fallback_tokens())
        tokens.update(theme.tokens)
        tokens.setdefault("text_on_accent", _text_on(tokens["accent_primary"]))
        tokens.update(checkbox_tokens(tokens))
        try:
            return qss.format(**tokens)
        except KeyError as exc:
            raise ThemeError(
                f"Theme '{theme.id}' is missing token {exc.args[0]!r} required by base.qss"
            ) from exc

    def apply(self, theme_id: str | None = None, *, persist: bool = False) -> Theme:
        """Apply a theme now; optionally remember it as the user's choice."""
        if theme_id is not None:
            if persist:
                self._prefs.set("appearance/theme", theme_id)
                self._preview_id = None
            else:
                # Session-only switch: the stored choice survives a restart.
                self._preview_id = theme_id
        theme = self.active_theme()
        if self._app is not None:
            self._app.setStyleSheet(self.stylesheet(theme))
        self._color_cache.clear()
        self._active_cached = None
        self._invalidate_icon_cache()
        self.themeChanged.emit(theme)
        return theme

    def preview(self, theme_id: str) -> Theme:
        """Apply ``theme_id`` without persisting it (Cancel restores)."""
        self._preview_id = theme_id
        self._active_cached = None
        theme = self.active_theme()
        if self._app is not None:
            self._app.setStyleSheet(self.stylesheet(theme))
        self._color_cache.clear()
        self._invalidate_icon_cache()
        self.themeChanged.emit(theme)
        return theme

    @staticmethod
    def _invalidate_icon_cache() -> None:
        """Drop the cached pixmaps of the theme-tinted glyphs.

        The resource manager caches rendered pixmaps by id, so a theme
        switch has to clear them or every already-built button keeps the
        glyph it was painted with.
        """
        from trigger_designer.qt.resource_manager import ResourceManager

        ResourceManager._cache.clear()

    def commit_preview(self) -> Theme:
        if self._preview_id is not None:
            self._prefs.set("appearance/theme", self._preview_id)
            self._preview_id = None
        return self.apply(persist=False)

    def cancel_preview(self) -> Theme:
        self._preview_id = None
        return self.apply(persist=False)

    def set_accent(self, accent: str, *, persist: bool = True) -> Theme:
        if persist:
            self._prefs.set("appearance/accent", accent or "")
        return self.apply(persist=False)

    # -- user themes ------------------------------------------------------
    def new_theme_id(self, name: str) -> str:
        base = _slugify(name)
        candidate = base
        index = 2
        while self._find_file(candidate) is not None:
            candidate = f"{base}-{index}"
            index += 1
        return candidate

    def save_user_theme(
        self,
        theme_id: str,
        name: str,
        appearance: str,
        tokens: Mapping[str, Any],
        *,
        extends: str | None = None,
    ) -> Theme:
        self._themes_dir.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "schema": SCHEMA_VERSION,
            "id": theme_id,
            "name": name,
            "appearance": "light" if appearance == "light" else "dark",
            "tokens": dict(tokens),
        }
        if extends:
            payload["extends"] = extends
        path = self._themes_dir / f"{theme_id}.json"
        path.write_bytes(
            json.dumps(payload, option=json.OPT_INDENT_2 | json.OPT_SORT_KEYS)
        )
        self.invalidate(theme_id)
        self.themesChanged.emit()
        return self.theme(theme_id, force=True)

    def delete_user_theme(self, theme_id: str) -> bool:
        path = self._themes_dir / f"{theme_id}.json"
        if not path.is_file():
            return False
        path.unlink()
        self.invalidate(theme_id)
        if self.requested_theme_id() == theme_id:
            self._prefs.set("appearance/theme", DEFAULT_THEME_ID)
        self.themesChanged.emit()
        return True

    def import_theme(self, path: str | Path) -> Theme:
        source = Path(path)
        data = self._read_data(source)
        requested_id = str(data.get("id") or _slugify(source.stem))
        name = str(data.get("name") or requested_id)
        theme_id = requested_id
        if (self._themes_dir / f"{theme_id}.json").is_file():
            theme_id = self.new_theme_id(requested_id)
        tokens, _warnings, errors = self._resolve_tokens(theme_id, data)
        if errors or not tokens:
            raise ThemeError("; ".join(errors) or f"{source.name} defines no tokens")
        extends = data.get("extends")
        return self.save_user_theme(
            theme_id,
            name,
            str(data.get("appearance") or "dark"),
            tokens,
            extends=str(extends) if extends else None,
        )

    def export_theme(self, theme_id: str, path: str | Path) -> Path:
        theme = self.theme(theme_id)
        payload = {
            "schema": SCHEMA_VERSION,
            "id": theme.id,
            "name": theme.name,
            "appearance": theme.appearance,
            "tokens": dict(theme.tokens),
        }
        target = Path(path)
        target.write_bytes(json.dumps(payload, option=json.OPT_INDENT_2))
        return target

    def duplicate_theme(self, theme_id: str, name: str | None = None) -> Theme:
        """Copy any theme into a fresh, editable user theme."""
        base = self.theme(theme_id)
        display = name or f"{base.name} Custom"
        new_id = self.new_theme_id(display)
        return self.save_user_theme(new_id, display, base.appearance, base.tokens)


_instance: ThemeManager | None = None


def get_theme_manager() -> ThemeManager:
    global _instance
    if _instance is None:
        _instance = ThemeManager()
    return _instance


def reset_theme_manager_instance() -> None:
    global _instance
    _instance = None


def _set_grid_colour(gr_scene: Any, colour: QColor, *, light: bool) -> None:
    """Set one grid colour on ``gr_scene`` without tripping the vendored print.

    ``QDMGraphicsScene.setGridColorLight`` writes a debug emoji to stdout.
    A windowed build has no stdout, so the write raises - and the failure
    used to abort the whole canvas theming, which meant the grid size and
    the visibility never reached the canvas either. The setter's own
    effect is small enough to apply directly; the public setter is used
    when the internals are not what we expect.
    """
    colour_attr = "_color_light" if light else "_color_dark"
    pen_attr = "_pen_light" if light else "_pen_dark"
    pen = getattr(gr_scene, pen_attr, None)
    if pen is None or not hasattr(gr_scene, colour_attr):
        setter = gr_scene.setGridColorLight if light else gr_scene.setGridColorDark
        setter(colour)
        return
    setattr(gr_scene, colour_attr, colour)
    pen.setColor(colour)


def apply_theme_to_scene(scene: Any, manager: ThemeManager | None = None) -> None:
    """Colour a ``TriggerScene`` canvas/grid from the active theme + prefs."""
    manager = manager or get_theme_manager()
    gr_scene = getattr(scene, "grScene", None)
    if gr_scene is None:
        return
    background = manager.color("canvas_background", "#0E1115")
    light = manager.color("canvas_grid_light", "#17FFFFFF")
    dark = manager.color("canvas_grid_dark", "#26FFFFFF")
    prefs = manager.preferences

    # The user's grid settings first, and on their own: they are what the
    # preferences dialog promises, and they must not be lost to a failure
    # in the painting below.
    try:
        gr_scene.gridSize = int(prefs.get("editor/grid_size", 20) or 20)
        gr_scene.showGrid = bool(prefs.get("editor/show_grid", True))
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning(f"Unable to apply the grid settings: {exc}")

    try:
        gr_scene.setBackgroundColor(background)
        _set_grid_colour(gr_scene, light, light=True)
        _set_grid_colour(gr_scene, dark, light=False)
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning(f"Unable to theme the canvas: {exc}")

    try:
        gr_scene.update()
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning(f"Unable to repaint the canvas: {exc}")


def repolish(widget: QWidget | None) -> None:
    """Re-evaluate QSS for a widget after a dynamic property change."""
    if widget is None:
        return
    style = widget.style()
    if style is None:
        return
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
