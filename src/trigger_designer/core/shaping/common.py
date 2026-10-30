"""Shared helpers for the shaping nodes (Qt-free)."""

from __future__ import annotations

from collections.abc import Iterable

import duckdb
import polars as pl

Frame = pl.LazyFrame | pl.DataFrame

#: DuckDB workers can enter Polars' ``LazyFrame.collect`` off the Qt main
#: thread. Formula and Filter live evaluation crashed in that path, and one
#: worker keeps the Arrow exchange on the caller. These shaping queries are
#: row-wise scans/projections, so the measured throughput loss is negligible;
#: a future heavy aggregation may warrant its own connection setting.
DUCKDB_THREADS = 1


def connect_duckdb() -> duckdb.DuckDBPyConnection:
    """Open the in-memory connection used by shaping nodes."""
    return duckdb.connect(":memory:", config={"threads": DUCKDB_THREADS})


#: Stable error codes (plan 03 translates; never reuse or renumber).
ERROR_CODES: dict[str, str] = {
    "TD-SHAPE-001": "A required setting is missing",
    "TD-SHAPE-002": "An output column name is empty, duplicated or already exists",
    "TD-SHAPE-003": "A selected column is not in the input any more",
    "TD-SHAPE-004": "A setting value is out of range or unknown",
    "TD-SHAPE-005": "A required input has no data",
    "TD-SHAPE-040": "The pattern is not a valid regular expression",
    "TD-SHAPE-041": "The pattern is too long",
    "TD-SHAPE-042": "Find text is empty",
    "TD-SHAPE-043": "Too many rules",
    "TD-SHAPE-044": "The column must be text",
    "TD-SHAPE-050": "The column is not a date and not text",
    "TD-SHAPE-052": "A holiday is not a YYYY-MM-DD date",
    "TD-SHAPE-053": "Working days must name at least one weekday",
    "TD-SHAPE-060": "Index, header and value columns must be different",
    "TD-SHAPE-061": "Too many new columns",
    "TD-SHAPE-070": "Amount or date column is set on one side only",
    "TD-SHAPE-071": "Add a key column pair or a date column",
    "TD-SHAPE-072": "Too many possible matches",
    "TD-SHAPE-081": "Too many possible fuzzy pairs",
    "TD-SHAPE-082": "Too many rows to compare without blocking",
    "TD-SHAPE-091": "The column must be a number",
    "TD-SHAPE-101": "The split pattern can match nothing",
    "TD-SHAPE-110": "Only one statement is allowed",
    "TD-SHAPE-111": "Only SELECT queries are allowed",
    "TD-SHAPE-112": "The SQL uses a function or file access that is not allowed",
    "TD-SHAPE-113": "The SQL could not be parsed or run",
    "TD-SHAPE-114": "The SQL is too long",
    "TD-SHAPE-115": "The query took too long",
}


class ShapingError(ValueError):
    """A configuration or data problem with a stable code."""

    def __init__(self, code: str, detail: str, columns: Iterable[str] = ()):
        self.code = code
        self.detail = detail
        self.columns = tuple(columns)
        super().__init__(f"[{code}] {detail}")


def as_lazy(frame: Frame) -> pl.LazyFrame:
    return frame if isinstance(frame, pl.LazyFrame) else frame.lazy()


def schema_of(frame: Frame) -> dict[str, pl.DataType]:
    schema = frame.collect_schema() if isinstance(frame, pl.LazyFrame) else frame.schema
    return dict(schema.items())


#: Live (editing) evaluation reads this many leading rows of each input and
#: shows at most this many rows of each output, so opening or editing a large
#: workflow stays responsive. Run always processes the whole input.
LIVE_SAMPLE_ROWS = 100


def live_sample(frame: Frame | None) -> Frame | None:
    """The leading rows live evaluation works on; ``None`` passes through."""
    return None if frame is None else frame.head(LIVE_SAMPLE_ROWS)


def require_columns(frame_schema: dict, names: Iterable[str]) -> None:
    missing = [name for name in names if name not in frame_schema]
    if missing:
        raise ShapingError(
            "TD-SHAPE-003",
            f"Column(s) not found: {', '.join(missing)}",
            missing,
        )


def unique_name(base: str, taken: Iterable[str]) -> str:
    """``base`` if free, else ``base_2``, ``base_3`` ... (deterministic)."""
    taken = set(taken)
    if base not in taken:
        return base
    index = 2
    while f"{base}_{index}" in taken:
        index += 1
    return f"{base}_{index}"


def numeric_expr(name: str, dtype: pl.DataType) -> pl.Expr:
    """Column as Float64; text is cast with strict=False (bad values -> null)."""
    column = pl.col(name)
    if dtype.is_numeric():
        return column.cast(pl.Float64)
    return (
        column.cast(pl.String)
        .str.replace_all(",", "")
        .str.strip_chars()
        .cast(pl.Float64, strict=False)
    )


def estimate_pairs(left: pl.DataFrame, right: pl.DataFrame, keys: list[str]) -> int:
    """Rows an inner join on ``keys`` would produce, without building it."""
    a = left.drop_nulls(keys).group_by(keys).len(name="__cnt_l")
    b = right.drop_nulls(keys).group_by(keys).len(name="__cnt_r")
    total = a.join(b, on=keys).select(
        (pl.col("__cnt_l").cast(pl.Int64) * pl.col("__cnt_r").cast(pl.Int64)).sum()
    )
    return int(total.item() or 0)
