"""Canvas view overrides for the installed ``nodeeditor`` package.

``TriggerCutLine`` keeps the library's cut stroke and takes the theme's text
colour when no stylesheet is set, because the library draws it white. The view
draws the drag-selection box itself, since Qlementine draws no ``QRubberBand``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nodeeditor.node_graphics_cutline import QDMCutLine
from nodeeditor.node_graphics_view import QDMGraphicsView
from qtpy.QtCore import QMargins, QRect, QRectF
from qtpy.QtGui import QColor, QPainter, QPalette, QPen
from qtpy.QtWidgets import QApplication

if TYPE_CHECKING:
    from nodeeditor.node_graphics_scene import QDMGraphicsScene
    from qtpy.QtWidgets import QWidget


class TriggerCutLine(QDMCutLine):
    """The library's cut stroke, in the theme's text colour when unstyled.

    The library paints the stroke white, which vanishes on a light canvas once
    no stylesheet is set (Qlementine). Take the theme's text colour then; the
    classic themes keep the library's colour.
    """

    def paint(self, painter, option, widget=None) -> None:
        if not QApplication.instance().styleSheet():
            self._pen.setColor(
                QApplication.palette().color(QPalette.ColorRole.WindowText)
            )
        super().paint(painter, option, widget)


#: Opacity of the selection box fill, out of 255.
BAND_FILL_ALPHA = 56


class TriggerGraphicsView(QDMGraphicsView):
    """The canvas view, drawing the cut line and the selection box."""

    CutLine_class = TriggerCutLine

    def __init__(
        self, grScene: QDMGraphicsScene, parent: QWidget | None = None
    ) -> None:
        super().__init__(grScene, parent)
        # The base view hard-codes ``QDMCutLine``; swap it before the first stroke.
        self.grScene.removeItem(self.cutline)
        self.cutline = self.CutLine_class()
        self.grScene.addItem(self.cutline)
        self._band = QRect()
        self.rubberBandChanged.connect(self._on_band_changed)

    def _on_band_changed(self, rect: QRect, *_args: object) -> None:
        """Track the drag-selection rectangle (empty once the drag ends)."""
        old, self._band = self._band, QRect(rect)
        margin = QMargins(2, 2, 2, 2)
        self.viewport().update(old.normalized().marginsAdded(margin))
        self.viewport().update(self._band.normalized().marginsAdded(margin))

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)
        # Qlementine draws no ``QRubberBand``; the classic styles do, and their
        # stylesheet is what tells the two apart.
        if self._band.isEmpty() or QApplication.instance().styleSheet():
            return
        accent = self.palette().color(QPalette.ColorRole.Highlight)
        fill = QColor(accent)
        fill.setAlpha(BAND_FILL_ALPHA)
        painter.save()
        painter.resetTransform()
        painter.setPen(QPen(accent, 1))
        painter.setBrush(fill)
        painter.drawRect(self._band.normalized().adjusted(0, 0, -1, -1))
        painter.restore()
