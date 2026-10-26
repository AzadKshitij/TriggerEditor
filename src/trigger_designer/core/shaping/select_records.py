"""Select first/last/range/ranked rows; the remainder leaves by output 2."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import (
    Frame,
    ShapingError,
    as_lazy,
    numeric_expr,
    require_columns,
    schema_of,
)

POS = "__pos"
MODES = ("first_n", "last_n", "row_range", "largest_n", "smallest_n")

DEFAULTS = {
    "mode": "first_n",
    "n": 10,
    "range_start": 1,
    "range_end": 100,
    "by": "",
    "ties": "exact",
    "group_by": [],
}


def apply_select_records(
    frame: Frame, settings: dict
) -> tuple[pl.LazyFrame, pl.LazyFrame]:
    s = {**DEFAULTS, **(settings or {})}
    lf = as_lazy(frame)
    schema = schema_of(lf)
    if s["mode"] not in MODES:
        raise ShapingError("TD-SHAPE-004", f"Unknown mode {s['mode']!r}")
    n = int(s["n"])
    if s["mode"] != "row_range" and n < 1:
        raise ShapingError("TD-SHAPE-004", "N must be at least 1")
    if s["mode"] == "row_range" and not (
        1 <= int(s["range_start"]) <= int(s["range_end"])
    ):
        raise ShapingError("TD-SHAPE-004", "Row range must satisfy 1 <= start <= end")
    groups = list(s["group_by"] or [])
    require_columns(schema, groups)

    def over(expr: pl.Expr) -> pl.Expr:
        return expr.over(groups) if groups else expr

    lf = lf.with_row_index(POS)
    ranked = None
    if s["mode"] == "first_n":
        keep = over(pl.int_range(pl.len())) < n
    elif s["mode"] == "last_n":
        keep = over(pl.int_range(pl.len())) >= over(pl.len()) - n
    elif s["mode"] == "row_range":
        keep = pl.col(POS).is_between(
            int(s["range_start"]) - 1, int(s["range_end"]) - 1
        )
    else:
        if not s["by"]:
            raise ShapingError("TD-SHAPE-001", "Pick the column to rank by")
        require_columns(schema, [s["by"]])
        largest = s["mode"] == "largest_n"
        lf = lf.with_columns(numeric_expr(s["by"], schema[s["by"]]).alias("__key"))
        method = "min" if s["ties"] == "include_ties" else "ordinal"
        keep = (over(pl.col("__key").rank(method, descending=largest)) <= n).fill_null(
            False
        )
        ranked = largest
    lf = lf.with_columns(keep.alias("__keep"))
    selected = lf.filter(pl.col("__keep"))
    if ranked is not None:
        selected = selected.sort(
            ["__key", POS],
            descending=[ranked, False],
            nulls_last=True,
            maintain_order=True,
        )
    rest = lf.filter(~pl.col("__keep"))
    drop = ["__keep", "__key", POS]
    return (
        selected.drop(drop, strict=False),
        rest.drop(drop, strict=False),
    )


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return list(apply_select_records(frames[0], settings))
