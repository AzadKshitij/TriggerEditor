"""Make every OS-framed window's title bar follow the colour scheme.

Windows that keep a native frame - floating dock groups, ``DataPreviewWindow``,
Qt's own message / input / colour dialogs - take their caption from the OS, so a
light theme still got a black bar (GitHub issue #45). Qt owns those windows, so
they cannot take the in-house chrome; this filter recolours the native caption
instead: caption, text and border colours on Windows 11, the system dark/light
flag on Windows 10, nothing elsewhere.

Windows that draw their own chrome (``FramelessWindowHint``) are skipped: they
paint the theme themselves.
"""

from __future__ import annotations

from loguru import logger
from qtpy.QtCore import QEvent, QObject, Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication, QWidget

from trigger_designer.qt.helpers.win_caption import (
    apply_native_title_colors,
    colorref,
    native_caption_supported,
)
from trigger_designer.qt.theme_manager import get_theme_manager

__all__ = ["NativeTitleTheme", "install_native_title_theme"]

#: Window types that carry a caption; menus, tooltips and splashes do not.
_CAPTIONED = (Qt.WindowType.Window, Qt.WindowType.Dialog, Qt.WindowType.Tool)


def _ref(color: QColor) -> int | None:
    return colorref(color.red(), color.green(), color.blue()) if color.isValid() else None


class NativeTitleTheme(QObject):
    """Application-wide filter that themes each framed window as it appears."""

    def __init__(self, application: QApplication) -> None:
        super().__init__(application)
        self._enabled = native_caption_supported()
        if not self._enabled:
            return
        application.installEventFilter(self)
        get_theme_manager().themeChanged.connect(self.reapply)

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        # Sees every event of the application: one bad event must never take
        # the event loop down with it.
        try:
            if (
                event.type() in (QEvent.Type.Show, QEvent.Type.WinIdChange)
                and isinstance(obj, QWidget)
                and obj.isWindow()
            ):
                self.apply(obj)
        except Exception:  # noqa: BLE001 - guard, see comment above
            logger.exception("native title theming failed")
        return False

    def reapply(self, _theme: object = None) -> None:
        """Recolour every visible framed window after a theme change."""
        for window in QApplication.topLevelWidgets():
            if window.isVisible():
                self.apply(window)

    def apply(self, window: QWidget) -> None:
        if (
            not self._enabled
            or window.windowType() not in _CAPTIONED
            or window.windowFlags() & Qt.WindowType.FramelessWindowHint
        ):
            return
        manager = get_theme_manager()
        apply_native_title_colors(
            int(window.winId()),
            dark=manager.is_dark(),
            caption=_ref(manager.color("background_secondary")),
            text=_ref(manager.color("text_primary")),
            border=_ref(manager.color("border_primary")),
        )


def install_native_title_theme(application: QApplication) -> NativeTitleTheme:
    """Start theming framed windows; keep the returned object alive."""
    return NativeTitleTheme(application)
