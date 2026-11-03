"""Running Total: cumulative sums as added columns (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import as_lazy, numeric_expr, schema_of
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes

DEFAULTS = {
    "sum_columns": [],
    "group_by_columns": [],
}


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    """Append ``RunTot_<column>`` cumulative sums in input row order."""
    settings = settings or {}
    frame = as_lazy(frames[0])
    schema = schema_of(frame)
    # Like Window: a text column is read as numbers (an unreadable value is
    # empty), because a CSV arrives with every column as text.
    numeric = [
        name
        for name, dtype in schema.items()
        if dtype.is_numeric() or dtype == pl.String
    ]
    sums = [name for name in settings.get("sum_columns") or [] if name in numeric]
    groups = [name for name in settings.get("group_by_columns") or [] if name in schema]
    if not sums:
        return [frame]

    expressions: list[pl.Expr] = []
    for name in sums:
        if schema[name] == pl.String:
            expression = numeric_expr(name, schema[name]).cum_sum()
        else:
            expression = pl.col(name).cum_sum()
        if groups:
            expression = expression.over(groups)
        expressions.append(expression.alias(f"RunTot_{name}"))

    # cum_sum keeps the input width (Int32 in -> Int32 out); normalise into
    # the dtype set every downstream node supports.
    return [normalize_to_supported_dtypes(frame.with_columns(expressions))]
