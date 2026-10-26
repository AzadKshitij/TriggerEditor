"""Pivot and Unpivot for the Transform family."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import (
    Frame,
    ShapingError,
    as_lazy,
    numeric_expr,
    require_columns,
    schema_of,
    unique_name,
)

MAX_PIVOT_COLUMNS = 500
AGGS = ("sum", "mean", "min", "max", "median", "first", "last", "count")
NUMERIC_AGGS = {"sum", "mean", "min", "max", "median"}

PIVOT_DEFAULTS = {
    "index_columns": [],
    "header_column": "",
    "value_column": "",
    "aggregation": "sum",
    "blank_label": "(blank)",
    "missing_as": "null",
}

UNPIVOT_DEFAULTS = {
    "id_columns": [],
    "value_columns": [],
    "variable_name": "Attribute",
    "value_name": "Value",
    "drop_nulls": False,
}


def _agg_expr(aggregation: str, column: str) -> pl.Expr:
    c = pl.col(column)
    return {
        "sum": pl.when(c.is_not_null().any()).then(c.sum()),
        "mean": c.mean(),
        "min": c.min(),
        "max": c.max(),
        "median": c.median(),
        "first": c.first(),
        "last": c.last(),
        "count": c.count().cast(pl.Int64),
    }[aggregation].alias(column)


def apply_pivot(frame: Frame, settings: dict) -> pl.DataFrame:
    s = {**PIVOT_DEFAULTS, **(settings or {})}
    lf = as_lazy(frame)
    schema = schema_of(lf)
    indexes = list(s["index_columns"] or [])
    header = s["header_column"]
    value_name = s["value_column"]
    if not header or not value_name:
        raise ShapingError(
            "TD-SHAPE-001", "Pick the header column and the value column"
        )
    if s["aggregation"] not in AGGS:
        raise ShapingError("TD-SHAPE-004", f"Unknown aggregation {s['aggregation']!r}")
    require_columns(schema, indexes + [header, value_name])
    if header in indexes or value_name in indexes or header == value_name:
        raise ShapingError(
            "TD-SHAPE-060", "Index, header and value columns must differ"
        )

    value = pl.col(value_name)
    if s["aggregation"] in NUMERIC_AGGS:
        value = numeric_expr(value_name, schema[value_name])
    base = lf.select(
        *[pl.col(name) for name in indexes],
        pl.col(header),
        value.alias(value_name),
    )
    aggregated = base.group_by(indexes + [header]).agg(
        _agg_expr(s["aggregation"], value_name)
    )
    aggregated = aggregated.collect()

    distinct = (
        aggregated.select(header)
        .unique()
        .sort(header, nulls_last=True)[header]
        .to_list()
    )
    if len(distinct) > MAX_PIVOT_COLUMNS:
        raise ShapingError(
            "TD-SHAPE-061",
            f"Header column has {len(distinct)} distinct values "
            f"(limit {MAX_PIVOT_COLUMNS})",
            [header],
        )
    taken = list(indexes)
    names: list[str] = []
    for value in distinct:
        name = unique_name(s["blank_label"] if value is None else str(value), taken)
        taken.append(name)
        names.append(name)
    mapping = {value: name for value, name in zip(distinct, names) if value is not None}
    header_name = (
        pl.col(header).replace_strict(mapping, return_dtype=pl.String)
        if mapping
        else pl.lit(None, pl.String)
    )
    blank = next((name for value, name in zip(distinct, names) if value is None), None)
    if blank is not None:
        header_name = (
            pl.when(pl.col(header).is_null()).then(pl.lit(blank)).otherwise(header_name)
        )
    aggregated = aggregated.with_columns(header_name.alias("__hdr")).drop(header)
    if indexes:
        wide = aggregated.pivot(
            on="__hdr",
            on_columns=names,
            index=indexes,
            values=value_name,
            aggregate_function="first",
            maintain_order=True,
        )
        wide = wide.sort(indexes, nulls_last=True, maintain_order=True)
    else:
        wide = aggregated.pivot(
            on="__hdr",
            on_columns=names,
            values=value_name,
            aggregate_function="first",
        )
    wide = wide.select(indexes + names)
    if s["missing_as"] == "zero":
        wide = wide.with_columns(pl.col(names).fill_null(0))
    return wide


def run_pivot(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return [apply_pivot(frames[0], settings).lazy()]


def apply_unpivot(frame: Frame, settings: dict) -> pl.LazyFrame:
    s = {**UNPIVOT_DEFAULTS, **(settings or {})}
    lf = as_lazy(frame)
    schema = schema_of(lf)
    ids = list(s["id_columns"] or [])
    values = list(s["value_columns"] or [])
    if not values:
        raise ShapingError("TD-SHAPE-001", "Pick at least one column to unpivot")
    require_columns(schema, ids + values)
    if set(ids) & set(values):
        raise ShapingError(
            "TD-SHAPE-060", "A column cannot be both an ID and a value column"
        )
    variable_name, value_name = (
        s["variable_name"].strip(),
        s["value_name"].strip(),
    )
    if (
        not variable_name
        or not value_name
        or variable_name == value_name
        or {variable_name, value_name} & set(ids)
    ):
        raise ShapingError("TD-SHAPE-002", "Name and value column names must be unique")
    dtypes = {schema[column] for column in values}
    if len(dtypes) > 1:
        target = (
            pl.Float64
            if all(schema[column].is_numeric() for column in values)
            else pl.String
        )
        lf = lf.with_columns(pl.col(values).cast(target))
    out = (
        lf.with_row_index("__pos")
        .unpivot(
            on=values,
            index=["__pos"] + ids,
            variable_name=variable_name,
            value_name=value_name,
        )
        .sort("__pos", maintain_order=True)
        .drop("__pos")
    )
    if s["drop_nulls"]:
        out = out.filter(pl.col(value_name).is_not_null())
    return out.select(ids + [variable_name, value_name])


def run_unpivot(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return [apply_unpivot(frames[0], settings)]
