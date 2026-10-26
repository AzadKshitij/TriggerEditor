"""Bounded second query: find the first row a cast could not convert."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocateResult:
    status: str
    row_index: int | None = None
    values: tuple[str, ...] = ()
    scanned_rows: int = 0
    elapsed_s: float = 0.0
    cap_hit: bool = False


def polars_dtype_from_name(name: str) -> pl.DataType | None:
    value = (name or "").strip()
    low = value.lower()
    aliases = {
        "i8": pl.Int8,
        "i16": pl.Int16,
        "i32": pl.Int32,
        "i64": pl.Int64,
        "u8": pl.UInt8,
        "u16": pl.UInt16,
        "u32": pl.UInt32,
        "u64": pl.UInt64,
        "f32": pl.Float32,
        "f64": pl.Float64,
        "bool": pl.Boolean,
        "boolean": pl.Boolean,
        "date": pl.Date,
        "time": pl.Time,
        "str": pl.String,
        "string": pl.String,
        "tinyint": pl.Int8,
        "int1": pl.Int8,
        "smallint": pl.Int16,
        "int2": pl.Int16,
        "int32": pl.Int32,
        "integer": pl.Int32,
        "int64": pl.Int64,
        "bigint": pl.Int64,
        "float": pl.Float32,
        "double": pl.Float64,
    }
    if low in aliases:
        return aliases[low]
    decimal = re.match(r"decimal(?:\[|\(|_)(\d+)\s*[, ]\s*(\d+)", low)
    if decimal:
        return pl.Decimal(int(decimal.group(1)), int(decimal.group(2)))
    if low.startswith("datetime") or low in {"timestamp", "timestamp_us"}:
        return pl.Datetime("us")
    return None


def probe_expr(
    column: str, target: pl.DataType, *, date_format: str | None = None
) -> pl.Expr:
    source = pl.col(column)
    if target == pl.Date:
        return source.str.to_date(format=date_format, strict=False)
    if isinstance(target, pl.Datetime):
        return source.str.to_datetime(format=date_format, strict=False)
    return source.str.strip_chars().cast(target, strict=False)


def _display(value: object, max_chars: int) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    text = text.encode("utf-8", "replace").decode("utf-8", "replace")
    if len(text) > max_chars:
        return text[: max_chars - 1] + "…"
    return text


def locate_conversion_failures(
    frames: Sequence[pl.LazyFrame | pl.DataFrame],
    column: str,
    target: pl.DataType | None,
    *,
    known_value: str | None = None,
    sum_mode: bool = False,
    date_format: str | None = None,
    row_cap: int = 5_000_000,
    max_values: int = 5,
    max_chars: int = 80,
) -> LocateResult:
    started = time.monotonic()
    try:
        chosen = None
        schema = {}
        for frame in frames or ():
            if frame is None:
                continue
            schema = frame.collect_schema()
            if column in schema:
                chosen = frame
                break
        if chosen is None:
            return LocateResult("skipped", elapsed_s=time.monotonic() - started)

        if target is None:
            target = pl.Float64
        lf = chosen.lazy().head(row_cap).with_row_index("__r", offset=1)
        source_dtype = schema.get(column)
        if sum_mode or (
            isinstance(source_dtype, pl.String)
            and not isinstance(source_dtype, pl.Categorical)
        ):
            bad = (
                pl.col(column).is_not_null()
                & probe_expr(column, target, date_format=date_format).is_null()
            )
        else:
            bad = (
                pl.col(column).is_not_null()
                & pl.col(column).cast(target, strict=False).is_null()
            )

        # Fetch a batch so duplicate bad values do not hide distinct ones.
        query = (
            lf.filter(bad)
            .select("__r", pl.col(column).cast(pl.String).alias("__v"))
            .head(max_values * 20)
        )
        rows = query.collect(engine="streaming").rows()
        hits: list[tuple[int, str]] = [(int(row), value) for row, value in rows]

        if known_value is not None and known_value not in {
            value for _row, value in hits
        }:
            extra = (
                lf.filter(pl.col(column).cast(pl.String) == known_value)
                .select("__r", pl.col(column).cast(pl.String).alias("__v"))
                .head(1)
                .collect(engine="streaming")
                .rows()
            )
            hits.extend((int(row), value) for row, value in extra)

        elapsed = time.monotonic() - started
        if not hits:
            return LocateResult(
                "not_found",
                scanned_rows=row_cap,
                elapsed_s=elapsed,
                cap_hit=True,
            )

        hits.sort(key=lambda item: item[0])
        row_index = hits[0][0]
        values: list[str] = []
        for _row, value in hits:
            display = _display(value, max_chars)
            if display not in values:
                values.append(display)
            if len(values) >= max_values:
                break
        return LocateResult(
            "found",
            row_index=row_index,
            values=tuple(values),
            scanned_rows=max(row for row, _value in hits),
            elapsed_s=elapsed,
        )
    except Exception as exc:  # noqa: BLE001 - locator never raises
        logger.debug("Row locator failed: %s", exc)
        return LocateResult("error", elapsed_s=time.monotonic() - started)
