"""Theme-aware widgets used by the Preferences and Theme editor dialogs.

These paint from a theme token mapping rather than QSS because they render a
*preview* of tokens that are not applied yet (the editor's working set).
Accessible appearance follows the design system: constant 1px border, hover
and focus restated in paint, no inline stylesheet.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from qtpy.QtCore import QRectF, QSize, Qt, Signal
from qtpy.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPen,
)
from qtpy.QtWidgets import (
    QAbstractButton,
    QColorDialog,
    QSizePolicy,
    QWidget,
)

from trigger_designer.qt.theme_manager import get_theme_manager


def _resolve(tokens: Mapping[str, Any] | None, key: str, fallback: str) -> QColor:
    if tokens is not None:
        value = tokens.get(key)
        if value is not None:
            color = QColor(value)
            if color.isValid():
                return color
    return get_theme_manager().color(key, fallback)


def _hex_with_alpha(color: QColor) -> str:
    if color.alpha() < 255:
        return color.name(QColor.NameFormat.HexArgb)
    return color.name(QColor.NameFormat.HexRgb)


def relative_luminance(color: QColor) -> float:
    """WCAG relative luminance of an sRGB colour."""

    def channel(value: float) -> float:
        value = value / 255.0
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(color.red())
        + 0.7152 * channel(color.green())
        + 0.0722 * channel(color.blue())
    )


def contrast_ratio(foreground: QColor | str, background: QColor | str) -> float:
    """WCAG contrast ratio (1..21) between two colours."""
    fg = QColor(foreground)
    bg = QColor(background)
    if not fg.isValid() or not bg.isValid():
        return 0.0
    light, dark = sorted((relative_luminance(fg), relative_luminance(bg)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


class ColorSwatchButton(QAbstractButton):
    """A 34x22 colour swatch that opens ``QColorDialog`` on click."""

    colorChanged = Signal(str)

    def __init__(
        self,
        color: str = "#000000",
        parent: QWidget | None = None,
        *,
        swatch_size: QSize | None = None,
        object_name: str = "ColorSwatch",
        open_dialog: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setFixedSize(QSize(34, 22) if swatch_size is None else swatch_size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._color = QColor(color)
        self._tokens: Mapping[str, Any] | None = None
        self._open_dialog = open_dialog
        self.clicked.connect(self._pick_color)

    @property
    def color(self) -> QColor:
        return QColor(self._color)

    def color_name(self) -> str:
        return _hex_with_alpha(self._color)

    def set_color(self, value: str | QColor, *, emit: bool = False) -> None:
        color = QColor(value)
        if not color.isValid():
            return
        changed = color != self._color
        self._color = color
        self.update()
        if emit and changed:
            self.colorChanged.emit(self.color_name())

    def set_tokens(self, tokens: Mapping[str, Any]) -> None:
        self._tokens = tokens
        self.update()

    def _pick_color(self) -> None:
        if not self._open_dialog:
            self.colorChanged.emit(self.color_name())
            return
        color = QColorDialog.getColor(
            self._color,
            self,
            "Choose colour",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if color.isValid():
            self.set_color(color, emit=True)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.5)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.5, -1.5)
        border = _resolve(self._tokens, "border_default", "#3e4750")
        if self.underMouse() or self.hasFocus():
            border = _resolve(self._tokens, "accent_secondary", "#6a96d7")
        painter.setPen(QPen(border, 1))
        painter.setBrush(QBrush(self._color))
        painter.drawRoundedRect(rect, 3, 3)
        if self.hasFocus():
            accent = _resolve(self._tokens, "accent_primary", "#5680c2")
            painter.setPen(QPen(accent, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                QRectF(self.rect()).adjusted(0.5, 0.5, -1.0, -1.0), 4, 4
            )


class ThemePreviewWidget(QWidget):
    """A miniature app: chrome strip, node canvas and a log strip."""

    #: Emitted with a human label when the user clicks a preview node.
    nodePicked = Signal(str)

    def __init__(
        self,
        tokens: Mapping[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ThemePreview")
        self._tokens: Mapping[str, Any] | None = dict(tokens) if tokens else None
        self.setMinimumSize(QSize(240, 190))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(210)

    def set_tokens(self, tokens: Mapping[str, Any]) -> None:
        self._tokens = dict(tokens)
        self.update()

    def _color(self, key: str, fallback: str) -> QColor:
        return _resolve(self._tokens, key, fallback)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        base = self._color("background_primary", "#14171b")
        raised = self._color("background_secondary", "#191e22")
        border = self._color("border_default", "#2f363d")

        painter.setPen(QPen(border, 1))
        painter.setBrush(QBrush(base))
        painter.drawRoundedRect(outer, 6, 6)

        body = outer.adjusted(0, 0, 0, 0)
        strip_h = 24.0
        log_h = 34.0
        strip = QRectF(body.x(), body.y(), body.width(), strip_h)
        canvas = QRectF(
            body.x(),
            body.y() + strip_h,
            body.width(),
            body.height() - strip_h - log_h,
        )
        log = QRectF(body.x(), body.bottom() - log_h, body.width(), log_h)

        painter.save()
        painter.setClipRect(strip)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(raised))
        painter.drawRect(strip)
        accent = self._color("accent_primary", "#5680c2")
        painter.setBrush(QBrush(accent))
        painter.drawRoundedRect(
            QRectF(strip.left() + 8, strip.center().y() - 5, 42, 10), 3, 3
        )
        chip = self._color("background_tertiary", "#1e242a")
        painter.setBrush(QBrush(chip))
        painter.setPen(QPen(border, 1))
        for index in range(3):
            painter.drawRoundedRect(
                QRectF(strip.right() - 70 + index * 22, strip.center().y() - 7, 18, 14),
                3,
                3,
            )
        painter.restore()

        painter.save()
        painter.setClipRect(canvas)
        canvas_bg = self._color("canvas_background", "#0e1115")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(canvas_bg))
        painter.drawRect(canvas)
        minor = self._color("canvas_grid_light", "#17ffffff")
        major = self._color("canvas_grid_dark", "#26ffffff")
        painter.setPen(QPen(minor, 1))
        step = 14
        x = canvas.left() + 6
        while x < canvas.right():
            painter.drawLine(int(x), int(canvas.top()), int(x), int(canvas.bottom()))
            x += step
        y = canvas.top() + 6
        while y < canvas.bottom():
            painter.drawLine(int(canvas.left()), int(y), int(canvas.right()), int(y))
            y += step
        painter.setPen(QPen(major, 1))
        for ratio in (0.25, 0.5, 0.75):
            x = canvas.left() + canvas.width() * ratio
            painter.drawLine(int(x), int(canvas.top()), int(x), int(canvas.bottom()))
        self._paint_node(painter, canvas, 0.16, 0.30, "node_input", border)
        self._paint_node(painter, canvas, 0.52, 0.18, "node_prepare", border)
        self._paint_node(painter, canvas, 0.52, 0.58, "node_transform", border)
        painter.restore()

        painter.save()
        painter.setClipRect(log)
        inset = self._color("editor_background", "#101418")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(inset))
        painter.drawRect(log)
        painter.setPen(QPen(border, 1))
        painter.drawLine(
            int(log.left()), int(log.top()), int(log.right()), int(log.top())
        )
        text = self._color("text_secondary", "#c6cdd5")
        info = self._color("info", "#5ba8d6")
        warning = self._color("warning", "#d9a441")
        line_y = log.top() + 9
        painter.setPen(QPen(info, 3))
        painter.drawLine(
            int(log.left() + 10), int(line_y), int(log.left() + 26), int(line_y)
        )
        painter.setPen(QPen(text, 3))
        painter.drawLine(
            int(log.left() + 32), int(line_y), int(log.right() - 90), int(line_y)
        )
        line_y += 10
        painter.setPen(QPen(warning, 3))
        painter.drawLine(
            int(log.left() + 10), int(line_y), int(log.left() + 22), int(line_y)
        )
        painter.setPen(QPen(text, 3))
        painter.drawLine(
            int(log.left() + 28), int(line_y), int(log.right() - 60), int(line_y)
        )
        painter.restore()

    def _paint_node(
        self,
        painter: QPainter,
        canvas: QRectF,
        x_ratio: float,
        y_ratio: float,
        token: str,
        border: QColor,
    ) -> None:
        width, height = 54.0, 26.0
        x = canvas.left() + canvas.width() * x_ratio
        y = canvas.top() + canvas.height() * y_ratio
        rect = QRectF(x, y, width, height)
        category = self._color(token, "#5680c2")
        painter.setPen(QPen(border, 1))
        painter.setBrush(QBrush(self._color("background_tertiary", "#1e242a")))
        painter.drawRoundedRect(rect, 4, 4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(category))
        painter.drawRoundedRect(
            QRectF(rect.x() + 1, rect.y() + 1, rect.width() - 2, 6), 3, 3
        )
        painter.setPen(QPen(border, 2))
        painter.drawLine(
            int(rect.left() + 6),
            int(rect.center().y() + 2),
            int(rect.right() - 8),
            int(rect.center().y() + 2),
        )

    def mousePressEvent(self, event) -> None:
        self.nodePicked.emit("preview")
        super().mousePressEvent(event)
