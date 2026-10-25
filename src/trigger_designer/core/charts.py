"""Pure chart model for the Graph node.

No Qt and no plotting library live here: the chart window and the unit tests
both build the same :class:`ChartSpec` from a Polars frame, so what the tests
assert is what the user sees.

Semantics
---------
* ``line`` and ``scatter`` plot one point per row by default.
* ``bar`` aggregates duplicate X values with ``sum`` by default: a bar of the
  same X drawn twice is rarely what the user meant.
* Every chart type can override the aggregation explicitly (count, mean,
  median, min, max, or none).

Ordering and size
-----------------
Charts are meant to be looked at, not to load a whole file into memory:
``max_points`` bounds the points handed to the renderer. Aggregation runs
before the bound, so a bar chart sums the whole frame and only the number of
*distinct* X groups is capped.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import polars as pl

#: Chart kinds the Graph node offers.
CHART_TYPES: tuple[str, ...] = ("line", "bar", "scatter")

#: Aggregations the user can pick. Empty means "the chart type's default".
AGGREGATIONS: tuple[str, ...] = (
    "none",
    "sum",
    "count",
    "mean",
    "median",
    "min",
    "max",
)

#: Aggregation applied when the model does not name one.
DEFAULT_AGGREGATION: dict[str, str] = {
    "line": "none",
    "bar": "sum",
    "scatter": "none",
}

#: Upper bound on the points handed to a renderer.
MAX_CHART_POINTS = 2000


@dataclass(frozen=True)
class ChartSeries:
    """One drawn series: a name and parallel X/Y values."""

    name: str
    x: tuple[Any, ...] = ()
    y: tuple[Any, ...] = ()


@dataclass(frozen=True)
class ChartSpec:
    """Everything a renderer needs, with no reference to the source frame."""

    chart_type: str = "line"
    x_column: str = ""
    y_column: str = ""
    color_column: str = ""
    aggregation: str = "none"
    title: str = ""
    series: tuple[ChartSeries, ...] = ()
    point_count: int = 0
    truncated: bool = False
    message: str = ""
    columns: tuple[str, ...] = field(default=(), repr=False)

    @property
    def renderable(self) -> bool:
        """Whether a renderer has points to draw."""
        return not self.message and self.point_count > 0 and bool(self.series)


def normalize_chart_type(value: Any) -> str:
    """Return a known chart type; unknown or empty values become ``line``."""
    text = str(value or "").strip().lower()
    return text if text in CHART_TYPES else "line"


def effective_aggregation(chart_type: Any, value: Any = "") -> str:
    """Resolve the aggregation a chart should use.

    An explicit, known value wins. Empty or unknown values fall back to the
    chart type's default (``sum`` for bars, ``none`` for line and scatter).
    """
    chart_type = normalize_chart_type(chart_type)
    text = str(value or "").strip().lower()
    if text in AGGREGATIONS:
        return text
    return DEFAULT_AGGREGATION[chart_type]


def status_text(spec: ChartSpec | None) -> str:
    """One-line summary of what the chart shows, for the dock status label."""
    if spec is None:
        return "No incoming data."
    if spec.message:
        return spec.message
    if not spec.renderable:
        return "No data to plot."
    points = f"{spec.point_count:,} point" + ("" if spec.point_count == 1 else "s")
    if spec.truncated:
        points += " shown (truncated)"
    parts = [points]
    if spec.aggregation != "none":
        parts.append(f"{spec.aggregation} of {spec.y_column} per {spec.x_column}")
    if spec.color_column:
        parts.append(f"colored by {spec.color_column}")
    return " · ".join(parts)


def build_chart_spec(
    data: Any,
    *,
    chart_type: Any = "line",
    x_column: Any = "",
    y_column: Any = "",
    color_column: Any = "",
    aggregation: Any = "",
    title: Any = "",
    max_points: int = MAX_CHART_POINTS,
) -> ChartSpec:
    """Turn a frame and the Graph node's settings into a render-ready spec.

    Never raises for ordinary bad input (missing columns, non-numeric Y, an
    empty frame): the returned spec carries a human-readable ``message`` and
    ``renderable`` stays ``False``, so the UI can show why nothing is drawn.
    """
    chart_type = normalize_chart_type(chart_type)
    aggregation = effective_aggregation(chart_type, aggregation)
    x_column = str(x_column or "")
    y_column = str(y_column or "")
    color_column = str(color_column or "")
    title = str(title or "")

    def make(
        message: str = "",
        series: Sequence[ChartSeries] = (),
        point_count: int = 0,
        truncated: bool = False,
        columns: Sequence[str] = (),
    ) -> ChartSpec:
        return ChartSpec(
            chart_type=chart_type,
            x_column=x_column,
            y_column=y_column,
            color_column=color_column,
            aggregation=aggregation,
            title=title,
            series=tuple(series),
            point_count=point_count,
            truncated=truncated,
            message=message,
            columns=tuple(columns),
        )

    if data is None:
        return make("No incoming data.")

    try:
        frame = _coerce_frame(data)
        if frame is None:
            return make("Graph needs a table input.")
        columns = _schema_names(frame)

        if not x_column:
            return make("Select an X column.", columns=columns)
        if not y_column:
            return make("Select a Y column.", columns=columns)
        if x_column not in columns:
            return make(
                f"X column '{x_column}' is not in the incoming data.",
                columns=columns,
            )
        if y_column not in columns:
            return make(
                f"Y column '{y_column}' is not in the incoming data.",
                columns=columns,
            )
        if color_column and color_column not in columns:
            color_column = ""

        if aggregation != "none":
            if x_column == y_column:
                return make("X and Y must differ to aggregate.", columns=columns)
            if color_column and color_column in (x_column, y_column):
                return make("Color by must differ from X and Y.", columns=columns)
            if aggregation != "count" and not _numeric_column(frame, y_column):
                return make(
                    f"Y column '{y_column}' must be numeric for {aggregation}.",
                    columns=columns,
                )
        elif color_column in (x_column, y_column):
            return make("Color by must differ from X and Y.", columns=columns)

        points, truncated = _collect_points(
            frame,
            chart_type=chart_type,
            aggregation=aggregation,
            x_column=x_column,
            y_column=y_column,
            color_column=color_column,
            max_points=max_points,
        )
        if points.height == 0:
            return make("No rows to plot.", columns=columns)

        series = _split_series(
            points,
            x_column=x_column,
            y_column=y_column,
            color_column=color_column,
        )
        point_count = sum(len(item.x) for item in series)
        return make(
            series=series,
            point_count=point_count,
            truncated=truncated,
            columns=columns,
        )
    except Exception as exc:  # noqa: BLE001 - a bad frame must not crash the UI
        return make(f"Could not build the chart: {exc}")


def _coerce_frame(data: Any) -> pl.DataFrame | pl.LazyFrame | None:
    """Polars frames pass through; pandas frames are converted; the rest is None."""
    if isinstance(data, (pl.DataFrame, pl.LazyFrame)):
        return data
    data_type = type(data)
    if data_type.__name__ == "DataFrame" and data_type.__module__.startswith("pandas"):
        return pl.from_pandas(data)
    return None


def _schema_names(frame: pl.DataFrame | pl.LazyFrame) -> list[str]:
    schema = frame.collect_schema() if isinstance(frame, pl.LazyFrame) else frame.schema
    return list(schema.keys())


def _numeric_column(frame: pl.DataFrame | pl.LazyFrame, column: str) -> bool:
    schema = frame.collect_schema() if isinstance(frame, pl.LazyFrame) else frame.schema
    dtype = schema.get(column)
    if dtype is None:
        return False
    try:
        return bool(dtype.is_numeric()) or dtype == pl.Boolean
    except Exception:  # noqa: BLE001 - exotic dtype: treat as non-numeric
        return False


def _collect_points(
    frame: pl.DataFrame | pl.LazyFrame,
    *,
    chart_type: str,
    aggregation: str,
    x_column: str,
    y_column: str,
    color_column: str,
    max_points: int,
) -> tuple[pl.DataFrame, bool]:
    """Collect at most ``max_points`` + 1 rows and report truncation."""
    lazy = frame.lazy() if isinstance(frame, pl.DataFrame) else frame
    limit = max(1, int(max_points))

    if aggregation == "none":
        work = lazy.select(
            [x_column, y_column] + ([color_column] if color_column else [])
        )
        if chart_type == "line":
            # maintain_order: line charts must draw x-ties in input order.
            # Polars 2.0's sort is no longer stable by default, so without
            # this the drawn order of tied points changes between runs.
            work = work.sort(x_column, nulls_last=True, maintain_order=True)
    else:
        if aggregation == "count":
            expression = pl.len().cast(pl.Float64)
        else:
            expression = getattr(
                pl.col(y_column).cast(pl.Float64, strict=False), aggregation
            )()
        work = lazy.group_by([x_column] + ([color_column] if color_column else [])).agg(
            expression.alias(y_column)
        )
        work = work.sort(x_column, nulls_last=True)

    probe = work.head(limit + 1).collect()
    truncated = probe.height > limit
    return (probe.head(limit) if truncated else probe), truncated


def _split_series(
    frame: pl.DataFrame,
    *,
    x_column: str,
    y_column: str,
    color_column: str,
) -> tuple[ChartSeries, ...]:
    """One series per color value, or a single series when Color by is off."""
    if not color_column:
        return (
            ChartSeries(
                name=y_column,
                x=tuple(frame.get_column(x_column).to_list()),
                y=tuple(frame.get_column(y_column).to_list()),
            ),
        )

    series: list[ChartSeries] = []
    partitions = frame.partition_by(color_column, as_dict=True)
    for key, part in sorted(partitions.items(), key=lambda item: str(item[0])):
        value = key[0] if isinstance(key, (tuple, list)) else key
        series.append(
            ChartSeries(
                name=f"{color_column}: {value}",
                x=tuple(part.get_column(x_column).to_list()),
                y=tuple(part.get_column(y_column).to_list()),
            )
        )
    return tuple(series)
