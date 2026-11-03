"""The Benford chart: observed bars, expected line, drawn with QPainter.

Lazy helper (``_LAZY_HELPER_MODULES``): imported by ``benford.py`` only. No
matplotlib; every colour is a theme token so the chart follows the theme.
"""

from __future__ import annotations

import itertools
import math

from qtpy.QtCore import QPointF, QRectF, QSize, Qt
from qtpy.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from qtpy.QtWidgets import QSizePolicy, QToolTip, QWidget

from trigger_designer.core.audit.benford import BenfordChartData
from trigger_designer.qt.theme_manager import get_theme_manager

_LEFT, _RIGHT, _TOP, _BOTTOM = 34, 6, 8, 18
_STEP = 0.05


def axis_max(data: BenfordChartData) -> float:
    """Top of the y axis: 10 % above the tallest value, on a 5 % step."""
    top = max([*data.observed, *data.expected, 0.0])
    return max(_STEP, math.ceil(top * 1.1 / _STEP - 1e-9) * _STEP)


class BenfordChartWidget(QWidget):
    """Bars for the observed proportions, a dotted line for Benford's expected ones."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("BenfordChart")
        self.setAccessibleName("Benford chart")
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMouseTracking(True)
        self._data: BenfordChartData | None = None
        get_theme_manager().themeChanged.connect(self.apply_theme)

    # ---- model -------------------------------------------------------------
    def set_data(self, data: BenfordChartData | None) -> None:
        self._data = data
        self.update()

    def data(self) -> BenfordChartData | None:
        return self._data

    def apply_theme(self, *_args) -> None:
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(300, 170)

    # ---- geometry ----------------------------------------------------------
    def _plot(self) -> QRectF:
        return QRectF(
            _LEFT,
            _TOP,
            max(1, self.width() - _LEFT - _RIGHT),
            max(1, self.height() - _TOP - _BOTTOM),
        )

    def _slot(self, index: int, count: int) -> QRectF:
        """The full-height column of bar ``index`` (also its hit area)."""
        plot = self._plot()
        width = plot.width() / count
        return QRectF(plot.left() + index * width, plot.top(), width, plot.height())

    def _bar_rect(self, index: int) -> QRectF:
        data = self._data
        assert data is not None
        plot = self._plot()
        slot = self._slot(index, len(data.digits))
        gap = 0.0 if len(data.digits) > 20 else slot.width() * 0.2
        height = plot.height() * data.observed[index] / axis_max(data)
        return QRectF(
            slot.left() + gap / 2, plot.bottom() - height, slot.width() - gap, height
        )

    def index_at(self, x: float) -> int | None:
        data = self._data
        if data is None or not data.digits:
            return None
        plot = self._plot()
        if not plot.left() <= x < plot.right():
            return None
        return min(
            len(data.digits) - 1,
            int((x - plot.left()) / plot.width() * len(data.digits)),
        )

    def tooltip_text(self, index: int) -> str:
        data = self._data
        assert data is not None
        return (
            f"Digit {data.digits[index]}: observed {data.observed[index]:.1%} "
            f"({data.counts[index]:,}), expected {data.expected[index]:.1%}, "
            f"z {data.z[index]:.2f}"
        )

    # ---- painting ----------------------------------------------------------
    @staticmethod
    def _color(token: str) -> QColor:
        return get_theme_manager().color(token)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(self.font())
        font.setPointSize(8)
        painter.setFont(font)
        data = self._data
        if data is None or not data.digits:
            painter.setPen(self._color("text_secondary"))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "No data to chart"
            )
            painter.end()
            return
        plot = self._plot()
        top = axis_max(data)

        grid = QPen(self._color("border_subtle"))
        grid.setWidth(1)
        for step in (1, 2, 3):
            value = top * step / 3
            y = plot.bottom() - plot.height() * step / 3
            painter.setPen(grid)
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(self._color("text_secondary"))
            painter.drawText(
                QRectF(0, y - 7, _LEFT - 4, 14),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{value:.0%}" if top >= 0.2 else f"{value:.1%}",
            )

        count = len(data.digits)
        accent, danger = self._color("accent_primary"), self._color("danger")
        painter.setPen(Qt.PenStyle.NoPen)
        for i, digit in enumerate(data.digits):
            painter.setBrush(danger if digit in data.flagged else accent)
            painter.drawRect(self._bar_rect(i))

        line = QPen(self._color("text_secondary"))
        line.setWidth(2)
        points = [
            QPointF(
                self._slot(i, count).center().x(),
                plot.bottom() - plot.height() * data.expected[i] / top,
            )
            for i in range(count)
        ]
        painter.setPen(line)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for a, b in itertools.pairwise(points):
            painter.drawLine(a, b)
        painter.setBrush(self._color("text_secondary"))
        painter.setPen(Qt.PenStyle.NoPen)
        for point in points:
            painter.drawEllipse(point, 2.0, 2.0)

        painter.setPen(self._color("text_primary"))
        for i, digit in enumerate(data.digits):
            if count > 20 and digit % 10:
                continue
            slot = self._slot(i, count)
            box = QRectF(slot.center().x() - 12, plot.bottom() + 2, 24, _BOTTOM - 2)
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, str(digit))
        painter.end()

    # ---- hover -------------------------------------------------------------
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        index = self.index_at(event.position().x())
        if index is None:
            QToolTip.hideText()
        else:
            QToolTip.showText(
                event.globalPosition().toPoint(), self.tooltip_text(index), self
            )
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        QToolTip.hideText()
        super().leaveEvent(event)
