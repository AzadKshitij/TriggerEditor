"""Optional Qlementine QStyle backend for the ``qlementine`` theme engine.

Qlementine (https://github.com/oclero/qlementine) is a C++ ``QStyle``. Unlike
a stylesheet it paints natively, follows ``QPalette`` and costs nothing to
parse. ``ThemeManager`` stays the only caller: it hands this module the
resolved colour tokens and gets the application style, palette and font
swapped, and swapped back when a QSS theme is chosen again.

Two upstream limits shape this module:

* Qlementine does not support proxy styles, and ``QStyleSheetStyle`` is one:
  with any application stylesheet active, ``widget.style()`` is no longer the
  Qlementine object, its event filters and delegates go quiet, and a
  ``QComboBox`` overflows the stack in ``sizeHint()`` (oclero/qlementine#155,
  #125). The caller must clear the application stylesheet before installing.
* Replacing the style destroys it, while delegates it installed keep pointers
  to it (#133). The style object is therefore created once and kept alive for
  the life of the process, even while a QSS theme is active.

The package is optional (Windows x64 wheel only), so everything degrades to
"unavailable" instead of raising, and the manager falls back to the QSS look.
:func:`theme_dict` is pure, so the token mapping is testable without it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from loguru import logger
from qtpy.QtCore import QJsonDocument
from qtpy.QtGui import QColor, QFont, QPalette
from qtpy.QtWidgets import QApplication, QStyle, QStyleFactory

from trigger_designer.qt.tab_indicator import ActiveTabMarks

try:
    import PySide6Qlementine as _q
    from shiboken6 import isValid as _is_valid
except Exception as exc:  # noqa: BLE001 - ImportError, or a DLL that fails to load
    _q = None
    _is_valid = None
    logger.debug(f"Qlementine style unavailable: {exc}")

_PX_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)")

#: Control height of the app's design system (``docs/DESIGN_SYSTEM.md``).
CONTROL_HEIGHT = 30
#: Height of a tab, at 100% scale. Qlementine makes a tab ``controlHeightLarge +
#: spacing`` tall (34 px with the dark themes' 4 px spacing, 38 with 8 px), which
#: leaves a band of empty space around a one-line label.
TAB_HEIGHT = 28
#: Extra width given to each menu-bar item, so File / Edit / Window / Help breathe.
MENU_BAR_ITEM_EXTRA_W = 6


def _px(value: Any, default: float) -> float:
    match = _PX_RE.match(str(value)) if value is not None else None
    return float(match.group(1)) if match else default


def _hex(color: QColor) -> str:
    """Qlementine's ``#rrggbbaa`` (Qt's own hex form puts alpha first)."""
    return f"#{color.red():02x}{color.green():02x}{color.blue():02x}{color.alpha():02x}"


def _mix(a: QColor, b: QColor, amount: float) -> QColor:
    """``amount`` of ``a`` over ``b``, opaque."""
    return QColor(
        round(a.red() * amount + b.red() * (1 - amount)),
        round(a.green() * amount + b.green() * (1 - amount)),
        round(a.blue() * amount + b.blue() * (1 - amount)),
    )


def _on(color: QColor) -> QColor:
    """Black or white text, whichever reads better on ``color``."""
    luminance = 0.2126 * color.redF() + 0.7152 * color.greenF() + 0.0722 * color.blueF()
    return QColor("#10151a" if luminance > 0.6 else "#ffffff")


def theme_dict(
    tokens: Mapping[str, Any],
    *,
    dark: bool,
    base: Mapping[str, Any],
    font_px: int = 12,
    scale: float = 1.0,
) -> dict[str, Any]:
    """Qlementine theme JSON for ``tokens``, laid over ``base``.

    ``base`` is Qlementine's own dark or light theme: every key the tokens do
    not cover (shadows, translucent overlays, animation timings, dial and
    slider metrics) keeps its tuned value. Colours use Qlementine's
    ``#rrggbbaa`` syntax.
    """
    out: dict[str, Any] = dict(base)

    def tok(*keys: str) -> QColor | None:
        for key in keys:
            color = QColor(str(tokens.get(key, "")))
            if color.isValid():
                return color
        return None

    def put(name: str, color: QColor | None) -> None:
        if color is not None and color.isValid():
            out[name] = _hex(color)

    def states(
        name: str,
        color: QColor | None,
        *,
        hovered: QColor | None = None,
        pressed: QColor | None = None,
        disabled: QColor | None = None,
    ) -> None:
        if color is None:
            return
        put(name, color)
        put(f"{name}Hovered", hovered or color.lighter(112))
        put(f"{name}Pressed", pressed or color.lighter(125))
        put(f"{name}Disabled", disabled or _mix(color, window, 0.4))

    window = tok("background_primary") or QColor("#000000" if dark else "#ffffff")
    inset = tok("editor_background", "background_primary")

    put("backgroundColorMain1", inset)
    put("backgroundColorMain2", window)
    put("backgroundColorMain3", tok("background_secondary"))
    put("backgroundColorMain4", tok("background_tertiary"))
    put("backgroundColorWorkspace", tok("canvas_background"))
    # Tab bars blend into the panels around them; the active tab is marked by
    # ``tab_indicator`` instead of by a differently coloured band.
    put("backgroundColorTabBar", window)

    states(
        "neutralColor",
        tok("button_bg", "background_secondary"),
        hovered=tok("background_hover"),
        pressed=tok("background_pressed"),
        disabled=tok("background_disabled"),
    )
    states(
        "borderColor",
        tok("border_default", "border_primary"),
        hovered=tok("border_strong"),
        pressed=tok("accent_primary"),
        disabled=tok("border_subtle"),
    )

    accent = tok("accent_primary")
    if accent is not None:
        on_accent = tok("text_on_accent") or _on(accent)
        states(
            "primaryColor",
            accent,
            hovered=tok("accent_secondary"),
            pressed=tok("accent_tertiary"),
            disabled=tok("accent_disabled"),
        )
        states(
            "primaryColorForeground",
            on_accent,
            hovered=on_accent,
            pressed=on_accent,
            disabled=tok("text_disabled"),
        )
        states(
            "primaryAlternativeColor",
            tok("accent_tertiary") or accent.darker(115),
            hovered=accent,
            pressed=tok("accent_secondary"),
            disabled=tok("accent_disabled"),
        )
        focus = QColor(accent)
        focus.setAlpha(0x66)
        put("focusColor", focus)

    text = tok("text_primary")
    states(
        "secondaryColor",
        text,
        hovered=text,
        pressed=tok("text_secondary"),
        disabled=tok("text_disabled"),
    )
    states(
        "secondaryColorForeground",
        window,
        hovered=window,
        pressed=window,
        disabled=tok("text_disabled"),
    )
    states(
        "secondaryAlternativeColor",
        tok("text_inactive", "text_secondary"),
        hovered=tok("text_secondary"),
        pressed=tok("text_primary"),
        disabled=tok("text_disabled"),
    )

    for name, key in (
        ("statusColorSuccess", "success"),
        ("statusColorInfo", "info"),
        ("statusColorWarning", "warning"),
        ("statusColorError", "danger"),
    ):
        states(name, tok(key))
    warning = tok("warning")
    if warning is not None:
        states("statusColorForeground", _on(warning))

    radius = _px(tokens.get("border_radius"), float(out.get("borderRadius", 6)))
    out["borderRadius"] = radius
    out["borderWidth"] = _px(
        tokens.get("border_width"), float(out.get("borderWidth", 1))
    )
    out["checkBoxBorderRadius"] = min(float(out.get("checkBoxBorderRadius", 4)), radius)
    out["menuItemBorderRadius"] = min(float(out.get("menuItemBorderRadius", 4)), radius)
    out["menuBarItemBorderRadius"] = min(
        float(out.get("menuBarItemBorderRadius", 4)), radius
    )
    out["spacing"] = round(
        _px(tokens.get("spacing_medium"), float(out.get("spacing", 8)))
    )
    out["controlHeightLarge"] = round(CONTROL_HEIGHT * max(scale, 1.0))
    # No empty band above the tab labels.
    out["tabBarPaddingTop"] = 0
    out["fontSize"] = font_px
    out["fontSizeMonospace"] = font_px
    out["fontSizeS1"] = max(8, font_px - 2)
    out["useSystemFonts"] = True
    out["meta"] = {
        "name": "Trigger Designer",
        "author": "Trigger Designer",
        "version": "1",
    }
    return out


@dataclass
class _Saved:
    """What the application looked like before Qlementine took over."""

    style: str
    palette: QPalette
    font: QFont


_shared_style: Any = None


if _q is not None:

    class _TriggerQlementineStyle(_q.QlementineStyle):
        """Qlementine with the app's tab height and menu-bar item width.

        A subclass, not a proxy style (which Qlementine does not support): it
        only post-adjusts two size hints, and everything is drawn by Qlementine.
        ``tab_height`` and ``menu_item_extra_w`` are set by the backend, in
        device pixels, so they follow the display scale.
        """

        tab_height = TAB_HEIGHT
        menu_item_extra_w = MENU_BAR_ITEM_EXTRA_W

        def sizeFromContents(self, ct, option, size, widget=None):
            result = super().sizeFromContents(ct, option, size, widget)
            if ct == QStyle.ContentsType.CT_TabBarTab:
                result.setHeight(min(result.height(), self.tab_height))
            elif ct == QStyle.ContentsType.CT_MenuBarItem:
                result.setWidth(result.width() + self.menu_item_extra_w)
            return result

else:
    _TriggerQlementineStyle = None


def _qlementine_style() -> Any:
    """The one Qlementine style object of the process, created on first use.

    It is never deleted: widgets and delegates it polished keep pointers to it
    (oclero/qlementine#133), so a style tied to anything shorter-lived than the
    process (a theme manager, a test) leaves them dangling, and the next
    application stylesheet crashes while repolishing them.
    """
    global _shared_style
    if _shared_style is None or not _is_valid(_shared_style):
        _shared_style = _TriggerQlementineStyle()
    return _shared_style


class QlementineBackend:
    """Installs and removes the Qlementine application style."""

    def __init__(self) -> None:
        self._style: Any = None
        self._marks: ActiveTabMarks | None = None
        self._saved: _Saved | None = None
        self._active = False
        self._failed = False

    @property
    def available(self) -> bool:
        return _q is not None and not self._failed

    @property
    def active(self) -> bool:
        """Whether Qlementine is currently the application style."""
        return self._active and self._style is not None and _is_valid(self._style)

    def install(
        self,
        app: QApplication,
        tokens: Mapping[str, Any],
        *,
        dark: bool,
        font_px: int,
        scale: float,
    ) -> bool:
        """Make Qlementine the application style, coloured from ``tokens``.

        The application stylesheet must already be clear (see the module
        docstring); the style it replaces is recorded here, and a stylesheet
        proxy would hide its name.
        """
        if not self.available:
            return False
        try:
            if not self.active:
                self._saved = _Saved(
                    style=app.style().objectName(),
                    palette=QPalette(app.palette()),
                    font=QFont(app.font()),
                )
            base = (_q.Theme.makeDark() if dark else _q.Theme.makeLight()).toJson()
            data = theme_dict(
                tokens,
                dark=dark,
                base=base.toVariant(),
                font_px=font_px,
                scale=scale,
            )
            theme = _q.Theme.fromJsonDoc(QJsonDocument.fromVariant(data))
            self._style = _qlementine_style()
            if not self.active:
                app.setStyle(self._style)
                self._active = True
            self._style.tab_height = round(TAB_HEIGHT * max(scale, 1.0))
            self._style.menu_item_extra_w = round(
                MENU_BAR_ITEM_EXTRA_W * max(scale, 1.0)
            )
            self._style.setTheme(theme)
            if self._marks is None:
                self._marks = ActiveTabMarks()
            self._marks.install(app)
        except Exception as exc:  # noqa: BLE001 - a native failure must not stop the app
            logger.error(f"Qlementine could not be applied; using the QSS look: {exc}")
            self._failed = True
            self.uninstall(app)
            return False
        return True

    def uninstall(self, app: QApplication) -> bool:
        """Restore the style, palette and font Qlementine replaced."""
        if not self.active or self._saved is None:
            self._active = False
            return False
        saved = self._saved
        self._active = False
        if self._marks is not None:
            self._marks.remove(app)
        # Qt deletes a replaced style only while the application owns it, so
        # let go of it first: it must outlive the switch.
        self._style.setParent(None)
        stock = QStyleFactory.create(saved.style)
        if stock is not None:
            app.setStyle(stock)
        app.setPalette(saved.palette)
        app.setFont(saved.font)
        return True
