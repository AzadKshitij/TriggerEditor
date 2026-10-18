#!/usr/bin/env python3
"""The matplotlib renderer the Graph window shows.

The view consumes a ``ChartSpec``, never a frame or a setting: the model is
tested in ``tests/unit/test_chart_model.py`` and the dock in
``tests/ui/test_graph_dock.py``. The question here is what actually lands in
the axes - lines, bars, ticks, legend and the message page.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest
from qtpy.QtWidgets import QApplication

from trigger_designer.core.charts import ChartSeries, ChartSpec
from trigger_designer.qt.widgets.nodes.Report.chart_view import ChartView

APP = QApplication.instance() or QApplication([])

#: Views built by this module, so teardown can release each canvas in turn.
_VIEWS: list = []


@pytest.fixture(autouse=True)
def _dispose_views():
    """Release each canvas before the shared leak fixture batches widgets."""
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


def _view(spec=None) -> ChartView:
    view = ChartView()
    view.set_spec(spec)
    _VIEWS.append(view)
    return view


def _legend_labels(view):
    legend = view.axes.get_legend()
    return [] if legend is None else [text.get_text() for text in legend.get_texts()]


def _tick_labels(view):
    return [label.get_text() for label in view.axes.get_xticklabels()]


def test_starts_on_the_message_page() -> None:
    view = _view()

    assert view.spec is None
    assert view.showing_message is True
    assert view.message.text() == "No incoming data."


def test_line_draws_one_curve_with_the_specs_points() -> None:
    spec = _spec()
    view = _view(spec)

    assert view.spec is spec
    assert view.showing_message is False
    assert len(view.axes.lines) == 1
    line = view.axes.lines[0]
    assert list(line.get_xdata()) == [1.0, 2.0, 3.0]
    assert list(line.get_ydata()) == [4.0, 5.0, 6.0]


def test_title_and_axis_labels_come_from_the_spec() -> None:
    view = _view(_spec(x_column="amount", y_column="spend", title="Spend"))

    assert view.axes.get_title() == "Spend"
    assert view.axes.get_xlabel() == "amount"
    assert view.axes.get_ylabel() == "spend"


def test_scatter_draws_points_instead_of_a_line() -> None:
    view = _view(_spec(chart_type="scatter"))

    assert len(view.axes.lines) == 0
    assert len(view.axes.collections) == 1
    offsets = [
        tuple(float(v) for v in point)
        for point in view.axes.collections[0].get_offsets()
    ]
    assert offsets == [(1.0, 4.0), (2.0, 5.0), (3.0, 6.0)]


def test_categorical_x_is_positioned_by_index_with_labelled_ticks() -> None:
    spec = _spec(series=(ChartSeries(name="y", x=("beta", "alpha"), y=(1.0, 2.0)),))
    view = _view(spec)

    line = view.axes.lines[0]
    assert list(line.get_xdata()) == [0.0, 1.0]
    assert _tick_labels(view) == ["beta", "alpha"]


def test_numeric_x_keeps_its_values() -> None:
    view = _view(_spec())

    assert list(view.axes.lines[0].get_xdata()) == [1.0, 2.0, 3.0]


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

    assert len(view.axes.patches) == 4
    centres = [patch.get_x() + patch.get_width() / 2 for patch in view.axes.patches]
    # Grouped: each series sits on one side of its category tick.
    assert centres[0] < 0.0 < centres[2]
    assert centres[1] < 1.0 < centres[3]
    assert [patch.get_height() for patch in view.axes.patches] == [1.0, 2.0, 3.0, 4.0]
    assert _legend_labels(view) == ["g: x", "g: y"]
    assert _tick_labels(view) == ["a", "b"]


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

    assert len(view.axes.lines) == 2
    assert _legend_labels(view) == ["g: x", "g: y"]


def test_single_series_hides_the_legend() -> None:
    view = _view(_spec())

    assert _legend_labels(view) == []
    assert view.axes.get_legend() is None


def test_message_spec_shows_the_message_and_clears_the_plot() -> None:
    view = _view(_spec())
    assert view.axes.lines

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
    assert len(view.axes.lines) == 0
    assert len(view.axes.patches) == 0


def test_rerender_replaces_the_previous_chart() -> None:
    view = _view(
        _spec(
            chart_type="bar",
            series=(ChartSeries(name="", x=("a",), y=(1.0,)),),
            point_count=1,
        )
    )
    assert len(view.axes.patches) == 1

    view.set_spec(_spec())

    assert len(view.axes.patches) == 0
    assert len(view.axes.lines) == 1


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
    assert len(view.axes.lines) == 0
    assert _legend_labels(view) == []


def test_long_category_labels_are_elided() -> None:
    long = "a category name far too long for the axis"
    spec = _spec(series=(ChartSeries(name="y", x=(long,), y=(1.0,)),), point_count=1)

    view = _view(spec)

    (label,) = _tick_labels(view)
    assert label.endswith("\u2026")
    assert len(label) <= 18


class _MotionEvent:
    """The slice of a matplotlib MouseEvent the hover handler reads."""

    def __init__(self, view: ChartView, xdata: float, ydata: float) -> None:
        self.xdata = xdata
        self.ydata = ydata
        self.inaxes = view.axes
        px, py = view.axes.transData.transform([[xdata, ydata]])[0]
        self.x = float(px)
        self.y = float(py)


def test_hover_shows_the_point_value() -> None:
    view = _view(_spec(x_column="amount", y_column="spend"))
    view.canvas.draw()

    view._on_motion(_MotionEvent(view, 2.0, 5.0))

    assert view._annotation.get_visible() is True
    assert view._annotation.get_text() == "amount: 2\nspend: 5"


def test_hover_snaps_to_the_nearest_point() -> None:
    view = _view(_spec())
    view.canvas.draw()

    event = _MotionEvent(view, 2.0, 5.0)
    event.x += 4
    event.y += 3
    view._on_motion(event)

    assert view._annotation.get_text() == "x: 2\ny: 5"


def test_hover_shows_a_bars_category_and_value() -> None:
    spec = _spec(
        chart_type="bar",
        x_column="region",
        y_column="orders",
        series=(ChartSeries(name="orders", x=("north", "south"), y=(3.0, 4.0)),),
        point_count=2,
    )
    view = _view(spec)
    view.canvas.draw()

    view._on_motion(_MotionEvent(view, 1.0, 2.0))

    assert view._annotation.get_visible() is True
    assert view._annotation.get_text() == "region: south\norders: 4"


def test_hover_hides_when_the_cursor_leaves_the_axes() -> None:
    view = _view(_spec())
    view.canvas.draw()
    view._on_motion(_MotionEvent(view, 1.0, 4.0))
    assert view._annotation.get_visible() is True

    event = _MotionEvent(view, 1.0, 4.0)
    event.inaxes = None
    view._on_motion(event)

    assert view._annotation.get_visible() is False


def test_hover_annotation_is_rebuilt_with_each_chart() -> None:
    view = _view(_spec())
    first = view._annotation

    view.set_spec(
        _spec(series=(ChartSeries(name="y", x=("a",), y=(1.0,)),), point_count=1)
    )

    assert view._annotation is not first
    assert view._annotation.get_visible() is False


def test_legend_without_labelled_artists_is_skipped() -> None:
    # matplotlib warns (and draws an empty box) when legend() has nothing to
    # show; the view skips it instead.
    view = _view(_spec())

    view._draw_legend()

    assert view.axes.get_legend() is None
