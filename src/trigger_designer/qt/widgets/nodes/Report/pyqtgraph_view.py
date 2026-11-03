"""pyqtgraph implementation of the Graph window's chart renderer.

The opt-in second renderer for the Graph node. It is deliberately an
independent implementation of the :class:`~chart_renderer.ChartRenderer`
contract: same ``ChartSpec`` in, same category ticks and tooltip numbers
out, no drawing code shared with the matplotlib view. Where the two cannot
feel identical is the toolbar - pyqtgraph has no ``NavigationToolbar2QT`` -
so this module ships a small one (reset view, save PNG) and the window
title says which renderer is up.

``nodes/__init__`` keeps this module out of its startup import sweep;
pyqtgraph loads the first time a window actually selects this renderer.
"""

from __future__ import annotations

import math
from typing import Any

import pyqtgraph as pg
from qtpy.QtCore import QCoreApplication, QEvent
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QWidget

from trigger_designer.core.charts import ChartSpec
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.widgets.common import IconButton
from trigger_designer.qt.widgets.nodes.Report.chart_renderer import (
    SERIES_COLORS,
    ChartRenderer,
    categories,
    category_labels,
    format_value,
    is_numeric_x,
    to_float,
    x_name,
)

#: Line width in pixels; matplotlib drew ``linewidth=2``.
_LINE_WIDTH = 2

#: Scatter spot diameter; matplotlib drew ``s=36`` (area, ~6 px radius).
_SCATTER_SPOT_PX = 12

#: Diameter of the invisible overlay spots that carry hover for lines and
#: bars. pyqtgraph hit-tests against the spot rect, so this is its version
#: of matplotlib's cursor radius.
_HOVER_SPOT_PX = 14

#: Corner offset (px) of the legend inside the plot, mirroring the
#: matplotlib legend's default upper-right corner.
_LEGEND_OFFSET = (10, 10)


class PyqtgraphChartView(ChartRenderer):
    """Draws a ``ChartSpec`` with pyqtgraph; a message draws its text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._plot = pg.PlotWidget(self)
        # One legend for the widget's life; renders clear it and toggle it.
        self._legend = self._plot.getPlotItem().addLegend(offset=_LEGEND_OFFSET)
        self._legend.setVisible(False)

        self._text_color = "#000000"
        self._background = "#ffffff"

        # Hover state: the items the last render drew, so the tooltip text
        # is resolved from the hovered spot's own payload without asking
        # the model again.
        self._tooltip: Any = None
        self._hover_key: str | None = None
        self._series_items: list[Any] = []
        self._x_label = ""
        self._y_label = ""
        self._show_series_names = False

        self._stack.addWidget(self._plot)
        self.set_spec(None)

    @property
    def plot(self) -> pg.PlotWidget | None:
        """The pyqtgraph canvas; the toolbar resets and saves through this."""
        return self._plot

    # -- contract hooks ----------------------------------------------------
    def plot_is_live(self) -> bool:
        return self._plot is not None

    def plot_page(self) -> QWidget:
        return self._plot

    def clear_plot(self) -> None:
        """Drop every drawn item so the next render starts clean."""
        plot_item = self._plot.getPlotItem()
        plot_item.clear()
        plot_item.getAxis("bottom").setTicks(None)
        self._series_items = []
        self._tooltip = None
        self._hover_key = None
        self._legend.clear()
        self._legend.setVisible(False)

    def render_plot(self, spec: ChartSpec) -> None:
        self.clear_plot()
        plot_item = self._plot.getPlotItem()
        self._apply_theme(plot_item)
        plot_item.setTitle(spec.title, color=self._text_color)
        plot_item.setLabel("bottom", spec.x_column, color=self._text_color)
        plot_item.setLabel("left", spec.y_column, color=self._text_color)
        self._x_label = spec.x_column
        self._y_label = spec.y_column

        show_legend = len(spec.series) > 1 and any(item.name for item in spec.series)
        self._show_series_names = show_legend
        self._legend.setVisible(show_legend)
        if spec.chart_type == "bar":
            self._draw_bars(spec, plot_item, show_legend)
        else:
            cats = None if is_numeric_x(spec.series) else categories(spec.series)
            self._draw_points(spec, plot_item, cats, show_legend)
            if cats is not None:
                self._set_category_ticks(plot_item, cats)

        # Rebuilt with each chart (like the matplotlib annotation), and never
        # drawn empty: pyqtgraph tooltips are plain scene items.
        fill = QColor(self._background)
        fill.setAlphaF(0.95)
        self._tooltip = pg.TextItem(
            text="",
            color=self._text_color,
            fill=pg.mkBrush(fill),
            border=pg.mkPen(self._text_color),
            anchor=(0, 1),
        )
        self._tooltip.setZValue(1000)
        plot_item.addItem(self._tooltip, ignoreBounds=True)
        self._tooltip.hide()

    # -- drawing ---------------------------------------------------------
    def dispose(self) -> None:
        """Release the plot widget in its own event-loop pass.

        The same discipline as the matplotlib canvas: tests call this before
        the shared widget cleanup so a scene is never destroyed in the same
        batch as the windows around it.
        """
        plot = getattr(self, "_plot", None)
        if plot is None:
            return
        self._plot = None
        self._tooltip = None
        try:
            plot.hide()
            plot.deleteLater()
        except RuntimeError:
            return
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.processEvents()

    def _apply_theme(self, plot_item: pg.PlotItem) -> None:
        palette = self.palette()
        self._background = palette.color(QPalette.ColorRole.Window).name()
        self._text_color = palette.color(QPalette.ColorRole.WindowText).name()

        # ViewBox.setBackgroundColor, not PlotWidget.setBackground: the
        # latter lands on the QGraphicsView's own brush and leaves the plot
        # area itself untouched.
        self._plot.getViewBox().setBackgroundColor(QColor(self._background))
        pen = pg.mkPen(QColor(self._text_color))
        for name in ("bottom", "left", "top", "right"):
            axis = plot_item.getAxis(name)
            axis.setPen(pen)
            axis.setTextPen(pen)
        plot_item.showGrid(x=False, y=True, alpha=0.2)

    def _draw_points(
        self,
        spec: ChartSpec,
        plot_item: pg.PlotItem,
        cats: list[Any] | None,
        show_legend: bool,
    ) -> None:
        positions = (
            {value: index for index, value in enumerate(cats)}
            if cats is not None
            else None
        )
        for order, series in enumerate(spec.series):
            color = SERIES_COLORS[order % len(SERIES_COLORS)]
            if positions is None:
                xs = [to_float(value) for value in series.x]
                labels = [format_value(value) for value in xs]
            else:
                xs = [float(positions[value]) for value in series.x]
                labels = [x_name(value) for value in series.x]
            ys = [to_float(value) for value in series.y]
            # NaN points are dropped from the hover payload: a missing value
            # has nothing to report, matching the matplotlib view.
            hovers = [
                (x, y, (label, y, series.name))
                for x, y, label in zip(xs, ys, labels)
                if math.isfinite(x) and math.isfinite(y)
            ]
            if spec.chart_type == "scatter":
                # The visible item carries its own hover payload.
                item = pg.ScatterPlotItem(
                    size=_SCATTER_SPOT_PX, brush=pg.mkBrush(color), hoverable=True
                )
                item.setData(
                    x=[point[0] for point in hovers],
                    y=[point[1] for point in hovers],
                    data=[point[2] for point in hovers],
                )
                hoverable = item
            else:
                # connect='finite' splits the curve at non-finite points,
                # so a missing value leaves a gap rather than being bridged
                # over - what matplotlib's line plot does with NaN.
                item = pg.PlotCurveItem(
                    x=xs,
                    y=ys,
                    pen=pg.mkPen(color, width=_LINE_WIDTH),
                    connect="finite",
                )
                hoverable = self._hover_overlay(hovers)
            plot_item.addItem(item)
            if hoverable is not item:
                plot_item.addItem(hoverable)
            hoverable.sigHovered.connect(self._on_hover)
            self._series_items.append(item)
            if show_legend:
                self._legend.addItem(item, series.name)

    def _draw_bars(
        self, spec: ChartSpec, plot_item: pg.PlotItem, show_legend: bool
    ) -> None:
        cats = categories(spec.series)
        names = [x_name(value) for value in cats]
        positions = {value: index for index, value in enumerate(cats)}
        count = max(1, len(spec.series))
        width = 0.8 / count

        for order, series in enumerate(spec.series):
            color = SERIES_COLORS[order % len(SERIES_COLORS)]
            offset = (order - (count - 1) / 2) * width
            centers: list[float] = []
            ys: list[float] = []
            hovers: list[tuple[float, float, tuple[str, float, str]]] = []
            for value, y in zip(series.x, series.y):
                index = positions.get(value)
                if index is None:
                    continue
                height = to_float(y)
                centre = index + offset
                centers.append(centre)
                ys.append(height)
                if math.isfinite(height):
                    hovers.append((centre, height, (names[index], height, series.name)))
            if not centers:
                continue
            # Signed heights: pyqtgraph draws 0 -> height in both directions,
            # like matplotlib's bars.
            item = pg.BarGraphItem(
                x=centers, height=ys, width=width, brush=pg.mkBrush(color)
            )
            plot_item.addItem(item)
            # Hover at the bar value; the whole bar face is not a hit area
            # the way matplotlib's rect test was. That difference is real and
            # acceptable - see the toolbar note.
            overlay = self._hover_overlay(hovers)
            overlay.sigHovered.connect(self._on_hover)
            plot_item.addItem(overlay)
            self._series_items.append(item)
            if show_legend:
                self._legend.addItem(item, series.name)
        self._set_category_ticks(plot_item, cats)

    def _hover_overlay(
        self, hovers: list[tuple[float, float, tuple[str, float, str]]]
    ) -> pg.ScatterPlotItem:
        """Invisible spots that give pyqtgraph something hoverable to hit."""
        overlay = pg.ScatterPlotItem(
            x=[point[0] for point in hovers],
            y=[point[1] for point in hovers],
            data=[point[2] for point in hovers],
            size=_HOVER_SPOT_PX,
            symbol="s",
            brush=pg.mkBrush(0, 0, 0, 0),
            hoverable=True,
        )
        return overlay

    def _set_category_ticks(self, plot_item: pg.PlotItem, cats: list[Any]) -> None:
        labels = category_labels(cats)
        plot_item.getAxis("bottom").setTicks(
            [[(float(index), label) for index, label in enumerate(labels) if label]]
        )

    # -- hover -----------------------------------------------------------
    def _on_hover(self, _item: Any, points: Any, _event: Any) -> None:
        """Show the hovered value in the floating text item.

        ``points`` are pyqtgraph ``SpotItem``s (or, in tests, anything with
        ``pos()`` and ``data()``): empty means the cursor left, and the
        payload placed on each spot by ``_hover_overlay`` carries
        ``(x label, y value, series name)``.
        """
        if self._tooltip is None or len(points) == 0:
            self._hide_hover()
            return
        point = points[0]
        x_text, y_value, series_name = point.data()
        position = point.pos()
        self._show_hover(
            position.x(), position.y(), self._hover_text(x_text, y_value, series_name)
        )

    def _hover_text(self, x_text: str, y_value: float, series_name: str) -> str:
        lines: list[str] = []
        if self._show_series_names and series_name:
            lines.append(series_name)
        lines.append(f"{self._x_label or 'X'}: {x_text}")
        lines.append(f"{self._y_label or 'Y'}: {format_value(y_value)}")
        return "\n".join(lines)

    def _show_hover(self, x: float, y: float, text: str) -> None:
        if self._tooltip is None or text == self._hover_key:
            return
        self._hover_key = text
        self._tooltip.setPos(x, y)
        self._tooltip.setText(text)
        self._tooltip.show()

    def _hide_hover(self) -> None:
        if self._tooltip is not None and self._tooltip.isVisible():
            self._tooltip.hide()
        self._hover_key = None


class PyqtgraphChartToolbar(QWidget):
    """Reset view + save PNG: what pyqtgraph's toolbar contract needs.

    pyqtgraph has no counterpart to the matplotlib navigation toolbar, and
    the two renderers are not meant to feel identical here - the window
    title names the renderer so the user knows which toolbar they are
    looking at.
    """

    def __init__(self, view: PyqtgraphChartView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view = view
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 4, 5, 4)
        layout.setSpacing(4)

        self.reset_button = IconButton.themed(
            "Reset view",
            rsm_icon=ResourceManager().get("icon_zoom_fit"),
        )
        self.reset_button.clicked.connect(self.reset_view)
        self.save_button = IconButton.themed(
            "Save PNG",
            rsm_icon=ResourceManager().get("icon_save"),
        )
        self.save_button.clicked.connect(self.save_png)

        layout.addWidget(self.reset_button)
        layout.addWidget(self.save_button)
        layout.addStretch()

    def reset_view(self) -> None:
        """Re-enable auto range and fit the data: pyqtgraph's 'home'."""
        plot = self._view.plot
        if plot is None:
            return
        view_box = plot.getViewBox()
        view_box.enableAutoRange()
        view_box.autoRange()

    def save_png(self) -> str | None:
        """Write the plot page out; the only file this window writes."""
        plot = self._view.plot
        if plot is None:
            return None
        path, _filter = QFileDialog.getSaveFileName(
            self, "Save PNG", "chart.png", "PNG image (*.png)"
        )
        if not path:
            return None
        plot.grab().save(path)
        return path


def create_view(parent: QWidget | None = None) -> PyqtgraphChartView:
    """The renderer-module contract ``chart_window`` builds against."""
    return PyqtgraphChartView(parent)


def create_toolbar(
    view: PyqtgraphChartView, parent: QWidget | None = None
) -> PyqtgraphChartToolbar:
    """The pyqtgraph half of the per-renderer toolbar contract."""
    return PyqtgraphChartToolbar(view, parent)
