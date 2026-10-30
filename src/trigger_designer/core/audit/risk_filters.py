"""Risk Filters: seven journal-entry risk indicators in one pass (Qt-free).

Each switched-on test yields a Boolean that is never null: a null or unreadable
cell fires nothing. An entry flagged by any test goes to **Flagged** with the
labels of the tests that fired and a weighted ``risk_score``; the rest go to
**Not flagged**. Indicators are not misstatements, so the Summary is ``warn``
when something was flagged and never ``fail``.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

import polars as pl

from trigger_designer.core.audit.common import (
    AuditConfigError,
    AuditResult,
    ParamsBase,
    amount_expr,
    as_lazy,
    check_date_format,
    check_range,
    check_reserved,
    date_expr,
    join_and,
    need,
    summary_frame,
    unreadable,
    warn_unreadable,
)

#: ``(id, label)`` in the order the tests are listed, scored and criteria-worded.
TESTS: tuple[tuple[str, str], ...] = (
    ("weekend", "Weekend posting"),
    ("holiday", "Public-holiday posting"),
    ("round_amount", "Round amount"),
    ("just_below_limit", "Just below approval limit"),
    ("keyword", "Keyword in description"),
    ("after_period_end", "Posted after period end"),
    ("manual_journal", "Manual journal"),
)
TEST_IDS = tuple(t for t, _ in TESTS)
LABELS = dict(TESTS)

DEFAULT_MANUAL_VALUES = ["manual", "m", "y", "yes", "true", "1"]
RISK_COLUMNS = ("risk_tests", "risk_score")

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _default_weights() -> dict:
    return dict.fromkeys(TEST_IDS, 1)


@dataclass
class RiskParams(ParamsBase):
    date_column: str = ""
    effective_date_column: str = ""
    amount_column: str = ""
    description_column: str = ""
    manual_column: str = ""
    date_format: str = "%Y-%m-%d"
    weekend: bool = False
    holiday: bool = False
    round_amount: bool = False
    just_below_limit: bool = False
    keyword: bool = False
    after_period_end: bool = False
    manual_journal: bool = False
    holidays: list = field(default_factory=list)
    round_multiple: int = 1000
    approval_limits: list = field(default_factory=list)
    below_pct: float = 2.0
    keywords: list = field(default_factory=list)
    period_end: str = ""
    manual_values: list = field(default_factory=lambda: list(DEFAULT_MANUAL_VALUES))
    weights: dict = field(default_factory=_default_weights)

    def switched_on(self) -> list[str]:
        return [t for t in TEST_IDS if getattr(self, t)]

    def weight(self, test: str) -> int:
        return int(self.weights.get(test, 1))


def _iso_date(text: str, field_name: str) -> dt.date:
    value = str(text).strip()
    try:
        if not _ISO_DATE.match(value):
            raise ValueError(value)
        return dt.date.fromisoformat(value)
    except ValueError:
        raise AuditConfigError(
            "TD-AUDIT-006",
            f"'{value}' is not a date. Use YYYY-MM-DD.",
            field=field_name,
        ) from None


def _validate(schema: dict, p: RiskParams) -> dict:
    """Raise ``AuditConfigError`` in the plan's order; return parsed options."""
    on = p.switched_on()
    if not on:
        raise AuditConfigError(
            "TD-AUDIT-008", "Switch on at least one risk test.", field="weekend"
        )
    opts: dict = {}
    if any(t in on for t in ("weekend", "holiday", "after_period_end")):
        need(schema, "date_column", p.date_column, "posting date")
        check_date_format(p.date_format)
    if p.amount_column or any(t in on for t in ("round_amount", "just_below_limit")):
        need(schema, "amount_column", p.amount_column, "amount")
    if "keyword" in on:
        need(schema, "description_column", p.description_column, "description")
        opts["keywords"] = [k.strip().lower() for k in p.keywords if k.strip()]
        if not opts["keywords"]:
            raise AuditConfigError(
                "TD-AUDIT-004",
                "Keywords must be at least one word.",
                field="keywords",
            )
    if "manual_journal" in on:
        need(schema, "manual_column", p.manual_column, "manual flag")
        opts["manual_values"] = [
            v.strip().lower() for v in p.manual_values if v.strip()
        ]
        check_range(
            bool(opts["manual_values"]),
            "manual_values",
            "Manual values",
            "at least one value",
        )
    if "holiday" in on:
        check_range(bool(p.holidays), "holidays", "Holidays", "at least one date")
        opts["holidays"] = [_iso_date(h, "holidays") for h in p.holidays]
    if "after_period_end" in on:
        opts["period_end"] = _iso_date(p.period_end, "period_end")
        if p.effective_date_column:
            need(schema, "effective_date_column", p.effective_date_column, "effective")
    if "round_amount" in on:
        check_range(
            int(p.round_multiple) >= 1, "round_multiple", "Round multiple", "1 or more"
        )
    if "just_below_limit" in on:
        check_range(
            bool(p.approval_limits) and all(float(x) > 0 for x in p.approval_limits),
            "approval_limits",
            "Approval limits",
            "at least one number above 0",
        )
        check_range(
            0 < float(p.below_pct) < 100, "below_pct", "Within", "above 0 and below 100"
        )
    check_range(
        all(1 <= int(w) <= 10 for w in p.weights.values()),
        "weights",
        "Weights",
        "between 1 and 10",
    )
    check_reserved(schema, list(RISK_COLUMNS))
    return opts


def _num(x: float) -> str:
    return f"{int(x):,}" if float(x) == int(x) else f"{x:,}"


def criteria_text(p: RiskParams) -> str:
    """The Summary's ``criteria`` sentence: only switched-on tests, table order."""
    parts: list[str] = []
    for test in p.switched_on():
        if test == "weekend":
            parts.append(f"posted on a Saturday or Sunday ({p.date_column})")
        elif test == "holiday":
            n = len(p.holidays)
            parts.append(
                f"posted on a listed public holiday ({p.date_column}; "
                f"{n} date{'s' if n != 1 else ''})"
            )
        elif test == "round_amount":
            parts.append(
                f"a round amount: a whole multiple of {int(p.round_multiple):,} "
                f"({p.amount_column})"
            )
        elif test == "just_below_limit":
            limits = ", ".join(_num(x) for x in p.approval_limits)
            parts.append(
                f"an amount within {p.below_pct:g}% below an approval limit ({limits})"
            )
        elif test == "keyword":
            words = join_and([f"'{k}'" for k in p.keywords if k.strip()])
            parts.append(f"a description containing {words}")
        elif test == "after_period_end":
            text = f"posted after the period end {p.period_end}"
            if p.effective_date_column:
                text += (
                    f", with an effective date on or before it "
                    f"({p.effective_date_column})"
                )
            parts.append(text)
        elif test == "manual_journal":
            parts.append(
                f"a manual journal ({p.manual_column} is one of "
                f"{', '.join(v for v in p.manual_values if v.strip())})"
            )
    return "Entries are flagged when any of these apply: " + "; ".join(parts) + "."


def _text(name: str, dtype: pl.DataType) -> pl.Expr:
    return pl.col(name) if dtype == pl.String else pl.col(name).cast(pl.String)


def run_risk_filters(frame, params: RiskParams) -> AuditResult:
    """Outputs: ``F`` Flagged, ``N`` Not flagged, ``S`` one-row Summary."""
    p = params
    lf = as_lazy(frame)
    schema = lf.collect_schema()
    opts = _validate(schema, p)
    on = p.switched_on()
    originals = list(schema.names())

    need_date = any(t in on for t in ("weekend", "holiday", "after_period_end"))
    use_eff = "after_period_end" in on and bool(p.effective_date_column)
    prep: list[pl.Expr] = []
    bad: list[str] = []

    if p.amount_column:
        parsed = amount_expr(p.amount_column, schema[p.amount_column])
        parsed = pl.when(parsed.is_finite()).then(parsed)  # inf / NaN read as null
        prep += [
            parsed.alias("__td_amt"),
            unreadable(p.amount_column, parsed).alias("__td_bad_amt"),
        ]
        bad.append("__td_bad_amt")
    if need_date:
        d = date_expr(p.date_column, schema[p.date_column], p.date_format)
        prep += [d.alias("__td_date"), unreadable(p.date_column, d).alias("__td_bad_d")]
        bad.append("__td_bad_d")
    if use_eff:
        e = date_expr(
            p.effective_date_column, schema[p.effective_date_column], p.date_format
        )
        prep += [
            e.alias("__td_eff"),
            unreadable(p.effective_date_column, e).alias("__td_bad_e"),
        ]
        bad.append("__td_bad_e")
    lf = lf.with_columns(prep)

    date = pl.col("__td_date")
    cents = (pl.col("__td_amt").abs() * 100).round(0).cast(pl.Int64, strict=False)
    flags: dict[str, pl.Expr] = {}
    for test in on:
        if test == "weekend":
            flags[test] = date.dt.weekday() >= 6
        elif test == "holiday":
            flags[test] = date.is_in(
                pl.Series(opts["holidays"], dtype=pl.Date).implode()
            )
        elif test == "round_amount":
            flags[test] = (cents > 0) & (cents % (int(p.round_multiple) * 100) == 0)
        elif test == "just_below_limit":
            flags[test] = pl.any_horizontal(
                [
                    (cents >= round(lim * 100 * (1 - p.below_pct / 100)))
                    & (cents < round(lim * 100))
                    for lim in map(float, p.approval_limits)
                ]
            )
        elif test == "keyword":
            text = _text(p.description_column, schema[p.description_column])
            text = text.str.to_lowercase()
            flags[test] = pl.any_horizontal(
                [text.str.contains(k, literal=True) for k in opts["keywords"]]
            )
        elif test == "after_period_end":
            cond = date > pl.lit(opts["period_end"])
            if use_eff:
                cond = cond & (pl.col("__td_eff") <= pl.lit(opts["period_end"]))
            flags[test] = cond
        elif test == "manual_journal":
            value = (
                _text(p.manual_column, schema[p.manual_column])
                .str.strip_chars()
                .str.to_lowercase()
            )
            flags[test] = value.is_in(opts["manual_values"])
    flags = {k: v.fill_null(False) for k, v in flags.items()}

    score = sum(
        (flags[t].cast(pl.Int64) * p.weight(t) for t in on),
        pl.lit(0, dtype=pl.Int64),
    )
    fired = sum((flags[t].cast(pl.Int64) for t in on), pl.lit(0, dtype=pl.Int64))
    tests = pl.concat_str(
        [pl.when(flags[t]).then(pl.lit(LABELS[t])) for t in on],
        separator="; ",
        ignore_nulls=True,
    )
    lf = lf.with_columns(
        *[f.alias(f"__td_f_{t}") for t, f in flags.items()],
        score.alias("risk_score"),
        fired.alias("__td_n"),
        tests.alias("risk_tests"),
    )
    hit = pl.col("risk_score") > 0

    amount = pl.col("__td_amt").abs() if p.amount_column else pl.lit(None, pl.Float64)
    bad_cells = (
        pl.sum_horizontal([pl.col(b).cast(pl.Int64) for b in bad])
        if bad
        else pl.lit(0, dtype=pl.Int64)
    )
    counts = [
        (
            pl.col(f"__td_f_{t}").sum().cast(pl.Int64)
            if t in on
            else pl.lit(None, dtype=pl.Int64)
        ).alias(f"n_{t}")
        for t in TEST_IDS
    ]
    agg = lf.select(
        pl.len().cast(pl.Int64).alias("population_rows"),
        amount.sum().alias("population_value")
        if p.amount_column
        else pl.lit(None, pl.Float64).alias("population_value"),
        hit.sum().cast(pl.Int64).alias("exception_rows"),
        (
            amount.filter(hit).sum() if p.amount_column else pl.lit(None, pl.Float64)
        ).alias("exception_value"),
        (pl.col("__td_n") >= 2).sum().cast(pl.Int64).alias("flagged_two_or_more"),
        pl.col("risk_score").sum().cast(pl.Int64).alias("total_score"),
        bad_cells.sum().cast(pl.Int64).alias("unparseable_rows"),
        *counts,
    )
    status = (
        pl.when(pl.col("exception_rows") > 0)
        .then(pl.lit("warn"))
        .otherwise(pl.lit("pass"))
    )
    message = pl.format(
        "{} of {} entries were flagged by at least one risk test.",
        pl.col("exception_rows"),
        pl.col("population_rows"),
    )
    status, message, code = warn_unreadable(
        status,
        message,
        pl.lit(None, dtype=pl.String),
        "unparseable_rows",
        "dates or amounts",
    )
    summary = summary_frame(
        agg,
        test_name="Risk Filters",
        criteria=criteria_text(p),
        parameters=p.to_dict(),
        status=status,
        message=message,
        code=code,
        extras=("flagged_two_or_more", "total_score", "unparseable_rows")
        + tuple(f"n_{t}" for t in TEST_IDS),
    )
    return AuditResult(
        frames=(
            lf.filter(hit).select(*originals, "risk_tests", "risk_score"),
            lf.filter(~hit).select(*originals),
            summary,
        ),
        summary_index=2,
    )
