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
    unique_name,
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
    pos = unique_name(POS, schema)
    taken = {*schema, pos}
    key_name = unique_name("__key", taken)
    taken.add(key_name)
    keep_name = unique_name("__keep", taken)
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

    lf = lf.with_row_index(pos)
    ranked = None
    if s["mode"] == "first_n":
        keep = over(pl.int_range(pl.len())) < n
    elif s["mode"] == "last_n":
        keep = over(pl.int_range(pl.len())) >= over(pl.len()) - n
    elif s["mode"] == "row_range":
        keep = pl.col(pos).is_between(
            int(s["range_start"]) - 1, int(s["range_end"]) - 1
        )
    else:
        if not s["by"]:
            raise ShapingError("TD-SHAPE-001", "Pick the column to rank by")
        require_columns(schema, [s["by"]])
        dtype = schema[s["by"]]
        if not dtype.is_numeric():
            if dtype not in (pl.String, pl.Categorical, pl.Enum):
                raise ShapingError(
                    "TD-SHAPE-091",
                    f"'{s['by']}' must be a number or text holding numbers",
                    [s["by"]],
                )
            # The only collect here: one aggregate pass, and only for text columns.
            flags = (
                as_lazy(frame)
                .select(
                    pl.col(s["by"]).is_not_null().any().alias("has_values"),
                    numeric_expr(s["by"], dtype)
                    .is_not_null()
                    .any()
                    .alias("has_numbers"),
                )
                .collect()
            )
            if flags["has_values"].item() and not flags["has_numbers"].item():
                raise ShapingError(
                    "TD-SHAPE-091",
                    f"'{s['by']}' has no values that can be read as numbers",
                    [s["by"]],
                )
        largest = s["mode"] == "largest_n"
        lf = lf.with_columns(numeric_expr(s["by"], schema[s["by"]]).alias(key_name))
        method = "min" if s["ties"] == "include_ties" else "ordinal"
        keep = (over(pl.col(key_name).rank(method, descending=largest)) <= n).fill_null(
            False
        )
        ranked = largest
    lf = lf.with_columns(keep.alias(keep_name))
    selected = lf.filter(pl.col(keep_name))
    if ranked is not None:
        selected = selected.sort(
            [key_name, pos],
            descending=[ranked, False],
            nulls_last=True,
            maintain_order=True,
        )
    rest = lf.filter(~pl.col(keep_name))
    drop = [keep_name, key_name, pos]
    return (
        selected.drop(drop, strict=False),
        rest.drop(drop, strict=False),
    )


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return list(apply_select_records(frames[0], settings))
