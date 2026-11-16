"""Canvas view overrides for the installed ``nodeeditor`` package.

``QDMCutLine`` builds its bounding rectangle from ``line_points``, but the
library replaces that list without calling ``prepareGeometryChange``. Qt then
repaints the item's *new* bounds only: while a CTRL-drag grows the stroke the
old pixels stay inside the new rectangle, but when the stroke ends the list is
emptied first, so the area the line covered is never repainted and the line
stays on the canvas until something else redraws the viewport (issue #34).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from nodeeditor.node_graphics_cutline import QDMCutLine
from nodeeditor.node_graphics_view import QDMGraphicsView
from qtpy.QtCore import QMargins, QPointF, QRect, QRectF
from qtpy.QtGui import QColor, QPainter, QPalette, QPen
from qtpy.QtWidgets import QApplication

if TYPE_CHECKING:
    from nodeeditor.node_graphics_scene import QDMGraphicsScene
    from qtpy.QtWidgets import QGraphicsItem, QWidget


class TriggerCutLine(QDMCutLine):
    """A cut line that reports its geometry change before it happens.

    Replacing the points moves ``boundingRect``, and Qt only repaints the area
    the item declared before the change. Declaring it covers the stroke that
    the release would otherwise leave behind.
    """

    def __init__(self, parent: QGraphicsItem | None = None) -> None:
        # Set first: ``QDMCutLine.__init__`` assigns ``line_points`` itself.
        self._points: list[QPointF] = []
        super().__init__(parent)

    @property
    def line_points(self) -> list[QPointF]:
        return self._points

    @line_points.setter
    def line_points(self, points: Iterable[QPointF]) -> None:
        points = list(points)
        if points == self._points:
            return
        self.prepareGeometryChange()
        self._points = points

    def paint(self, painter, option, widget=None) -> None:
        # The library draws white, which vanishes on a light canvas. Without a
        # stylesheet (Qlementine) take the theme's text colour; classic is as it was.
        if not QApplication.instance().styleSheet():
            self._pen.setColor(
                QApplication.palette().color(QPalette.ColorRole.WindowText)
            )
        super().paint(painter, option, widget)


#: Opacity of the selection box fill, out of 255.
BAND_FILL_ALPHA = 56


class TriggerGraphicsView(QDMGraphicsView):
    """The canvas view, drawing the repaint-safe cut line and selection box."""

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
