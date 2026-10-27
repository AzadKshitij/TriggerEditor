"""Select: ordered column projection, rename and dtype conversion (Qt-free)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any

import polars as pl

from trigger_designer.core.shaping.common import as_lazy, schema_of

BOOLEAN_TRUE_TOKENS = ("true", "1", "yes", "y", "t", "on")
BOOLEAN_FALSE_TOKENS = ("false", "0", "no", "n", "f", "off")

DEFAULTS = {
    "columns": [],
    "auto_accept_new_columns": True,
}

_DTYPE_MAP = {
    "String": pl.String,
    "Int64": pl.Int64,
    "Float64": pl.Float64,
    "Boolean": pl.Boolean,
    "Date": pl.Date,
    "Datetime": pl.Datetime,
    "List": pl.List,
    "Struct": pl.Struct,
    "Categorical": pl.Categorical,
    "Binary": pl.Binary,
    "Decimal": pl.Decimal,
    "Duration": pl.Duration,
    # Legacy display names
    "object": pl.String,
    "int64": pl.Int64,
    "float64": pl.Float64,
    "bool": pl.Boolean,
    "datetime64": pl.Datetime,
}


def display_dtype(dtype: Any) -> str:
    """Short dtype name used by the table's dropdown."""
    text = str(dtype)
    text = text.removeprefix("pl.")
    if "(" in text:
        text = text.split("(", 1)[0]
    return text


def _date_parse_formats() -> list[str]:
    return [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%m-%d-%Y",
        "%m/%d/%Y",
        "%m.%d.%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d %Y",
        "%B %d %Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
    ]


def _datetime_parse_formats() -> list[str]:
    formats: list[str] = []
    for date_format in _date_parse_formats():
        for suffix in (" %H:%M:%S", " %H:%M", "T%H:%M:%S", "T%H:%M"):
            formats.append(f"{date_format}{suffix}")
    formats.extend(
        [
            "%d %b %Y %H:%M:%S",
            "%d %B %Y %H:%M:%S",
            "%b %d %Y %H:%M:%S",
            "%B %d %Y %H:%M:%S",
            "%d %b %Y %H:%M",
            "%d %B %Y %H:%M",
            "%b %d %Y %H:%M",
            "%B %d %Y %H:%M",
        ]
    )
    return formats


def _map_dtype(dtype: str) -> pl.DataType | None:
    return _DTYPE_MAP.get(dtype)


def dtype_matches(current: pl.DataType | None, target: str) -> bool:
    if current is None:
        return False
    wanted = _map_dtype(target)
    if wanted is None:
        return False
    base = getattr(current, "base_type", None)
    if base is None:
        return False
    return base() == wanted


def _boolean_expr(column: str) -> pl.Expr:
    source = pl.col(column)
    token = source.cast(pl.String, strict=False).str.to_lowercase().str.strip_chars()
    number = source.cast(pl.Float64, strict=False)
    return (
        pl.when(token.is_in(BOOLEAN_TRUE_TOKENS))
        .then(True)
        .when(token.is_in(BOOLEAN_FALSE_TOKENS))
        .then(False)
        .when(number.is_not_null() & (number != 0.0))
        .then(True)
        .when(number.is_not_null())
        .then(False)
        .otherwise(None)
        .alias(column)
    )


def build_dtype_expr(
    column: str,
    dtype: str,
    date_format: str = "",
    source_dtype: pl.DataType | None = None,
) -> pl.Expr | None:
    target = _map_dtype(dtype)
    if target is None:
        return None
    if target is pl.Boolean:
        return _boolean_expr(column)
    if target not in (pl.Date, pl.Datetime):
        return pl.col(column).cast(target, strict=False).alias(column)

    # Polars 2.0 raises on String -> temporal casts instead of returning null,
    # so the bare cast is only a fallback for sources that can use it: epoch
    # numerics, or a Date/Datetime being re-typed. An unresolved source gets none.
    base_fn = getattr(source_dtype, "base_type", None)
    allow_raw_cast = (
        source_dtype is not None
        and (base_fn() if base_fn is not None else source_dtype) != pl.String
    )

    text = pl.col(column).cast(pl.String, strict=False)
    if target == pl.Date:
        if date_format:
            expressions = [
                text.str.strptime(pl.Date, date_format, strict=False, exact=True),
                text.str.to_date(strict=False),
            ]
        else:
            expressions = [
                text.str.strptime(pl.Date, fmt, strict=False, exact=True)
                for fmt in _date_parse_formats()
            ]
            expressions.extend(
                text.str.strptime(pl.Datetime, fmt, strict=False, exact=True).cast(
                    pl.Date, strict=False
                )
                for fmt in _datetime_parse_formats()
            )
            expressions.append(text.str.to_date(strict=False))
        if allow_raw_cast:
            expressions.append(pl.col(column).cast(pl.Date, strict=False))
        return pl.coalesce(expressions).alias(column)

    if date_format:
        expressions = [
            text.str.strptime(pl.Datetime, date_format, strict=False, exact=True),
            text.str.to_datetime(strict=False),
        ]
    else:
        expressions = [
            text.str.strptime(pl.Datetime, fmt, strict=False, exact=True)
            for fmt in _datetime_parse_formats()
        ]
        expressions.extend(
            text.str.strptime(pl.Date, fmt, strict=False, exact=True).cast(
                pl.Datetime, strict=False
            )
            for fmt in _date_parse_formats()
        )
        expressions.append(text.str.to_datetime(strict=False))
    if allow_raw_cast:
        expressions.append(pl.col(column).cast(pl.Datetime, strict=False))
    return pl.coalesce(expressions).alias(column)


def infer_dtype(values: Iterable[Any]) -> tuple[str | None, str | None]:
    """Infer one of the table's dtype labels from sampled values."""
    clean = [v for v in values if v is not None and str(v).strip() != ""]
    if not clean:
        return "String", None
    lowered = [str(v).strip().lower() for v in clean]
    if all(v in ("true", "false") for v in lowered):
        return "Boolean", None
    try:
        for value in clean:
            int(str(value).strip())
        return "Int64", None
    except TypeError, ValueError:
        pass
    try:
        for value in clean:
            float(str(value).strip())
        return "Float64", None
    except TypeError, ValueError:
        pass
    for fmt in _date_parse_formats():
        try:
            for value in clean:
                datetime.strptime(str(value).strip(), fmt)  # noqa: DTZ007 - date-only sample
            return "Date", fmt
        except TypeError, ValueError, re.error:
            continue
    return "String", None


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    """Project selected columns in table order, then cast and rename."""
    frame = as_lazy(frames[0])
    schema = schema_of(frame)
    columns = list((settings or {}).get("columns") or [])
    if not columns:
        return [frame]

    selected = [
        column
        for column in columns
        if bool(column.get("selected")) and column.get("name") in schema
    ]
    if not selected:
        # Preserve the old Select behaviour: no usable selection means keep
        # the input rather than silently returning a zero-column frame.
        return [frame]

    expressions: list[pl.Expr] = []
    for column in selected:
        name = str(column.get("name") or "")
        dtype = str(column.get("dtype") or "")
        rename = str(column.get("rename") or "")
        expression = pl.col(name)
        if dtype and not dtype_matches(schema[name], dtype):
            converted = build_dtype_expr(
                name,
                dtype,
                str(column.get("date_format") or ""),
                source_dtype=schema[name],
            )
            if converted is not None:
                expression = converted
        target = rename or name
        expressions.append(expression.alias(target))
    return [frame.select(expressions)]
