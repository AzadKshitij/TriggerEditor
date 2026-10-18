"""matplotlib view for the Graph node's chart window.

The Config Dock configures the chart; the window draws it, and this module is
the only renderer. Everything drawn comes from a
:class:`~trigger_designer.core.charts.ChartSpec`, so no frame, setting or node
state crosses this boundary.

``nodes/__init__`` keeps this module and ``chart_window`` out of its startup
import sweep, so matplotlib loads the first time a chart window actually opens
rather than on every launch.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from qtpy.QtCore import QCoreApplication, QEvent, Qt
from qtpy.QtGui import QPalette
from qtpy.QtWidgets import QApplication, QLabel, QStackedLayout, QWidget

from trigger_designer.core.charts import ChartSeries, ChartSpec

#: Categorical series colours, in drawing order.
SERIES_COLORS: tuple[str, ...] = (
    "#4c9aff",
    "#f2994a",
    "#27ae60",
    "#eb5757",
    "#9b51e0",
    "#2d9cdb",
    "#f2c94c",
    "#6fcf97",
)

#: Longest category label drawn on the axis before it is elided.
_MAX_TICK_CHARS = 18

#: Most category ticks to label before thinning them out.
_MAX_LABELLED_TICKS = 40

#: Cursor distance, in pixels, at which a point or bar counts as hovered.
_HOVER_RADIUS_PX = 12


def _to_float(value: Any) -> float:
    """Best-effort numeric conversion; non-numeric values become NaN."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _format_value(value: float) -> str:
    """Compact number for a tooltip: no trailing zeros, thousands separated."""
    if math.isnan(value):
        return "\u2014"
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.6g}"


def _tick_label(value: Any) -> str:
    text = "null" if value is None else str(value)
    if len(text) > _MAX_TICK_CHARS:
        return text[: _MAX_TICK_CHARS - 1] + "\u2026"
    return text


def _x_name(value: Any) -> str:
    """Full X value for a tooltip; the axis label is the elided form."""
    return "null" if value is None else str(value)


def _is_numeric_x(series: Sequence[ChartSeries]) -> bool:
    values = [value for item in series for value in item.x]
    if not values:
        return False
    try:
        for value in values:
            float(value)
    except (TypeError, ValueError):
        return False
    return True


def _categories(series: Sequence[ChartSeries]) -> list[Any]:
    """Distinct X values in first-seen order, across every series."""
    seen: dict[Any, None] = {}
    for item in series:
        for value in item.x:
            seen.setdefault(value, None)
    return list(seen)


def _category_labels(categories: list[Any]) -> list[str]:
    """Elide every label, and blank out all but ~40 so the axis stays readable."""
    step = max(1, len(categories) // _MAX_LABELLED_TICKS)
    return [
        _tick_label(value) if index % step == 0 else ""
        for index, value in enumerate(categories)
    ]


class ChartView(QWidget):
    """Draws a ``ChartSpec``; an empty or invalid spec draws its message."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._spec: ChartSpec | None = None
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

        self.message = QLabel(self)
        self.message.setObjectName("EmptyStateLabel")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)

        self.figure = Figure(layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.axes = self.figure.add_subplot(111)

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.addWidget(self.message)
        self._stack.addWidget(self.canvas)

        self._hover_cid = self.canvas.mpl_connect(
            "motion_notify_event", self._on_motion
        )
        self.set_spec(None)

    @property
    def spec(self) -> ChartSpec | None:
        """The spec currently drawn."""
        return self._spec

    @property
    def showing_message(self) -> bool:
        """Whether the message page is up instead of the plot."""
        return self._stack.currentWidget() is self.message

    def set_spec(self, spec: ChartSpec | None) -> None:
        self._spec = spec
        if self.canvas is None:
            # Disposed: the window that owned this view is gone.
            return
        if spec is None or not spec.renderable:
            self._reset()
            self.message.setText(
                spec.message if spec is not None else "No incoming data."
            )
            self._stack.setCurrentWidget(self.message)
            return
        self._render(spec)
        self._stack.setCurrentWidget(self.canvas)

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
        except (AttributeError, ValueError):
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

    def _reset(self) -> None:
        """Drop every drawn artist so the next render starts clean."""
        self.axes.clear()
        self._annotation = None
        self._hover_points = []
        self._hover_bars = []
        self._hover_key = None
        self.canvas.draw_idle()

    def _render(self, spec: ChartSpec) -> None:
        self._reset()
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
            categories = (
                None if _is_numeric_x(spec.series) else _categories(spec.series)
            )
            self._draw_points(spec, categories, show_legend)
            if categories is not None:
                self._set_category_ticks(categories)
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
        categories = _categories(spec.series)
        names = [_x_name(value) for value in categories]
        positions = {value: index for index, value in enumerate(categories)}
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
                ys.append(_to_float(y))
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
        self._set_category_ticks(categories)
        if show_legend:
            self._draw_legend()

    def _draw_points(
        self,
        spec: ChartSpec,
        categories: list[Any] | None,
        show_legend: bool,
    ) -> None:
        positions = (
            {value: index for index, value in enumerate(categories)}
            if categories is not None
            else None
        )
        for order, series in enumerate(spec.series):
            color = SERIES_COLORS[order % len(SERIES_COLORS)]
            if positions is None:
                xs = [_to_float(value) for value in series.x]
                labels = [_format_value(value) for value in xs]
            else:
                xs = [float(positions[value]) for value in series.x]
                labels = [_x_name(value) for value in series.x]
            ys = [_to_float(value) for value in series.y]
            label = series.name if show_legend else None
            if spec.chart_type == "scatter":
                self.axes.scatter(xs, ys, s=36, color=color, label=label)
            else:
                # NaNs leave gaps, which is what a missing point should show.
                self.axes.plot(xs, ys, color=color, linewidth=2, label=label)
            self._hover_points.append((xs, ys, labels, series.name))
        if show_legend:
            self._draw_legend()

    def _set_category_ticks(self, categories: list[Any]) -> None:
        self.axes.set_xticks(range(len(categories)))
        self.axes.set_xticklabels(_category_labels(categories))

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
        lines.append(f"{self._y_label or 'Y'}: {_format_value(y_value)}")
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
