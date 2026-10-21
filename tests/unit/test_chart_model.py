#!/usr/bin/env python3
"""Chart semantics for the Graph node, with no Qt in the way.

The old Graph passed whatever the user selected straight to matplotlib, so a
bar chart of a duplicated X column drew several bars where the user meant
one. :func:`build_chart_spec` owns that meaning now; these tests pin it: bar
aggregates duplicate X by default, line and scatter keep every row, and
anything undrawable comes back as a message instead of a traceback.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
import pytest

from trigger_designer.core.charts import (
    build_chart_spec,
    effective_aggregation,
    status_text,
)


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "city": ["B", "A", "B", "A", "B"],
            "amount": [10.0, 1.0, 5.0, 2.0, 7.0],
            "team": ["x", "x", "y", "y", "x"],
        }
    )


@pytest.mark.parametrize(
    ("chart_type", "stored", "expected"),
    [
        ("bar", "", "sum"),
        ("line", "", "none"),
        ("scatter", "", "none"),
        ("bar", "mean", "mean"),
        ("line", "count", "count"),
        ("bar", "garbage", "sum"),
        ("nonsense", "", "none"),
    ],
)
def test_effective_aggregation_follows_the_chart_type(
    chart_type: str, stored: str, expected: str
) -> None:
    assert effective_aggregation(chart_type, stored) == expected


def test_bar_sums_duplicate_x() -> None:
    spec = build_chart_spec(
        _frame(), chart_type="bar", x_column="city", y_column="amount"
    )

    assert spec.aggregation == "sum"
    assert spec.renderable
    assert spec.point_count == 2
    (series,) = spec.series
    assert series.x == ("A", "B")
    assert series.y == (3.0, 22.0)


def test_line_keeps_every_row_and_sorts_by_x() -> None:
    spec = build_chart_spec(
        _frame(), chart_type="line", x_column="city", y_column="amount"
    )

    assert spec.aggregation == "none"
    assert spec.point_count == 5
    (series,) = spec.series
    assert series.x == ("A", "A", "B", "B", "B")


def test_scatter_keeps_the_row_order() -> None:
    spec = build_chart_spec(
        _frame(), chart_type="scatter", x_column="city", y_column="amount"
    )

    (series,) = spec.series
    assert series.x == ("B", "A", "B", "A", "B")


@pytest.mark.parametrize(
    ("aggregation", "expected_a", "expected_b"),
    [
        ("count", 2.0, 3.0),
        ("sum", 3.0, 22.0),
        ("mean", 1.5, 22 / 3),
        ("median", 1.5, 7.0),
        ("min", 1.0, 5.0),
        ("max", 2.0, 10.0),
    ],
)
def test_explicit_aggregations_group_by_x(
    aggregation: str, expected_a: float, expected_b: float
) -> None:
    spec = build_chart_spec(
        _frame(),
        chart_type="bar",
        x_column="city",
        y_column="amount",
        aggregation=aggregation,
    )

    assert spec.aggregation == aggregation
    (series,) = spec.series
    assert series.x == ("A", "B")
    assert series.y == pytest.approx((expected_a, expected_b))


def test_count_accepts_a_non_numeric_y() -> None:
    spec = build_chart_spec(
        _frame(),
        chart_type="bar",
        x_column="city",
        y_column="team",
        aggregation="count",
    )

    assert spec.renderable
    (series,) = spec.series
    assert series.y == (2.0, 3.0)


def test_numeric_aggregation_rejects_a_non_numeric_y() -> None:
    spec = build_chart_spec(
        _frame(), chart_type="bar", x_column="city", y_column="team"
    )

    assert spec.message == "Y column 'team' must be numeric for sum."
    assert not spec.renderable


def test_unaggregated_line_leaves_a_non_numeric_y_alone() -> None:
    spec = build_chart_spec(
        _frame(), chart_type="line", x_column="city", y_column="team"
    )

    assert spec.renderable
    (series,) = spec.series
    # Line charts sort by X, so the row order is not the drawn order.
    assert series.y == ("x", "y", "x", "y", "x")


def test_missing_columns_are_messages_not_exceptions() -> None:
    x_missing = build_chart_spec(
        _frame(), chart_type="bar", x_column="nope", y_column="amount"
    )
    assert x_missing.message == "X column 'nope' is not in the incoming data."
    assert not x_missing.renderable

    y_missing = build_chart_spec(
        _frame(), chart_type="bar", x_column="city", y_column="nope"
    )
    assert y_missing.message == "Y column 'nope' is not in the incoming data."


def test_unset_columns_ask_for_a_choice() -> None:
    assert (
        build_chart_spec(
            _frame(), chart_type="bar", x_column="", y_column="amount"
        ).message
        == "Select an X column."
    )
    assert (
        build_chart_spec(
            _frame(), chart_type="bar", x_column="city", y_column=""
        ).message
        == "Select a Y column."
    )


def test_nothing_to_chart_is_a_message() -> None:
    assert (
        build_chart_spec(None, x_column="city", y_column="amount").message
        == "No incoming data."
    )
    assert (
        build_chart_spec("not a table", x_column="city", y_column="amount").message
        == "Graph needs a table input."
    )
    empty = pl.DataFrame(
        schema={"city": pl.String, "amount": pl.Float64},
    )
    assert (
        build_chart_spec(
            empty, chart_type="bar", x_column="city", y_column="amount"
        ).message
        == "No rows to plot."
    )


def test_lazy_and_eager_frames_build_the_same_spec() -> None:
    frame = _frame()
    eager = build_chart_spec(
        frame,
        chart_type="bar",
        x_column="city",
        y_column="amount",
        title="Spend",
    )
    lazy = build_chart_spec(
        frame.lazy(),
        chart_type="bar",
        x_column="city",
        y_column="amount",
        title="Spend",
    )

    assert eager == lazy
    assert eager.title == "Spend"


def test_color_column_splits_the_aggregation_per_series() -> None:
    spec = build_chart_spec(
        _frame(),
        chart_type="bar",
        x_column="city",
        y_column="amount",
        color_column="team",
    )

    assert spec.renderable
    assert spec.point_count == 4
    assert [series.name for series in spec.series] == ["team: x", "team: y"]
    x_series, y_series = spec.series
    assert x_series.x == ("A", "B")
    assert x_series.y == (1.0, 17.0)
    assert y_series.y == (2.0, 5.0)
    assert spec.color_column == "team"


def test_color_column_must_differ_from_the_axes() -> None:
    spec = build_chart_spec(
        _frame(),
        chart_type="bar",
        x_column="city",
        y_column="amount",
        color_column="city",
    )

    assert spec.message == "Color by must differ from X and Y."


def test_x_and_y_must_differ_to_aggregate() -> None:
    spec = build_chart_spec(
        _frame(), chart_type="bar", x_column="amount", y_column="amount"
    )

    assert spec.message == "X and Y must differ to aggregate."


def test_max_points_bounds_the_drawn_points() -> None:
    frame = pl.DataFrame({"x": list(range(50)), "y": list(range(50))})

    line = build_chart_spec(
        frame, chart_type="line", x_column="x", y_column="y", max_points=10
    )
    assert line.truncated is True
    assert line.point_count == 10

    bars = build_chart_spec(
        frame, chart_type="bar", x_column="x", y_column="y", max_points=10
    )
    assert bars.truncated is True
    assert bars.point_count == 10


def test_status_text_names_what_the_chart_shows() -> None:
    spec = build_chart_spec(
        _frame(),
        chart_type="bar",
        x_column="city",
        y_column="amount",
        color_column="team",
    )

    text = status_text(spec)
    assert "4 points" in text
    assert "sum of amount per city" in text
    assert "colored by team" in text

    assert status_text(None) == "No incoming data."

    broken = build_chart_spec(
        _frame(), chart_type="bar", x_column="nope", y_column="amount"
    )
    assert status_text(broken) == broken.message
