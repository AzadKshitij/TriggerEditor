"""Theme-coloured glyphs for the dock title-bar buttons and tab close buttons.

QtAds draws its buttons from the style's standard icons, which are a dark grey
that all but vanishes on a dark theme and differ between styles. These are
drawn in code from the theme's text colour, so they follow the theme and the
display scale under both engines. Pure Qt: nothing here imports QtAds.
"""

from __future__ import annotations

from qtpy.QtCore import QPointF, QRectF, Qt
from qtpy.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
)

#: Glyph names understood by :func:`glyph_icon`.
MENU = "menu"
UNDOCK = "undock"
CLOSE = "close"
GLYPHS = (MENU, UNDOCK, CLOSE)

#: Logical size of a glyph, in pixels.
SIZE = 16
#: Opacity of the disabled state, out of 255.
DISABLED_ALPHA = 90


def _draw(painter: QPainter, glyph: str) -> None:
    if glyph == MENU:
        painter.drawPolyline([QPointF(4.5, 6.5), QPointF(8, 10), QPointF(11.5, 6.5)])
    elif glyph == UNDOCK:
        painter.drawRoundedRect(QRectF(3.5, 6.5, 6, 6), 1, 1)
        painter.drawPolyline(
            [QPointF(6.5, 6.5), QPointF(6.5, 3.5), QPointF(12.5, 3.5)]
            + [QPointF(12.5, 9.5), QPointF(9.5, 9.5)]
        )
    elif glyph == CLOSE:
        painter.drawLine(QPointF(4.5, 4.5), QPointF(11.5, 11.5))
        painter.drawLine(QPointF(11.5, 4.5), QPointF(4.5, 11.5))
    else:
        raise ValueError(f"Unknown dock glyph {glyph!r}")


def _pixmap(glyph: str, color: QColor, dpr: float) -> QPixmap:
    side = max(1, round(SIZE * dpr))
    pixmap = QPixmap(side, side)
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, 1.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    _draw(painter, glyph)
    painter.end()
    return pixmap


def glyph_icon(glyph: str, color: QColor) -> QIcon:
    """The glyph in ``color``, with a faded disabled variant."""
    screen = QGuiApplication.primaryScreen()
    dpr = float(screen.devicePixelRatio()) if screen is not None else 1.0
    faded = QColor(color)
    faded.setAlpha(DISABLED_ALPHA)
    icon = QIcon()
    icon.addPixmap(_pixmap(glyph, color, dpr), QIcon.Mode.Normal)
    icon.addPixmap(_pixmap(glyph, faded, dpr), QIcon.Mode.Disabled)
    return icon
