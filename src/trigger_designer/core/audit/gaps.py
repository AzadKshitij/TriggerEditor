"""Gaps: missing, repeated and out-of-order document numbers; days with no entry.

Qt-free. ``run_gaps(frame, params) -> AuditResult`` returns two lazy frames, the
``Gaps`` findings (one row per gap range, never expanded) and a one-row ``Summary``.
See docs/plan/04-audit-test-nodes.md section 4.2.

Number modes read the sequence as ``<prefix><digits>``; the series is the group
columns plus the prefix. Date mode reads dates and reports the calendar days between
two consecutive distinct dates (optionally skipping weekends and listed holidays).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import polars as pl

from trigger_designer.core.audit.common import (
    ROW,
    AuditConfigError,
    AuditResult,
    ParamsBase,
    as_lazy,
    check_date_format,
    check_range,
    check_reserved,
    date_expr,
    join_and,
    need,
    summary_frame,
    warn_unreadable,
)

MODES = ("number", "prefixed", "date")
FINDINGS = ("gap", "duplicate", "out_of_order", "date_gap")
#: Columns the Gaps output adds; a group column may not use one of these names.
OUTPUT_COLUMNS = ("prefix", "finding", "from", "to", "count", "source_row")
SUMMARY_EXTRAS = (
    "series",
    "gap_ranges",
    "missing_items",
    "duplicate_values",
    "out_of_order_rows",
    "unparseable_rows",
)

_NUM = "__td_num"
_PREFIX = "__td_prefix"
_WIDTH = "__td_width"
_TXT = "__td_txt"
_BAD = "__td_bad"
_DATE = "__td_dt"

_NUMBER_RE = r"^\+?(\d+)(?:\.0+)?$"
_PREFIXED_DIGITS_RE = r"(?s)^.*?(\d+)$"
_PREFIXED_PREFIX_RE = r"(?s)^(.*?)\d+$"


@dataclass
class GapsParams(ParamsBase):
    sequence_column: str = ""
    mode: str = "prefixed"  # "number" | "prefixed" | "date"
    group_columns: list[str] = field(default_factory=list)
    report_duplicates: bool = True  # number / prefixed
    report_out_of_order: bool = True  # number / prefixed
    range_start: int | None = None  # None = lowest seen
    range_end: int | None = None  # None = highest seen
    date_format: str = "%Y-%m-%d"  # date mode
    min_gap_days: int = 1  # date mode: ignore gaps shorter than this
    business_days_only: bool = False  # date mode: Saturday/Sunday not expected
    holidays: list[str] = field(default_factory=list)  # ISO dates, date mode


def parse_holidays(values: list[str]) -> list[dt.date]:
    """``["2024-03-29"]`` -> dates; a bad entry is a configuration error (004)."""
    out: list[dt.date] = []
    for text in values:
        try:
            out.append(dt.date.fromisoformat(str(text).strip()))
        except ValueError:
            raise AuditConfigError(
                "TD-AUDIT-004",
                f"Holiday '{text}' is not a date. Write it as YYYY-MM-DD.",
                field="holidays",
            ) from None
    return out


def validate(schema: dict, p: GapsParams) -> None:
    need(schema, "sequence_column", p.sequence_column, "sequence")
    for name in p.group_columns:
        need(schema, "group_columns", name, "group")
    if p.mode not in MODES:
        raise AuditConfigError(
            "TD-AUDIT-004", "Type must be number, prefixed or date.", field="mode"
        )
    if p.mode == "date":
        check_date_format(p.date_format)
        check_range(
            p.min_gap_days >= 1, "min_gap_days", "Smallest gap", "1 day or more"
        )
        parse_holidays(p.holidays)
    else:
        for field_name, label, value in (
            ("range_start", "Expected first number", p.range_start),
            ("range_end", "Expected last number", p.range_end),
        ):
            check_range(value is None or value >= 0, field_name, label, "0 or more")
        if p.range_start is not None and p.range_end is not None:
            check_range(
                p.range_end >= p.range_start,
                "range_end",
                "Expected last number",
                "not below the first",
            )
    check_reserved(schema, [ROW])
    clash = [c for c in p.group_columns if c in OUTPUT_COLUMNS]
    if clash:
        raise AuditConfigError(
            "TD-AUDIT-005",
            f"Group column '{clash[0]}' has the name of a column this node adds. "
            "Rename it first.",
            field="group_columns",
            columns=(clash[0],),
        )


def criteria_text(p: GapsParams) -> str:
    col = p.sequence_column
    groups = (
        f" separately for each {join_and(p.group_columns)}" if p.group_columns else ""
    )
    if p.mode == "date":
        text = (
            f"{col} is read as a date; days with no entry between the first and "
            f"last date are reported{groups}."
        )
        if p.business_days_only:
            text += " Saturdays and Sundays are not expected."
            if p.holidays:
                text += f" Listed holidays ({len(p.holidays)}) are not expected."
        if p.min_gap_days > 1:
            text += f" Gaps shorter than {p.min_gap_days} days are ignored."
        return text
    reading = (
        "a prefix followed by digits (for example JE-000123)"
        if p.mode == "prefixed"
        else "a whole number"
    )
    text = (
        f"{col} is read as {reading}; numbers missing between the lowest and "
        f"highest value are reported{groups}."
    )
    if p.range_start is not None or p.range_end is not None:
        first = "the lowest seen" if p.range_start is None else f"{p.range_start}"
        last = "the highest seen" if p.range_end is None else f"{p.range_end}"
        text += f" The expected range runs from {first} to {last}."
    also = []
    if p.report_duplicates:
        also.append("repeated numbers")
    if p.report_out_of_order:
        also.append("numbers that appear after a higher number")
    if also:
        text += f" Also reported: {join_and(also)}."
    return text


def _fmt(prefix: pl.Expr, number: pl.Expr, width: pl.Expr) -> pl.Expr:
    """``JE-`` + 124 with width 6 -> ``JE-000124`` (never truncates)."""
    return prefix + number.cast(pl.String).str.zfill(width)


def _findings_frame(
    keys: list[str],
    *,
    prefix: pl.Expr,
    finding: str,
    start: pl.Expr,
    end: pl.Expr,
    count: pl.Expr,
    source_row: pl.Expr,
) -> list[pl.Expr]:
    return [
        *[pl.col(k) for k in keys],
        prefix.alias("prefix"),
        pl.lit(finding).alias("finding"),
        start.alias("from"),
        end.alias("to"),
        count.cast(pl.Int64).alias("count"),
        source_row.cast(pl.UInt32).alias("source_row"),
    ]


# ---- number / prefixed ---------------------------------------------------------
def _number_findings(
    lf: pl.LazyFrame, schema: dict, p: GapsParams
) -> tuple[pl.LazyFrame, pl.LazyFrame]:
    """``(findings, annotated rows)`` for number and prefixed mode."""
    groups = list(p.group_columns)
    text = pl.col(p.sequence_column).cast(pl.String).str.strip_chars()
    text = pl.when(text == "").then(None).otherwise(text)
    lf = lf.with_row_index(ROW).with_columns(text.alias(_TXT))
    txt = pl.col(_TXT)
    if p.mode == "number":
        digits = txt.str.extract(_NUMBER_RE, 1)
        prefix = pl.when(digits.is_not_null()).then(pl.lit(""))
    else:
        digits = txt.str.extract(_PREFIXED_DIGITS_RE, 1)
        prefix = txt.str.extract(_PREFIXED_PREFIX_RE, 1)
    number = digits.cast(pl.Int64, strict=False)
    # Zero padding is only restored for a series that has some: the widest
    # zero-led digit string. A series written 1, 2, ... 12 stays unpadded.
    padded = (
        pl.when(digits.str.starts_with("0") & (digits.str.len_chars() > 1))
        .then(digits.str.len_chars())
        .otherwise(0)
    )
    lf = lf.with_columns(
        number.alias(_NUM),
        pl.when(number.is_not_null()).then(prefix).alias(_PREFIX),
        padded.alias(_WIDTH),
    ).with_columns(
        (pl.col(_TXT).is_not_null() & pl.col(_NUM).is_null()).alias(_BAD),
    )
    keys = [*groups, _PREFIX]
    num, width = pl.col(_NUM), pl.col(_WIDTH)
    valid = lf.filter(num.is_not_null()).with_columns(
        width.max().over(keys).alias(_WIDTH)
    )
    dist = (
        valid.group_by([*keys, _NUM])
        .agg(
            width.first(),
            pl.len().alias("__td_n"),
            pl.col(ROW).min().alias("__td_first"),
        )
        .sort([*keys, _NUM])
    )
    out_keys = [*groups]
    pre = pl.col(_PREFIX)
    parts: list[pl.LazyFrame] = []

    nxt = num.shift(-1).over(keys)
    internal = (
        dist.with_columns(nxt.alias("__td_next"))
        .filter(pl.col("__td_next") - num > 1)
        .select(
            *[pl.col(k) for k in keys],
            width,
            (num + 1).alias("__td_from"),
            (pl.col("__td_next") - 1).alias("__td_to"),
        )
    )
    ends = dist.group_by(keys).agg(
        num.min().alias("__td_lo"), num.max().alias("__td_hi"), width.first()
    )
    gap_sources = [internal]
    if p.range_start is not None:
        gap_sources.append(
            ends.filter(pl.col("__td_lo") > p.range_start).select(
                *[pl.col(k) for k in keys],
                width,
                pl.lit(p.range_start, dtype=pl.Int64).alias("__td_from"),
                (pl.col("__td_lo") - 1).alias("__td_to"),
            )
        )
    if p.range_end is not None:
        gap_sources.append(
            ends.filter(pl.col("__td_hi") < p.range_end).select(
                *[pl.col(k) for k in keys],
                width,
                (pl.col("__td_hi") + 1).alias("__td_from"),
                pl.lit(p.range_end, dtype=pl.Int64).alias("__td_to"),
            )
        )
    f, t = pl.col("__td_from"), pl.col("__td_to")
    parts.append(
        pl.concat(gap_sources).select(
            _findings_frame(
                out_keys,
                prefix=pre,
                finding="gap",
                start=_fmt(pre, f, width),
                end=_fmt(pre, t, width),
                count=t - f + 1,
                source_row=pl.lit(None),
            )
        )
    )
    if p.report_duplicates:
        value = _fmt(pre, num, width)
        parts.append(
            dist.filter(pl.col("__td_n") > 1).select(
                _findings_frame(
                    out_keys,
                    prefix=pre,
                    finding="duplicate",
                    start=value,
                    end=value,
                    count=pl.col("__td_n"),
                    source_row=pl.col("__td_first") + 1,
                )
            )
        )
    if p.report_out_of_order:
        value = _fmt(pre, num, width)
        parts.append(
            valid.with_columns(num.cum_max().shift(1).over(keys).alias("__td_prev"))
            .filter(num < pl.col("__td_prev"))
            .select(
                _findings_frame(
                    out_keys,
                    prefix=pre,
                    finding="out_of_order",
                    start=value,
                    end=value,
                    count=pl.lit(1),
                    source_row=pl.col(ROW) + 1,
                )
            )
        )
    return pl.concat(parts), lf


# ---- date ------------------------------------------------------------------------
def _date_findings(
    lf: pl.LazyFrame, schema: dict, p: GapsParams
) -> tuple[pl.LazyFrame, pl.LazyFrame]:
    groups = list(p.group_columns)
    parsed = date_expr(p.sequence_column, schema[p.sequence_column], p.date_format)
    lf = lf.with_columns(parsed.alias(_DATE)).with_columns(
        (pl.col(p.sequence_column).is_not_null() & pl.col(_DATE).is_null()).alias(_BAD)
    )
    day = pl.col(_DATE)
    dist = (
        lf.filter(day.is_not_null())
        .select(*groups, day)
        .unique()
        .sort([*groups, _DATE])
    )
    nxt = day.shift(-1)
    if groups:
        nxt = nxt.over(groups)
    one = pl.duration(days=1)
    gap = (
        dist.with_columns(nxt.alias("__td_next"))
        .filter(pl.col("__td_next") - day > one)
        .select(
            *[pl.col(g) for g in groups],
            (day + one).alias("__td_from"),
            (pl.col("__td_next") - one).alias("__td_to"),
        )
    )
    f, t = pl.col("__td_from"), pl.col("__td_to")
    if p.business_days_only:
        holidays = parse_holidays(p.holidays)
        gap = gap.with_columns(
            f.dt.add_business_days(0, holidays=holidays, roll="forward"),
            t.dt.add_business_days(0, holidays=holidays, roll="backward"),
        ).with_columns(
            pl.business_day_count(f, t + one, holidays=holidays)
            .clip(lower_bound=0)
            .cast(pl.Int64)
            .alias("__td_count")
        )
    else:
        gap = gap.with_columns((t - f).dt.total_days().add(1).alias("__td_count"))
    gap = gap.filter(pl.col("__td_count") >= p.min_gap_days)
    iso = "%Y-%m-%d"
    findings = gap.select(
        _findings_frame(
            groups,
            prefix=pl.lit(""),
            finding="date_gap",
            start=f.dt.to_string(iso),
            end=t.dt.to_string(iso),
            count=pl.col("__td_count"),
            source_row=pl.lit(None),
        )
    )
    return findings, lf


# ---- run ---------------------------------------------------------------------------
def run_gaps(frame, params: GapsParams) -> AuditResult:
    """Outputs: ``G`` gaps and other findings, ``S`` one-row summary."""
    p = params
    lf = as_lazy(frame)
    schema = lf.collect_schema()
    validate(schema, p)
    groups = list(p.group_columns)
    if p.mode == "date":
        findings, annotated = _date_findings(lf, schema, p)
        readable = pl.col(_DATE).is_not_null()
    else:
        findings, annotated = _number_findings(lf, schema, p)
        readable = pl.col(_NUM).is_not_null()
    findings = findings.sort(
        [*groups, "prefix", "finding", "from"], nulls_last=True, maintain_order=True
    )

    series_keys = groups if p.mode == "date" else [*groups, _PREFIX]
    if series_keys:
        series = pl.struct(series_keys).filter(readable).n_unique()
    else:
        series = readable.any().cast(pl.Int64)
    base = annotated.select(
        pl.len().cast(pl.Int64).alias("population_rows"),
        pl.lit(None, dtype=pl.Float64).alias("population_value"),
        pl.col(_BAD).sum().cast(pl.Int64).alias("unparseable_rows"),
        series.cast(pl.Int64).alias("series"),
    )
    kind = pl.col("finding")
    is_gap = kind.is_in(["gap", "date_gap"])
    counts = findings.select(
        pl.len().cast(pl.Int64).alias("exception_rows"),
        pl.lit(None, dtype=pl.Float64).alias("exception_value"),
        is_gap.sum().cast(pl.Int64).alias("gap_ranges"),
        pl.col("count").filter(is_gap).sum().cast(pl.Int64).alias("missing_items"),
        (kind == "duplicate").sum().cast(pl.Int64).alias("duplicate_values"),
        (kind == "out_of_order").sum().cast(pl.Int64).alias("out_of_order_rows"),
    )
    agg = base.join(counts, how="cross").with_columns(
        pl.col("series", "gap_ranges", "missing_items", "unparseable_rows").fill_null(0)
    )
    status = (
        pl.when(pl.col("exception_rows") > 0)
        .then(pl.lit("fail"))
        .otherwise(pl.lit("pass"))
    )
    if p.mode == "date":
        message = pl.format(
            "{} gap ranges covering {} days.",
            pl.col("gap_ranges"),
            pl.col("missing_items"),
        )
        kind_text = "dates"
    else:
        message = pl.format(
            "{} gap ranges covering {} missing numbers; {} repeated numbers; "
            "{} numbers out of order.",
            pl.col("gap_ranges"),
            pl.col("missing_items"),
            pl.col("duplicate_values"),
            pl.col("out_of_order_rows"),
        )
        kind_text = "numbers"
    status, message, code = warn_unreadable(
        status, message, pl.lit(None, dtype=pl.String), "unparseable_rows", kind_text
    )
    summary = summary_frame(
        agg,
        test_name="Gaps",
        criteria=criteria_text(p),
        parameters=p.to_dict(),
        status=status,
        message=message,
        code=code,
        extras=SUMMARY_EXTRAS,
    )
    return AuditResult(frames=(findings, summary), summary_index=1)
