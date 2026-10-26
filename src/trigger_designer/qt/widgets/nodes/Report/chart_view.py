"""matplotlib implementation of the Graph window's chart renderer.

The Config Dock configures the chart; the window draws it. Everything drawn
comes from a :class:`~trigger_designer.core.charts.ChartSpec`, so no frame,
setting or node state crosses this boundary. The shared message-page
behaviour and the label logic that keeps both renderers in agreement live
in :mod:`chart_renderer`; nothing about drawing is shared with
``pyqtgraph_view`` on purpose.

``nodes/__init__`` keeps this module, ``chart_window``, ``chart_renderer``
and ``pyqtgraph_view`` out of its startup import sweep, so matplotlib loads
the first time a chart window actually opens rather than on every launch.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from qtpy.QtCore import QCoreApplication, QEvent
from qtpy.QtGui import QPalette
from qtpy.QtWidgets import QApplication, QWidget

from trigger_designer.core.charts import ChartSpec
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

#: Cursor distance, in pixels, at which a point or bar counts as hovered.
_HOVER_RADIUS_PX = 12


class _ChartToolbar(NavigationToolbar2QT):
    """Toolbar without the subplot editor.

    ``configure_subplots`` calls ``subplots_adjust`` and switches the figure
    to a tight layout, which conflicts with the constrained layout the chart
    draws with; the rest of the toolbar (home, pan, zoom, save) is fine.
    """

    toolitems = tuple(
        item for item in NavigationToolbar2QT.toolitems if item[0] != "Subplots"
    )


def create_view(parent: QWidget | None = None) -> ChartView:
    """The renderer-module contract ``chart_window`` builds against."""
    return ChartView(parent)


def create_toolbar(view: ChartView, parent: QWidget | None = None) -> QWidget:
    """The matplotlib half of the per-renderer toolbar contract."""
    return _ChartToolbar(view.canvas, parent)


class ChartView(ChartRenderer):
    """Draws a ``ChartSpec`` with matplotlib; a message draws its text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text_color = "#000000"
        self._background = "#ffffff"

        # Hover state: what the last render drew, so motion can resolve the
        # point or bar under the cursor without asking the model again.
        self._annotation: Any = None
        self._hover_points: list[tuple[list[float], list[float], list[str], str]] = []
        self._hover_bars: list[tuple[float, float, float, float, str, float, str]] = []
        self._hover_key: str | None = None
        self._x_label = ""
        self._y_label = ""
        self._show_series_names = False

        self.figure = Figure(layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.axes = self.figure.add_subplot(111)

        self._stack.addWidget(self.canvas)

        self._hover_cid = self.canvas.mpl_connect(
            "motion_notify_event", self._on_motion
        )
        self.set_spec(None)

    # -- contract hooks ----------------------------------------------------
    def plot_is_live(self) -> bool:
        return self.canvas is not None

    def plot_page(self) -> QWidget:
        return self.canvas

    def clear_plot(self) -> None:
        """Drop every drawn artist so the next render starts clean."""
        self.axes.clear()
        self._annotation = None
        self._hover_points = []
        self._hover_bars = []
        self._hover_key = None
        self.canvas.draw_idle()

    def render_plot(self, spec: ChartSpec) -> None:
        self.clear_plot()
        self._apply_theme()
        self.axes.set_title(spec.title)
        self.axes.set_xlabel(spec.x_column)
        self.axes.set_ylabel(spec.y_column)
        self._x_label = spec.x_column
        self._y_label = spec.y_column

        show_legend = len(spec.series) > 1 and any(item.name for item in spec.series)
        self._show_series_names = show_legend
        if spec.chart_type == "bar":
            self._draw_bars(spec, show_legend)
        else:
            cats = None if is_numeric_x(spec.series) else categories(spec.series)
            self._draw_points(spec, cats, show_legend)
            if cats is not None:
                self._set_category_ticks(cats)
        self._annotation = self.axes.annotate(
            "",
            xy=(0.0, 0.0),
            xytext=(12, 12),
            textcoords="offset points",
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": self._background,
                "edgecolor": self._text_color,
                "alpha": 0.95,
            },
            color=self._text_color,
            fontsize=9,
            zorder=20,
            annotation_clip=False,
        )
        self._annotation.set_visible(False)
        self.canvas.draw_idle()

    # -- drawing ---------------------------------------------------------
    def dispose(self) -> None:
        """Release the canvas in its own event-loop pass.

        Used by tests before the shared widget cleanup runs, so a figure is
        never destroyed in the same batch as the windows around it.
        """
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return
        try:
            canvas.mpl_disconnect(self._hover_cid)
        except AttributeError, ValueError:
            pass
        self.canvas = None
        self._annotation = None
        try:
            canvas.hide()
            canvas.deleteLater()
        except RuntimeError:
            return
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.processEvents()

    def _apply_theme(self) -> None:
        palette = self.palette()
        self._background = palette.color(QPalette.ColorRole.Window).name()
        self._text_color = palette.color(QPalette.ColorRole.WindowText).name()

        self.figure.set_facecolor(self._background)
        self.axes.set_facecolor(self._background)
        for spine in self.axes.spines.values():
            spine.set_color(self._text_color)
        self.axes.tick_params(colors=self._text_color, labelcolor=self._text_color)
        self.axes.xaxis.label.set_color(self._text_color)
        self.axes.yaxis.label.set_color(self._text_color)
        self.axes.title.set_color(self._text_color)
        self.axes.grid(True, axis="y", color=self._text_color, alpha=0.2)

    def _draw_legend(self) -> None:
        handles, labels = self.axes.get_legend_handles_labels()
        if not labels:
            # matplotlib warns when legend() has nothing to show.
            return
        legend = self.axes.legend(handles, labels, labelcolor=self._text_color)
        frame = legend.get_frame()
        frame.set_facecolor(self._background)
        frame.set_edgecolor(self._text_color)

    def _draw_bars(self, spec: ChartSpec, show_legend: bool) -> None:
        cats = categories(spec.series)
        names = [x_name(value) for value in cats]
        positions = {value: index for index, value in enumerate(cats)}
        count = max(1, len(spec.series))
        width = 0.8 / count

        for order, series in enumerate(spec.series):
            offset = (order - (count - 1) / 2) * width
            xs: list[float] = []
            ys: list[float] = []
            labels: list[str] = []
            for value, y in zip(series.x, series.y):
                index = positions.get(value)
                if index is None:
                    continue
                xs.append(index + offset)
                ys.append(to_float(y))
                labels.append(names[index])
            if not xs:
                continue
            self.axes.bar(
                xs,
                ys,
                width=width,
                color=SERIES_COLORS[order % len(SERIES_COLORS)],
                label=series.name if show_legend else None,
            )
            for centre, height, x_text in zip(xs, ys, labels):
                self._hover_bars.append(
                    (
                        centre - width / 2,
                        width,
                        min(0.0, height),
                        abs(height),
                        x_text,
                        height,
                        series.name,
                    )
                )
        self._set_category_ticks(cats)
        if show_legend:
            self._draw_legend()

    def _draw_points(
        self,
        spec: ChartSpec,
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
            label = series.name if show_legend else None
            if spec.chart_type == "scatter":
                self.axes.scatter(xs, ys, s=36, color=color, label=label)
            else:
                # NaNs leave gaps, which is what a missing point should show.
                self.axes.plot(xs, ys, color=color, linewidth=2, label=label)
            self._hover_points.append((xs, ys, labels, series.name))
        if show_legend:
            self._draw_legend()

    def _set_category_ticks(self, cats: list[Any]) -> None:
        self.axes.set_xticks(range(len(cats)))
        self.axes.set_xticklabels(category_labels(cats))

    # -- hover -----------------------------------------------------------
    def _on_motion(self, event: Any) -> None:
        """Show the hovered value in a small annotation."""
        if self._annotation is None or event.inaxes is not self.axes:
            self._hide_hover()
            return
        x = event.xdata
        y = event.ydata
        if x is None or y is None:
            self._hide_hover()
            return

        for left, width, bottom, height, x_text, value, name in self._hover_bars:
            if left <= x <= left + width and bottom <= y <= bottom + height:
                self._show_hover(x, y, self._hover_text(x_text, value, name))
                return

        best: tuple[float, str, float, float] | None = None
        origin = np.array([event.x, event.y], dtype=float)
        for xs, ys, labels, name in self._hover_points:
            if not xs:
                continue
            points = self.axes.transData.transform(np.column_stack([xs, ys]))
            distances = ((points - origin) ** 2).sum(axis=1)
            distances[np.isnan(points).any(axis=1)] = np.inf
            index = int(np.argmin(distances))
            distance = float(distances[index])
            if distance > _HOVER_RADIUS_PX**2:
                continue
            if best is None or distance < best[0]:
                best = (
                    distance,
                    self._hover_text(labels[index], ys[index], name),
                    xs[index],
                    ys[index],
                )
        if best is None:
            self._hide_hover()
            return
        self._show_hover(best[2], best[3], best[1])

    def _hover_text(self, x_text: str, y_value: float, series_name: str) -> str:
        lines: list[str] = []
        if self._show_series_names and series_name:
            lines.append(series_name)
        lines.append(f"{self._x_label or 'X'}: {x_text}")
        lines.append(f"{self._y_label or 'Y'}: {format_value(y_value)}")
        return "\n".join(lines)

    def _show_hover(self, x: float, y: float, text: str) -> None:
        if self._annotation is None or text == self._hover_key:
            return
        self._hover_key = text
        self._annotation.xy = (x, y)
        self._annotation.set_text(text)
        self._annotation.set_visible(True)
        self.canvas.draw_idle()

    def _hide_hover(self) -> None:
        if self._annotation is not None and self._annotation.get_visible():
            self._annotation.set_visible(False)
            self.canvas.draw_idle()
        self._hover_key = None
