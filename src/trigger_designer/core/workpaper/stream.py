"""Statistics, the full-list CSV sidecar and file hashes (streaming, Qt-free)."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import polars as pl

from trigger_designer.core.excel.cells import (
    ColumnPlan,
    column_values,
    needs_quote_prefix,
)
from trigger_designer.core.excel.spool import Spooled
from trigger_designer.core.utils.amounts import amount_expr as shared_amount_expr

HASH_CAP_BYTES = 4 * 1024**3
_CHUNK = 1024 * 1024


def amount_expr(name: str, dtype: Any) -> pl.Expr | None:
    """Float64 value of the amount column; ``None`` when the dtype cannot hold amounts.

    Text goes through the shared decimal-comma aware parser
    (``core/utils/amounts.py``): ``1,234.50``, ``1.234,50``, ``1'234,50``,
    ``12,5`` and ``(12.00)`` are read; anything else becomes null (the caller
    counts those and keeps the original text).
    """
    if dtype == pl.String:
        return shared_amount_expr(name, dtype)
    col = pl.col(name)
    if dtype.is_numeric():
        return col.cast(pl.Float64, strict=False)
    return None


@dataclass
class ExceptionStats:
    total: int = 0
    schema: dict[str, Any] = field(default_factory=dict)
    amount_usable: bool = False
    amount_sum: float | None = None
    unparseable: int = 0
    max_len: dict[str, int] = field(default_factory=dict)


def compute_stats(
    spooled: Spooled, plans: list[ColumnPlan], amount_column: str = ""
) -> ExceptionStats:
    """One pass over the spooled exceptions: count, amount sum, text lengths."""
    stats = ExceptionStats(schema=dict(spooled.schema))
    exprs: list[pl.Expr] = [pl.len().cast(pl.Int64).alias("__n")]
    amount = None
    if amount_column and amount_column in spooled.schema:
        amount = amount_expr(amount_column, spooled.schema[amount_column])
    if amount is not None:
        exprs.append(amount.sum().alias("__sum"))
        if spooled.schema[amount_column] == pl.String:
            raw = pl.col(amount_column)
            bad = raw.is_not_null() & (raw.str.strip_chars() != "") & amount.is_null()
            exprs.append(bad.sum().cast(pl.Int64).alias("__bad"))
    for i, plan in enumerate(plans):
        if plan.kind == "str":
            exprs.append(pl.col(plan.name).str.len_chars().max().alias(f"__len{i}"))
    row = spooled.lazy().select(exprs).collect().row(0, named=True)
    stats.total = int(row["__n"])
    if amount is not None:
        stats.amount_usable = True
        stats.amount_sum = float(row["__sum"] or 0.0)
        stats.unparseable = int(row.get("__bad") or 0)
    for i, plan in enumerate(plans):
        if plan.kind == "str":
            stats.max_len[plan.name] = int(row[f"__len{i}"] or 0)
    return stats


def population_stats(
    population: pl.LazyFrame | pl.DataFrame, amount_column: str = ""
) -> tuple[int, float | None, str | None]:
    """(rows, value of the amount column or None, note) of the Population input."""
    lazy = population.lazy()
    schema = lazy.collect_schema()
    exprs: list[pl.Expr] = [pl.len().cast(pl.Int64).alias("__n")]
    note = None
    amount = None
    if amount_column:
        if amount_column in schema:
            amount = amount_expr(amount_column, schema[amount_column])
        if amount is None:
            note = (
                f"The amount column '{amount_column}' is not a usable amount on the "
                "Population input, so the population value is not shown."
            )
    if amount is not None:
        exprs.append(amount.sum().alias("__sum"))
    row = lazy.select(exprs).collect().row(0, named=True)
    value = float(row["__sum"] or 0.0) if amount is not None else None
    return int(row["__n"]), value, note


def sha256_file(path: str) -> str | None:
    """SHA-256 of a file; ``None`` when it is missing or larger than 4 GiB."""
    try:
        if os.path.getsize(path) > HASH_CAP_BYTES:
            return None
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            while chunk := handle.read(_CHUNK):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str):
        return "'" + value if needs_quote_prefix(value) else value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return (
            value.isoformat(sep=" ")
            if isinstance(value, dt.datetime)
            else value.isoformat()
        )
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    return "'" + text if needs_quote_prefix(text) else text


def write_csv_sidecar(spooled: Spooled, plans: list[ColumnPlan], path: str) -> int:
    """Every exception row as UTF-8 (BOM) CSV with a ``Ref`` column; returns rows.

    Text that Excel could read as a formula gets a leading apostrophe.
    """
    rows = 0
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Ref", *(_csv_cell(p.header) for p in plans)])
        for batch in spooled.batches():
            columns = [column_values(batch[p.name], p) for p in plans]
            for i in range(batch.height):
                rows += 1
                writer.writerow([rows, *(_csv_cell(col[i]) for col in columns)])
    return rows
