"""Marks the active tab of every tab bar while no stylesheet is applied.

Qlementine draws the selected tab in the window colour on a tab-bar band. The
band is kept at the window colour too, so tab bars do not stand out from the
panels around them, which leaves nothing to say which tab is active. Each
``QTabBar`` therefore gets a click-through overlay that tints the current tab
and underlines it in the accent colour. The QSS themes style their own tabs,
so the overlay paints only when the application has no stylesheet.

Colours come from the widget's palette (Qlementine sets it from the theme):
the text colour, faintly, for the tint and the highlight colour for the line.
"""

from __future__ import annotations

from qtpy.QtCore import QEvent, QObject, QRectF, Qt
from qtpy.QtGui import QColor, QPainter, QPaintEvent, QPalette
from qtpy.QtWidgets import QApplication, QTabBar, QWidget

#: Opacity of the tint over the active tab, out of 255.
TINT_ALPHA = 28
#: Thickness of the accent line under the active tab, in pixels.
LINE_WIDTH = 2
_MARKED = "tdActiveTabMark"

_NORTH = (QTabBar.Shape.RoundedNorth, QTabBar.Shape.TriangularNorth)
_SOUTH = (QTabBar.Shape.RoundedSouth, QTabBar.Shape.TriangularSouth)
_FOLLOW = (
    QEvent.Type.Resize,
    QEvent.Type.Move,
    QEvent.Type.Show,
    QEvent.Type.LayoutRequest,
    QEvent.Type.StyleChange,
)


class _ActiveTabMark(QWidget):
    """The overlay of one tab bar."""

    def __init__(self, bar: QTabBar) -> None:
        super().__init__(bar)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._bar = bar
        bar.installEventFilter(self)
        bar.currentChanged.connect(self._repaint)
        bar.tabMoved.connect(self._repaint)
        self._follow_bar()
        # A child added to a bar that is already on screen starts hidden.
        self.show()

    def _repaint(self, *_args: object) -> None:
        self.update()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self._bar and event.type() in _FOLLOW:
            self._follow_bar()
        return False

    def _follow_bar(self) -> None:
        self.setGeometry(self._bar.rect())
        self.raise_()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        bar = self._bar
        if QApplication.instance().styleSheet():
            return
        shape = bar.shape()
        if shape not in _NORTH and shape not in _SOUTH:
            return
        index = bar.currentIndex()
        if index < 0:
            return
        tab = bar.tabRect(index)
        if tab.isEmpty():
            return
        palette = bar.palette()
        tint = QColor(palette.color(QPalette.ColorRole.WindowText))
        tint.setAlpha(TINT_ALPHA)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = 4.0
        painter.setClipRect(tab)
        painter.setBrush(tint)
        flat = radius + LINE_WIDTH
        if shape in _NORTH:
            painter.drawRoundedRect(QRectF(tab).adjusted(0, 0, 0, flat), radius, radius)
            line_y = tab.bottom() + 1 - LINE_WIDTH
        else:
            painter.drawRoundedRect(
                QRectF(tab).adjusted(0, -flat, 0, 0), radius, radius
            )
            line_y = tab.top()
        painter.setBrush(palette.color(QPalette.ColorRole.Highlight))
        painter.drawRect(tab.left(), line_y, tab.width(), LINE_WIDTH)
        painter.end()


class ActiveTabMarks(QObject):
    """Attaches the overlay to every tab bar of the application, present and future.

    The overlays are kept referenced here: Qt owns them through their tab bar,
    but PySide drops the Python wrapper (and with it ``_bar``) of an object
    nothing in Python holds, and its event filter then raises.
    """

    def __init__(self) -> None:
        super().__init__()
        self._marks: set[_ActiveTabMark] = set()

    def install(self, app: QApplication) -> None:
        app.installEventFilter(self)
        for widget in app.allWidgets():
            if isinstance(widget, QTabBar):
                self._attach(widget)

    def remove(self, app: QApplication) -> None:
        app.removeEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Polish and isinstance(obj, QTabBar):
            self._attach(obj)
        return False

    def _attach(self, bar: QTabBar) -> None:
        if not bar.property(_MARKED):
            bar.setProperty(_MARKED, True)
            mark = _ActiveTabMark(bar)
            self._marks.add(mark)
            mark.destroyed.connect(lambda *_: self._marks.discard(mark))
