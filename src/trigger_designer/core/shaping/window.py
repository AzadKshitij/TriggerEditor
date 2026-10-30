"""Window: look-back, look-ahead, ranking, running and rolling columns."""

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

OPS = (
    "lag",
    "lead",
    "row_number",
    "rank",
    "dense_rank",
    "cum_sum",
    "cum_min",
    "cum_max",
    "cum_mean",
    "rolling_sum",
)
#: Operations that read text as numbers (``numeric_expr``).
NUMERIC_OPS = frozenset(
    {
        "rank",
        "dense_rank",
        "cum_sum",
        "cum_min",
        "cum_max",
        "cum_mean",
        "rolling_sum",
    }
)
#: Operations whose source must be numeric or text.
ACCUMULATING_OPS = frozenset(
    {"cum_sum", "cum_min", "cum_max", "cum_mean", "rolling_sum"}
)

DEFAULTS = {
    "partition_by": [],
    "order_by": [],
    "ops": [],
}
OP_DEFAULT = {
    "op": "lag",
    "source": "",
    "name": "",
    "offset": 1,
    "window": 3,
    "partial": False,
    "descending": False,
    "nulls": "skip",
}


def _default_name(op: dict) -> str:
    kind, source = op["op"], op["source"]
    if kind == "row_number":
        return "Row_Number"
    if kind in ("lag", "lead"):
        return f"{source}_{kind}{op['offset']}"
    if kind == "rolling_sum":
        return f"{source}_roll{op['window']}"
    return f"{source}_{kind}"


def _whole_number(value, label: str, index: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ShapingError(
            "TD-SHAPE-004", f"Calculation {index}: {label} must be a whole number"
        ) from exc
    return number


def normalize(settings: dict) -> dict:
    s = {**DEFAULTS, **(settings or {})}
    s["partition_by"] = list(s["partition_by"] or [])
    order = []
    for item in s["order_by"] or []:
        column = str((item or {}).get("column") or "")
        if not column:
            raise ShapingError("TD-SHAPE-001", "Pick a column for every Order by row")
        order.append(
            {"column": column, "descending": bool((item or {}).get("descending"))}
        )
    s["order_by"] = order
    operations = []
    for index, raw in enumerate(s["ops"] or [], start=1):
        op = {**OP_DEFAULT, **(raw or {})}
        kind = op["op"]
        if kind not in OPS:
            raise ShapingError("TD-SHAPE-004", f"Unknown window operation {kind}")
        op["source"] = str(op["source"] or "")
        if kind != "row_number" and not op["source"]:
            raise ShapingError("TD-SHAPE-001", "Pick a source column")
        op["offset"] = _whole_number(op["offset"], "Offset", index)
        op["window"] = _whole_number(op["window"], "Window size", index)
        if kind in ("lag", "lead") and op["offset"] < 1:
            raise ShapingError(
                "TD-SHAPE-004", "Offset and window size must be at least 1"
            )
        if kind == "rolling_sum" and op["window"] < 1:
            raise ShapingError(
                "TD-SHAPE-004", "Offset and window size must be at least 1"
            )
        if op["nulls"] not in ("skip", "zero"):
            raise ShapingError("TD-SHAPE-004", f"Unknown null handling {op['nulls']}")
        op["partial"] = bool(op["partial"])
        op["descending"] = bool(op["descending"])
        op["name"] = str(op["name"] or "").strip() or _default_name(op)
        operations.append(op)
    s["ops"] = operations
    return s


def _op_expr(op: dict, dtype: pl.DataType | None) -> pl.Expr:
    kind = op["op"]
    if kind == "row_number":
        return pl.int_range(1, pl.len() + 1, dtype=pl.Int64)
    column = pl.col(op["source"])
    if kind in NUMERIC_OPS and (
        dtype == pl.String or (dtype is not None and dtype.is_numeric())
    ):
        column = numeric_expr(op["source"], dtype)
    if kind == "lag":
        return column.shift(op["offset"])
    if kind == "lead":
        return column.shift(-op["offset"])
    if kind in ("rank", "dense_rank"):
        method = "min" if kind == "rank" else "dense"
        return column.rank(method, descending=op["descending"]).cast(pl.Int64)
    if op["nulls"] == "zero":
        column = column.fill_null(0.0)
    if kind == "cum_sum":
        return column.cum_sum()
    if kind == "cum_min":
        return column.cum_min()
    if kind == "cum_max":
        return column.cum_max()
    if kind == "cum_mean":
        return column.cum_sum() / column.is_not_null().cum_sum()
    return column.rolling_sum(
        window_size=op["window"], min_samples=1 if op["partial"] else op["window"]
    )


def _check_source(op: dict, dtype: pl.DataType) -> None:
    kind = op["op"]
    if kind == "row_number" or kind in ("lag", "lead"):
        return
    ok = dtype == pl.String or dtype.is_numeric()
    if kind in ("rank", "dense_rank"):
        ok = ok or dtype.is_temporal()
    if not ok:
        raise ShapingError(
            "TD-SHAPE-091",
            f"'{op['source']}' must be a number or text holding numbers",
            [op["source"]],
        )


def apply_window(frame: Frame, settings: dict) -> pl.LazyFrame:
    s = normalize(settings)
    lf = as_lazy(frame)
    schema = schema_of(lf)
    order_cols = [item["column"] for item in s["order_by"]]
    sources = [op["source"] for op in s["ops"] if op["op"] != "row_number"]
    require_columns(schema, [*s["partition_by"], *order_cols, *sources])
    taken = set(schema) | {POS}
    for op in s["ops"]:
        if op["name"] in taken:
            raise ShapingError(
                "TD-SHAPE-002",
                f"Output column name already used: '{op['name']}'",
                [op["name"]],
            )
        taken.add(op["name"])
        if op["op"] != "row_number":
            _check_source(op, schema[op["source"]])
    if not s["ops"]:
        return lf

    parts = list(s["partition_by"])
    exprs = []
    for op in s["ops"]:
        expr = _op_expr(op, schema.get(op["source"]))
        exprs.append((expr.over(parts) if parts else expr).alias(op["name"]))
    if not order_cols:
        return lf.with_columns(exprs)
    # Sort-compute-restore: `over(order_by=)` takes one direction for every
    # key, so sort by partition, each key's own direction, then input position.
    keys = [*parts, *order_cols, POS]
    descending = (
        [False] * len(parts) + [item["descending"] for item in s["order_by"]] + [False]
    )
    return (
        lf.with_row_index(POS)
        .sort(keys, descending=descending, nulls_last=True, maintain_order=True)
        .with_columns(exprs)
        .sort(POS, maintain_order=True)
        .drop(POS)
    )


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return [apply_window(frames[0], settings)]
