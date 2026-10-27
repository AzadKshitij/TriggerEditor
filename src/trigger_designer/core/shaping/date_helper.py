"""Date parts, fiscal periods, day arithmetic and business-day logic."""

from __future__ import annotations

import re
from datetime import date

import polars as pl

from trigger_designer.core.shaping.common import (
    LIVE_SAMPLE_ROWS,
    Frame,
    ShapingError,
    as_lazy,
    require_columns,
    schema_of,
)

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
TWO_DATE_OPS = {
    "days_between",
    "business_days_between",
}
OPS = (
    "weekday_name",
    "weekday_number",
    "is_weekend",
    "is_month_end",
    "quarter",
    "fiscal_year",
    "fiscal_period",
    "fiscal_quarter",
    "days_between",
    "add_days",
    "add_business_days",
    "is_business_day",
    "business_days_between",
)
DEFAULTS = {
    "fiscal_start_month": 1,
    "working_days": list(WEEKDAYS[:5]),
    "holidays": "",
    "date_format": "auto",
    "roll": "forward",
    "ops": [],
}


def _parse_holidays(text: str) -> list[date]:
    values = []
    for token in re.split(r"[\s,;]+", str(text or "")):
        if not token:
            continue
        try:
            values.append(date.fromisoformat(token))
        except ValueError as exc:
            raise ShapingError(
                "TD-SHAPE-052", f"Holiday '{token}' is not YYYY-MM-DD"
            ) from exc
    return sorted(set(values))


def normalize(settings: dict) -> dict:
    s = {**DEFAULTS, **(settings or {})}
    s["fiscal_start_month"] = int(s["fiscal_start_month"])
    if not 1 <= s["fiscal_start_month"] <= 12:
        raise ShapingError("TD-SHAPE-004", "Fiscal start month must be 1-12")
    working = [str(day) for day in (s["working_days"] or [])]
    unknown = [day for day in working if day not in WEEKDAYS]
    if unknown:
        raise ShapingError(
            "TD-SHAPE-004", f"Unknown working day(s): {', '.join(unknown)}"
        )
    if not working:
        raise ShapingError("TD-SHAPE-053", "Pick at least one working day")
    s["working_days"] = working
    s["week_mask"] = [day in working for day in WEEKDAYS]
    s["holidays_parsed"] = _parse_holidays(s["holidays"])
    if s["roll"] not in ("forward", "backward"):
        raise ShapingError("TD-SHAPE-004", "Roll must be forward or backward")
    operations = []
    taken: list[str] = []
    for index, raw in enumerate(s["ops"] or [], start=1):
        op = {
            "op": "weekday_name",
            "source": "",
            "source2": "",
            "n": 0,
            "n_column": "",
            "name": "",
            **(raw or {}),
        }
        kind = op["op"]
        if kind not in OPS:
            raise ShapingError("TD-SHAPE-004", f"Rule {index}: unknown calculation")
        if not op["source"]:
            raise ShapingError("TD-SHAPE-001", f"Rule {index}: pick the date column")
        if kind in TWO_DATE_OPS and not op["source2"]:
            raise ShapingError(
                "TD-SHAPE-001", f"Rule {index}: pick the second date column"
            )
        name = str(op["name"] or "").strip()
        if not name:
            if kind in TWO_DATE_OPS:
                name = f"{op['source']}_to_{op['source2']}_{kind}"
            else:
                name = f"{op['source']}_{kind}"
        if name in taken:
            raise ShapingError(
                "TD-SHAPE-002", f"Duplicate output column '{name}'", [name]
            )
        op["name"] = name
        taken.append(name)
        op["n"] = int(op["n"])
        operations.append(op)
    s["ops"] = operations
    return s


def date_expr(name: str, dtype: pl.DataType, fmt: str) -> pl.Expr:
    column = pl.col(name)
    if dtype == pl.Date:
        return column
    if isinstance(dtype, pl.Datetime):
        return column.dt.date()
    if dtype == pl.String:
        return column.str.to_date(None if fmt == "auto" else fmt, strict=False)
    raise ShapingError("TD-SHAPE-050", f"Column '{name}' is not a date or text", [name])


def _op_expr(
    op: dict, settings: dict, first: pl.Expr, second: pl.Expr | None
) -> pl.Expr:
    kind = op["op"]
    mask = tuple(settings["week_mask"])
    holidays = settings["holidays_parsed"]
    fiscal = int(settings["fiscal_start_month"])
    month = first.dt.month()
    if kind == "weekday_name":
        return first.dt.to_string("%A")
    if kind == "weekday_number":
        return first.dt.weekday().cast(pl.Int64)
    if kind == "is_weekend":
        workdays = [index + 1 for index, active in enumerate(mask) if active]
        return ~first.dt.weekday().is_in(workdays)
    if kind == "is_month_end":
        return first == first.dt.month_end()
    if kind == "quarter":
        return first.dt.quarter().cast(pl.Int64)
    if kind == "fiscal_year":
        bump = (month >= fiscal).cast(pl.Int64) if fiscal != 1 else pl.lit(0, pl.Int64)
        return first.dt.year().cast(pl.Int64) + bump
    if kind == "fiscal_period":
        return ((month - fiscal) % 12 + 1).cast(pl.Int64)
    if kind == "fiscal_quarter":
        return (((month - fiscal) % 12) // 3 + 1).cast(pl.Int64)
    if kind == "days_between":
        return (second - first).dt.total_days()
    n = (
        pl.col(op["n_column"]).cast(pl.Int64, strict=False)
        if op["n_column"]
        else pl.lit(int(op["n"]), pl.Int64)
    )
    if kind == "add_days":
        return first + pl.duration(days=n)
    if kind == "add_business_days":
        return first.dt.add_business_days(
            n,
            week_mask=mask,
            holidays=holidays,
            roll=settings["roll"],
        )
    if kind == "is_business_day":
        return first.dt.is_business_day(week_mask=mask, holidays=holidays)
    return pl.business_day_count(first, second, week_mask=mask, holidays=holidays)


def apply_date_helper(frame: Frame, settings: dict) -> pl.LazyFrame:
    s = normalize(settings)
    lf = as_lazy(frame)
    schema = schema_of(lf)
    sources = [op["source"] for op in s["ops"]]
    sources += [op["source2"] for op in s["ops"] if op["source2"]]
    sources += [op["n_column"] for op in s["ops"] if op["n_column"]]
    require_columns(schema, sources)
    for op in s["ops"]:
        if op["name"] in schema:
            raise ShapingError(
                "TD-SHAPE-002",
                f"Output column '{op['name']}' already exists",
                [op["name"]],
            )
    expressions = []
    for op in s["ops"]:
        first = date_expr(op["source"], schema[op["source"]], s["date_format"])
        second = (
            date_expr(op["source2"], schema[op["source2"]], s["date_format"])
            if op["source2"]
            else None
        )
        expressions.append(_op_expr(op, s, first, second).alias(op["name"]))
    return lf.with_columns(expressions) if expressions else lf


def parse_failures(frame: Frame, settings: dict) -> dict[str, int]:
    s = normalize(settings)
    lf = as_lazy(frame)
    schema = schema_of(lf)
    text_sources = sorted(
        {op["source"] for op in s["ops"] if schema.get(op["source"]) == pl.String}
    )
    if not text_sources:
        return {}
    try:
        head = lf.head(10_000)
        expressions = []
        for name in text_sources:
            parsed = date_expr(name, pl.String, s["date_format"])
            expressions.append(
                (pl.col(name).is_not_null() & parsed.is_null()).sum().alias(name)
            )
        row = head.select(expressions).collect().row(0)
        return {name: int(count) for name, count in zip(text_sources, row) if count}
    except Exception:  # noqa: BLE001
        return {}


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    try:
        failures = parse_failures(frames[0], settings)
    except Exception:  # noqa: BLE001
        return []
    scope = f"first {LIVE_SAMPLE_ROWS} rows"
    return [
        (f"{count:,} unreadable dates in {name} ({scope})", "warning")
        for name, count in failures.items()
    ]


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return [apply_date_helper(frames[0], settings)]
