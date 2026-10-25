"""Shared contract for the Graph node's chart renderers.

Two independent drawing implementations subclass :class:`ChartRenderer`:
``chart_view`` (matplotlib, the default) and ``pyqtgraph_view`` (opt-in).
The base owns what neither library should do differently - the message page
vs the plot page, and the pure label logic that makes both renderers label
*the same categories* and format *the same tooltip numbers*. Drawing itself
is never shared: an abstraction across two plotting libraries ends up
carrying the lowest common denominator of both.

Everything drawn comes from a :class:`~trigger_designer.core.charts.ChartSpec`
and no plotting library is imported here, so importing this module is free.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QStackedLayout, QWidget

from trigger_designer.core.charts import ChartSeries, ChartSpec

#: Categorical series colours, in drawing order. Plain hex so either
#: library resolves them without name translation.
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
MAX_TICK_CHARS = 18

#: Most category ticks to label before thinning them out.
MAX_LABELLED_TICKS = 40


def to_float(value: Any) -> float:
    """Best-effort numeric conversion; non-numeric values become NaN."""
    try:
        return float(value)
    except TypeError, ValueError:
        return float("nan")


def format_value(value: float) -> str:
    """Compact number for a tooltip: no trailing zeros, thousands separated."""
    if math.isnan(value):
        return "\u2014"
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.6g}"


def tick_label(value: Any) -> str:
    text = "null" if value is None else str(value)
    if len(text) > MAX_TICK_CHARS:
        return text[: MAX_TICK_CHARS - 1] + "\u2026"
    return text


def x_name(value: Any) -> str:
    """Full X value for a tooltip; the axis label is the elided form."""
    return "null" if value is None else str(value)


def is_numeric_x(series: Sequence[ChartSeries]) -> bool:
    values = [value for item in series for value in item.x]
    if not values:
        return False
    try:
        for value in values:
            float(value)
    except TypeError, ValueError:
        return False
    return True


def categories(series: Sequence[ChartSeries]) -> list[Any]:
    """Distinct X values in first-seen order, across every series."""
    seen: dict[Any, None] = {}
    for item in series:
        for value in item.x:
            seen.setdefault(value, None)
    return list(seen)


def category_labels(categories: list[Any]) -> list[str]:
    """Elide every label, and blank out all but ~40 so the axis stays readable."""
    step = max(1, len(categories) // MAX_LABELLED_TICKS)
    return [
        tick_label(value) if index % step == 0 else ""
        for index, value in enumerate(categories)
    ]


class ChartRenderer(QWidget):
    """One message page and one plot page; the plot page draws a ``ChartSpec``.

    Subclasses implement the four hooks (``plot_is_live``, ``plot_page``,
    ``clear_plot``, ``render_plot``) and ``dispose()``; ``set_spec`` routes
    every spec to the message or to their drawing, exactly once per call.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._spec: ChartSpec | None = None

        self.message = QLabel(self)
        self.message.setObjectName("EmptyStateLabel")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.addWidget(self.message)

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
        if not self.plot_is_live():
            # Disposed: the window that owned this view is gone.
            return
        if spec is None or not spec.renderable:
            self.clear_plot()
            self.message.setText("No incoming data." if spec is None else spec.message)
            self._stack.setCurrentWidget(self.message)
            return
        self.render_plot(spec)
        self._stack.setCurrentWidget(self.plot_page())

    def dispose(self) -> None:
        """Release the plot widget in its own event-loop pass."""
        raise NotImplementedError

    # -- renderer hooks ----------------------------------------------------
    # Every drawing detail lives behind these; the base never asks what
    # library is on the other side.
    def plot_is_live(self) -> bool:
        """Whether the plot page still exists (False after ``dispose``)."""
        raise NotImplementedError

    def plot_page(self) -> QWidget:
        """The widget the stack shows instead of the message page."""
        raise NotImplementedError

    def clear_plot(self) -> None:
        """Drop every drawn item so the next render starts clean."""
        raise NotImplementedError

    def render_plot(self, spec: ChartSpec) -> None:
        """Draw ``spec``; leaves the plot page ready to show."""
        raise NotImplementedError
