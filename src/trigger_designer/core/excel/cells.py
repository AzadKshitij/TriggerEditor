"""How a Polars value becomes an Excel cell (Qt-free, library-free).

This is the only place that decides cell types. Every write is an explicit
``write_string`` / ``write_number`` / ... call: ``ws.write()`` guesses types and
turns ``=...`` text into a formula, which would let file content run as a
formula (formula injection). Strings are always stored as strings, and text that
Excel could re-interpret when the user edits the cell (``=``, ``@``, ``+x``,
``-x``) additionally gets the ``quote_prefix`` format.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import polars as pl

MAX_CELL_CHARS = 32_767
RESERVED_HEADERS = ("Ref", "Tick mark", "Auditor comment")
_DANGER = re.compile(r"^(?:[=@\t\r]|[+-](?!\s*[\d.,]+\s*$))")
_PLAIN_NUMBER = r"^[+-]\s*[\d.,]+\s*$"
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_ILLEGAL_SHEET = re.compile(r"[\[\]:*?/\\]")
ID_NAME = re.compile(
    r"(?i)(^|[\W_])(id|no|num|number|ref|code|acct|account|invoice|po)($|[\W_])"
)
BIG_INT = 10**15
FLAG_CONTROL = 1
FLAG_SHORTENED = 2
EXCEL_EPOCH_YEAR = 1900

FORMATS: dict[str, dict[str, Any]] = {
    "text": {},
    "int": {"num_format": "#,##0"},
    "id": {"num_format": "0"},
    "float": {"num_format": "#,##0.00"},
    "date": {"num_format": "yyyy-mm-dd"},
    "datetime": {"num_format": "yyyy-mm-dd hh:mm:ss"},
    "time": {"num_format": "hh:mm:ss"},
    "duration": {"num_format": "#,##0.000"},
    "bool": {},
    "hdr": {
        "bold": True,
        "bg_color": "#D9E1F2",
        "border": 1,
        "text_wrap": True,
        "valign": "top",
    },
}


# ------------------------------------------------------------------ text rules
def needs_quote_prefix(text: str) -> bool:
    """True when ``text`` could be read as a formula if the cell is re-entered."""
    return bool(_DANGER.match(text))


def danger_expr(col: pl.Expr) -> pl.Expr:
    """Polars twin of :func:`needs_quote_prefix` (its regex engine has no look-around)."""
    plain = col.str.contains(_PLAIN_NUMBER)
    signed = col.str.starts_with("+") | col.str.starts_with("-")
    return (
        col.str.starts_with("=")
        | col.str.starts_with("@")
        | col.str.starts_with("\t")
        | col.str.starts_with("\r")
        | (signed & ~plain)
    ).fill_null(False)


def guard_text(s: str, *, hint: str = "full text in the CSV file") -> tuple[str, int]:
    """Make ``s`` storable: control characters -> U+FFFD, over-long text shortened."""
    flags = 0
    if _CONTROL.search(s):
        s = _CONTROL.sub("�", s)
        flags |= FLAG_CONTROL
    if len(s) > MAX_CELL_CHARS:
        marker = f" ...[shortened from {len(s):,} characters; {hint}]"
        s = s[: MAX_CELL_CHARS - len(marker)] + marker
        flags |= FLAG_SHORTENED
    return s, flags


def safe_sheet_name(raw: Any, used: Iterable[str] = (), default: str = "Sheet") -> str:
    """A valid, unique (case-insensitive) worksheet name of at most 31 characters."""
    taken = {u.lower() for u in used}
    name = _ILLEGAL_SHEET.sub(" ", str(raw or ""))
    name = re.sub(r"\s+", " ", name).strip(" '")
    name = name[:31].strip(" '") or default
    candidate, n = name, 1
    while candidate.lower() in taken:
        n += 1
        suffix = f" ({n})"
        candidate = name[: 31 - len(suffix)].rstrip() + suffix
    return candidate


def quote_sheet(name: str) -> str:
    """The sheet name as written inside a formula."""
    return "'" + name.replace("'", "''") + "'"


def unique_headers(
    names: Sequence[str], reserved: Sequence[str] = RESERVED_HEADERS
) -> list[str]:
    """Header texts: empty -> ``Column n``; clashes with ``reserved`` -> `` (data)``."""
    taken = {r.lower() for r in reserved}
    out = []
    for i, raw in enumerate(names, start=1):
        text = str(raw) if str(raw).strip() else f"Column {i}"
        out.append(f"{text} (data)" if text.lower() in taken else text)
    return out


# ----------------------------------------------------------------- column plan
@dataclass(frozen=True)
class ColumnPlan:
    name: str
    header: str
    kind: str  # str int float decimal bool date datetime time duration other
    fmt_key: str
    is_amount: bool = False
    tz_aware: bool = False


def _kind_of(dtype: Any) -> str:
    if dtype == pl.Boolean:
        return "bool"
    if dtype.is_integer():
        return "int"
    if dtype.is_float():
        return "float"
    if dtype.is_decimal():
        return "decimal"
    if dtype == pl.String or dtype == pl.Categorical or dtype == pl.Enum:
        return "str"
    if dtype == pl.Date:
        return "date"
    if dtype == pl.Datetime:
        return "datetime"
    if dtype == pl.Time:
        return "time"
    if dtype == pl.Duration:
        return "duration"
    return "other"


def column_plan(
    schema: Mapping[str, Any],
    amount_column: str = "",
    *,
    reserved: Sequence[str] = RESERVED_HEADERS,
) -> list[ColumnPlan]:
    """One :class:`ColumnPlan` per column: cell kind, number format, header text."""
    names = list(schema)
    headers = unique_headers(names, reserved)
    plans = []
    for name, header in zip(names, headers, strict=True):
        dtype = schema[name]
        kind = _kind_of(dtype)
        tz = kind == "datetime" and getattr(dtype, "time_zone", None) is not None
        if kind == "int":
            fmt = "id" if ID_NAME.search(name) else "int"
        elif kind in ("str", "other"):
            fmt = "text"
        elif kind == "decimal":
            fmt = "float"
        else:
            fmt = kind
        if kind == "duration":
            header += " (seconds)"
        plans.append(ColumnPlan(name, header, kind, fmt, name == amount_column, tz))
    return plans


class FormatBook:
    """Workbook formats, created once per (key, quoted) pair."""

    def __init__(self, workbook: Any) -> None:
        self._wb = workbook
        self._cache: dict[tuple[str, bool], Any] = {}

    def get(self, key: str, quoted: bool = False) -> Any:
        return self.custom(key, FORMATS.get(key, {}), quoted)

    def custom(self, name: str, props: Mapping[str, Any], quoted: bool = False) -> Any:
        slot = (name, quoted)
        if slot not in self._cache:
            merged = dict(props)
            if quoted:
                merged["quote_prefix"] = True
            self._cache[slot] = self._wb.add_format(merged)
        return self._cache[slot]


def column_values(series: pl.Series, plan: ColumnPlan) -> list:
    """The Python values of one batch column, ready for :func:`write_value`."""
    if plan.kind == "datetime" and plan.tz_aware:
        series = series.dt.replace_time_zone(None)
    elif plan.kind == "duration":
        series = series.dt.total_microseconds().cast(pl.Float64) / 1e6
    return series.to_list()


def _count(stats: dict[str, int] | None, key: str) -> None:
    if stats is not None:
        stats[key] = stats.get(key, 0) + 1


def write_text(
    ws: Any,
    row: int,
    col: int,
    text: str,
    book: FormatBook,
    base: str = "text",
    stats: dict[str, int] | None = None,
) -> int:
    """Write ``text`` as a string cell (never a formula); danger text is quote-prefixed."""
    text, flags = guard_text(text)
    if flags & FLAG_CONTROL:
        _count(stats, "control")
    if flags & FLAG_SHORTENED:
        _count(stats, "shortened")
    return ws.write_string(row, col, text, book.get(base, needs_quote_prefix(text)))


def write_value(
    ws: Any,
    row: int,
    col: int,
    value: Any,
    kind: str,
    book: FormatBook,
    fmt_key: str,
    stats: dict[str, int] | None = None,
) -> int:
    """Write one value with an explicit call; returns the library's return code."""
    if value is None:
        return ws.write_blank(row, col, None, book.get(fmt_key))
    if isinstance(value, bool):
        return ws.write_boolean(row, col, value, book.get("bool"))
    if isinstance(value, dt.datetime):
        return _write_temporal(ws, row, col, value, "datetime", book, stats)
    if isinstance(value, dt.date):
        return _write_temporal(ws, row, col, value, "date", book, stats)
    if isinstance(value, dt.time):
        return _write_temporal(ws, row, col, value, "time", book, stats)
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, int):
        if abs(value) >= BIG_INT:  # Excel keeps 15 significant digits
            return write_text(ws, row, col, str(value), book, "text", stats)
        return ws.write_number(row, col, value, book.get(fmt_key))
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            text = (
                "NaN"
                if math.isnan(value)
                else ("Infinity" if value > 0 else "-Infinity")
            )
            return ws.write_string(row, col, text, book.get("text"))
        return ws.write_number(row, col, value, book.get(fmt_key))
    text = value if isinstance(value, str) else str(value)
    return write_text(ws, row, col, text, book, "text", stats)


def _write_temporal(ws, row, col, value, key, book, stats) -> int:
    if getattr(value, "year", EXCEL_EPOCH_YEAR) < EXCEL_EPOCH_YEAR:
        return write_text(ws, row, col, value.isoformat(), book, "text", stats)
    return ws.write_datetime(row, col, value, book.get(key))
