#!/usr/bin/env python3
"""The pyqtgraph renderer the Graph window can show.

Mirrors ``tests/ui/test_chart_view.py`` question for question: the view
consumes a ``ChartSpec``, never a frame or a setting, and the tests here pin
what lands in the plot - curves, spots, bars, ticks, legend and the message
page. Hover is driven through ``_on_hover`` with stub spots because the real
signal comes from scene mouse events the offscreen platform never delivers;
the stub protocol (``pos()``/``data()``) is exactly what pyqtgraph's own
``SpotItem`` implements.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pyqtgraph as pg
import pytest
from qtpy.QtCore import QPointF
from qtpy.QtGui import QPalette
from qtpy.QtWidgets import QApplication

from trigger_designer.core.charts import ChartSeries, ChartSpec
from trigger_designer.qt.widgets.nodes.Report.pyqtgraph_view import PyqtgraphChartView

APP = QApplication.instance() or QApplication([])

#: Views built by this module, so teardown can release each plot in turn.
_VIEWS: list = []


@pytest.fixture(autouse=True)
def _dispose_views():
    """Release each plot before the shared leak fixture batches widgets."""
    yield
    while _VIEWS:
        _VIEWS.pop().dispose()


def _spec(**overrides) -> ChartSpec:
    base = {
        "chart_type": "line",
        "x_column": "x",
        "y_column": "y",
        "title": "Chart",
        "series": (ChartSeries(name="y", x=(1.0, 2.0, 3.0), y=(4.0, 5.0, 6.0)),),
        "point_count": 3,
    }
    base.update(overrides)
    return ChartSpec(**base)


def _view(spec=None) -> PyqtgraphChartView:
    view = PyqtgraphChartView()
    view.set_spec(spec)
    _VIEWS.append(view)
    return view


def _plot_item(view):
    return view.plot.getPlotItem()


def _legend_labels(view):
    return [label.text for _sample, label in view._legend.items]


def _tick_labels(view):
    """The labelled category ticks, ``(position, label)`` pairs."""
    levels = _plot_item(view).getAxis("bottom")._tickLevels
    return [] if levels is None else levels[0]


class _Spot:
    """The slice of a pyqtgraph ``SpotItem`` the hover handler reads."""

    def __init__(self, data, x: float = 0.0, y: float = 0.0) -> None:
        self._data = data
        self._pos = QPointF(x, y)

    def pos(self) -> QPointF:
        return self._pos

    def data(self):
        return self._data


def test_starts_on_the_message_page() -> None:
    view = _view()

    assert view.spec is None
    assert view.showing_message is True
    assert view.message.text() == "No incoming data."
    assert view.message.objectName() == "EmptyStateLabel"


def test_line_draws_one_curve_with_the_specs_points() -> None:
    spec = _spec()
    view = _view(spec)

    assert view.spec is spec
    assert view.showing_message is False
    assert len(view._series_items) == 1
    curve = view._series_items[0]
    assert isinstance(curve, pg.PlotCurveItem)
    xs, ys = curve.getData()
    assert [float(v) for v in xs] == [1.0, 2.0, 3.0]
    assert [float(v) for v in ys] == [4.0, 5.0, 6.0]


def test_title_and_axis_labels_come_from_the_spec() -> None:
    view = _view(_spec(x_column="amount", y_column="spend", title="Spend"))
    plot_item = _plot_item(view)

    assert plot_item.titleLabel.text == "Spend"
    assert plot_item.getAxis("bottom").labelText == "amount"
    assert plot_item.getAxis("left").labelText == "spend"


def test_scatter_draws_points_instead_of_a_line() -> None:
    view = _view(_spec(chart_type="scatter"))

    assert [i for i in _plot_item(view).items if isinstance(i, pg.PlotCurveItem)] == []
    (scatter,) = view._series_items
    assert isinstance(scatter, pg.ScatterPlotItem)
    assert [float(v) for v in scatter.data["x"]] == [1.0, 2.0, 3.0]
    assert [float(v) for v in scatter.data["y"]] == [4.0, 5.0, 6.0]


def test_scatter_drops_non_finite_points() -> None:
    # A missing value hovers as nothing, exactly as matplotlib hides it.
    view = _view(
        _spec(
            chart_type="scatter",
            series=(ChartSeries(name="y", x=(1.0, 2.0), y=(3.0, None)),),
        )
    )

    (scatter,) = view._series_items
    assert [float(v) for v in scatter.data["x"]] == [1.0]


def test_line_nan_stays_in_the_data_the_curve_splits_on() -> None:
    view = _view(
        _spec(series=(ChartSeries(name="y", x=(1.0, 2.0, 3.0), y=(4.0, None, 6.0)),))
    )

    (_curve,) = view._series_items
    ys = _curve.getData()[1]
    assert ys[1] != ys[1]  # NaN, not silently bridged by dropping
    assert _curve.opts["connect"] == "finite"


def test_categorical_x_is_positioned_by_index_with_labelled_ticks() -> None:
    spec = _spec(series=(ChartSeries(name="y", x=("beta", "alpha"), y=(1.0, 2.0)),))
    view = _view(spec)

    xs = [float(v) for v in view._series_items[0].getData()[0]]
    assert xs == [0.0, 1.0]
    assert _tick_labels(view) == [(0.0, "beta"), (1.0, "alpha")]


def test_numeric_x_keeps_its_values() -> None:
    view = _view(_spec())

    xs = [float(v) for v in view._series_items[0].getData()[0]]
    assert xs == [1.0, 2.0, 3.0]
    assert _tick_labels(view) == []


def test_bar_draws_grouped_bars_and_a_legend_per_series() -> None:
    spec = _spec(
        chart_type="bar",
        color_column="g",
        series=(
            ChartSeries(name="g: x", x=("a", "b"), y=(1.0, 2.0)),
            ChartSeries(name="g: y", x=("a", "b"), y=(3.0, 4.0)),
        ),
        point_count=4,
    )
    view = _view(spec)

    assert len(view._series_items) == 2
    first, second = view._series_items
    assert isinstance(first, pg.BarGraphItem)
    # Grouped: each series sits on one side of its category tick.
    assert [round(float(v), 2) for v in first.opts["x"]] == [-0.2, 0.8]
    assert [round(float(v), 2) for v in second.opts["x"]] == [0.2, 1.2]
    assert [float(v) for v in first.opts["height"]] == [1.0, 2.0]
    assert _legend_labels(view) == ["g: x", "g: y"]
    assert _tick_labels(view) == [(0.0, "a"), (1.0, "b")]


def test_colored_line_draws_one_named_curve_per_series() -> None:
    spec = _spec(
        color_column="g",
        series=(
            ChartSeries(name="g: x", x=(1.0, 2.0), y=(1.0, 2.0)),
            ChartSeries(name="g: y", x=(1.0, 2.0), y=(2.0, 1.0)),
        ),
        point_count=4,
    )
    view = _view(spec)

    assert len(view._series_items) == 2
    assert all(isinstance(i, pg.PlotCurveItem) for i in view._series_items)
    assert _legend_labels(view) == ["g: x", "g: y"]


def test_single_series_hides_the_legend() -> None:
    view = _view(_spec())

    assert view._legend.isVisible() is False
    assert _legend_labels(view) == []


def test_message_spec_shows_the_message_and_clears_the_plot() -> None:
    view = _view(_spec())
    assert view._series_items

    view.set_spec(
        ChartSpec(
            chart_type="bar",
            x_column="x",
            y_column="y",
            message="Pick two different columns.",
        )
    )
    view.set_spec(None)

    assert view.showing_message is True
    assert view.message.text() == "No incoming data."
    assert view._series_items == []
    assert _plot_item(view).items == []
    assert _tick_labels(view) == []


def test_rerender_replaces_the_previous_chart() -> None:
    view = _view(
        _spec(
            chart_type="bar",
            series=(ChartSeries(name="", x=("a",), y=(1.0,)),),
            point_count=1,
        )
    )
    assert len(view._series_items) == 1

    view.set_spec(_spec())

    assert isinstance(view._series_items[0], pg.PlotCurveItem)
    assert [i for i in _plot_item(view).items if isinstance(i, pg.BarGraphItem)] == []


def test_a_message_spec_replaces_a_chart() -> None:
    view = _view(_spec())

    view.set_spec(
        ChartSpec(
            chart_type="bar",
            x_column="x",
            y_column="y",
            message="Pick two different columns.",
        )
    )

    assert view.showing_message is True
    assert view.message.text() == "Pick two different columns."
    assert view._series_items == []
    assert _legend_labels(view) == []


def test_long_category_labels_are_elided() -> None:
    long = "a category name far too long for the axis"
    spec = _spec(series=(ChartSeries(name="y", x=(long,), y=(1.0,)),), point_count=1)

    view = _view(spec)

    ((_pos, label),) = _tick_labels(view)
    assert label.endswith("\u2026")
    assert len(label) <= 18


def test_hover_overlay_carries_the_tooltip_payload() -> None:
    view = _view(_spec())

    overlays = [i for i in _plot_item(view).items if isinstance(i, pg.ScatterPlotItem)]
    assert len(overlays) == 1  # the invisible hover proxy, not a chart item
    payloads = [tuple(row) for row in overlays[0].data["data"]]
    assert payloads == [("1", 4.0, "y"), ("2", 5.0, "y"), ("3", 6.0, "y")]


def test_hover_shows_the_point_value() -> None:
    view = _view(_spec(x_column="amount", y_column="spend"))

    view._on_hover(None, [_Spot(("2", 5.0, "y"))], None)

    assert view._tooltip.isVisible() is True
    assert view._tooltip.toPlainText() == "amount: 2\nspend: 5"


def test_hover_shows_the_series_name_with_several_series() -> None:
    spec = _spec(
        color_column="g",
        series=(
            ChartSeries(name="g: x", x=(1.0, 2.0), y=(1.0, 2.0)),
            ChartSeries(name="g: y", x=(1.0, 2.0), y=(2.0, 1.0)),
        ),
        point_count=4,
    )
    view = _view(spec)

    view._on_hover(None, [_Spot(("1", 1.0, "g: x"))], None)

    assert view._tooltip.toPlainText() == "g: x\nx: 1\ny: 1"


def test_hover_shows_a_bars_category_and_value() -> None:
    spec = _spec(
        chart_type="bar",
        x_column="region",
        y_column="orders",
        series=(ChartSeries(name="orders", x=("north", "south"), y=(3.0, 4.0)),),
        point_count=2,
    )
    view = _view(spec)

    view._on_hover(None, [_Spot(("south", 4.0, "orders"))], None)

    assert view._tooltip.isVisible() is True
    assert view._tooltip.toPlainText() == "region: south\norders: 4"


def test_hover_hides_when_no_point_is_under_the_cursor() -> None:
    view = _view(_spec())
    view._on_hover(None, [_Spot(("2", 5.0, "y"))], None)
    assert view._tooltip.isVisible() is True

    view._on_hover(None, [], None)

    assert view._tooltip.isVisible() is False


def test_hover_tooltip_is_rebuilt_with_each_chart() -> None:
    view = _view(_spec())
    first = view._tooltip

    view.set_spec(
        _spec(series=(ChartSeries(name="y", x=("a",), y=(1.0,)),), point_count=1)
    )

    assert view._tooltip is not first
    assert view._tooltip.isVisible() is False


def test_theme_uses_palette_colors() -> None:
    view = _view(_spec())
    plot_item = _plot_item(view)
    window = view.palette().color(QPalette.ColorRole.Window).name()
    text = view.palette().color(QPalette.ColorRole.WindowText).name()

    assert plot_item.getViewBox().state["background"].name() == window
    assert plot_item.getAxis("bottom")._pen.color().name() == text
    assert plot_item.getAxis("bottom")._textPen.color().name() == text
    assert plot_item.titleLabel.opts["color"] == text


def test_disposed_view_absorbs_specs_without_drawing() -> None:
    view = _view(_spec())
    view.dispose()

    view.set_spec(_spec())

    assert view.plot_is_live() is False
    assert view.spec is not None
