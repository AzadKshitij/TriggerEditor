"""Benford's Law test: first (or first two) digits of an amount column.

Qt-free. ``run_benford(frame, params)`` counts the leading digits of the tested
amounts in **one streaming pass** that returns at most 91 groups (never the
population), then builds the digit table, the verdict and a lazy drill-down.
See docs/plan/04-audit-test-nodes.md section 4.3 for the definitions.

Live evaluation passes ``row_limit`` so that a very large input is only read up
to that many leading rows; a workflow Run never limits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import polars as pl

from trigger_designer.core.audit.common import (
    AuditResult,
    ParamsBase,
    amount_expr,
    as_lazy,
    check_range,
    check_reserved,
    need,
    summary_frame,
    warn_unreadable,
)

DIGIT_COLUMN = "benford_digits"

#: Mean absolute deviation bands (Nigrini 2012, Table 7.1), upper bound inclusive:
#: ``(close, acceptable, marginal)``; anything above ``marginal`` is nonconforming.
MAD_BANDS: dict[int, tuple[float, float, float]] = {
    1: (0.006, 0.012, 0.015),
    2: (0.0012, 0.0018, 0.0022),
}

#: Below this many tested rows a pass is downgraded to a warning (TD-AUDIT-101).
MIN_TESTED: dict[int, int] = {1: 100, 2: 1000}

#: Two-sided 5 % critical value of the standard normal.
Z_CRITICAL = 1.96

#: Live evaluation reads at most this many leading rows (Run reads them all).
LIVE_ROW_LIMIT = 1_000_000

_CONFORMITY_LABEL = {
    "close": "close",
    "acceptable": "acceptable",
    "marginal": "marginally acceptable",
    "nonconforming": "nonconforming",
}
_STATUS_OF = {
    "close": "pass",
    "acceptable": "pass",
    "marginal": "warn",
    "nonconforming": "fail",
}


@dataclass
class BenfordParams(ParamsBase):
    amount_column: str = ""
    digits: int = 1  # 1 = first digit (9 bins), 2 = first two digits (90 bins)
    min_abs_amount: float = 10.0  # |amount| below this is not tested; zero never is
    drill_auto: bool = True  # drill-down = digits over-represented AND significant
    drill_digits: list = field(default_factory=list)  # used when drill_auto is False


def digit_range(ndig: int) -> range:
    return range(1, 10) if ndig == 1 else range(10, 100)


# ---- chi-square survival function (no scipy) ---------------------------------
def _gser(a: float, x: float) -> float:
    """Regularised lower incomplete gamma P(a, x) by series (x < a + 1)."""
    gln, ap, s = math.lgamma(a), a, 1.0 / a
    d = s
    for _ in range(10000):
        ap += 1
        d *= x / ap
        s += d
        if abs(d) < abs(s) * 1e-16:
            break
    return s * math.exp(-x + a * math.log(x) - gln)


def _gcf(a: float, x: float) -> float:
    """Regularised upper incomplete gamma Q(a, x) by Lentz's fraction (x >= a + 1)."""
    gln, tiny = math.lgamma(a), 1e-300
    b = x + 1 - a
    c, d = 1 / tiny, 1 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < 1e-16:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def chi2_sf(x: float, df: int) -> float:
    """P(chi-square with ``df`` degrees of freedom > ``x``)."""
    if x <= 0:
        return 1.0
    a, xx = df / 2.0, x / 2.0
    return max(0.0, 1.0 - _gser(a, xx)) if xx < a + 1 else min(1.0, _gcf(a, xx))


# ---- digits -------------------------------------------------------------------
def first_digits_expr(amount: pl.Expr, ndig: int) -> pl.Expr:
    """Leading digit (1-9) or two digits (10-99) of ``|amount|`` as Int64.

    ``log10(1000.0)`` is ``2.9999999999999996`` and ``0.3 / 0.1`` is
    ``2.9999999999999996``; the ``1 + 1e-12`` nudge and the renormalisation keep
    exact powers of ten and decimal fractions on the right digit.
    """
    a = amount.abs()
    e = a.log10().floor()
    m = a / pl.lit(10.0).pow(e) * (1 + 1e-12)
    m = pl.when(m >= 10).then(m / 10).when(m < 1).then(m * 10).otherwise(m)
    if ndig == 1:
        return m.floor().clip(1, 9).cast(pl.Int64)
    return (m * 10).floor().clip(10, 99).cast(pl.Int64)


def conformity(mad: float, ndig: int) -> str:
    close, acceptable, marginal = MAD_BANDS[ndig]
    if mad <= close:
        return "close"
    if mad <= acceptable:
        return "acceptable"
    if mad <= marginal:
        return "marginal"
    return "nonconforming"


# ---- table --------------------------------------------------------------------
TABLE_SCHEMA = {
    "digit": pl.Int64,
    "count": pl.Int64,
    "proportion": pl.Float64,
    "expected_proportion": pl.Float64,
    "expected_count": pl.Float64,
    "difference": pl.Float64,
    "z_statistic": pl.Float64,
    "significant": pl.Boolean,
    "chi_square_contribution": pl.Float64,
}


def build_table(counts: dict[int, int], ndig: int) -> pl.DataFrame:
    """The full 9 or 90 row digit table (eager; ``counts`` may miss digits)."""
    digits = list(digit_range(ndig))
    n = sum(counts.get(d, 0) for d in digits)
    base = pl.DataFrame(
        {"digit": digits, "count": [counts.get(d, 0) for d in digits]},
        schema={"digit": pl.Int64, "count": pl.Int64},
    ).with_columns(
        (1 + 1 / pl.col("digit")).log10().alias("expected_proportion"),
    )
    if n == 0:
        return base.with_columns(
            pl.lit(None, dtype=pl.Float64).alias("proportion"),
            (pl.col("expected_proportion") * 0).alias("expected_count"),
            pl.lit(None, dtype=pl.Float64).alias("difference"),
            pl.lit(None, dtype=pl.Float64).alias("z_statistic"),
            pl.lit(False).alias("significant"),
            pl.lit(None, dtype=pl.Float64).alias("chi_square_contribution"),
        ).select(list(TABLE_SCHEMA))
    cc = 1.0 / (2 * n)
    return (
        base.with_columns(
            (pl.col("count") / n).alias("proportion"),
            (pl.col("expected_proportion") * n).alias("expected_count"),
        )
        .with_columns(
            (pl.col("proportion") - pl.col("expected_proportion")).alias("difference")
        )
        .with_columns(
            (
                (
                    pl.col("difference").abs()
                    - pl.when(cc < pl.col("difference").abs()).then(cc).otherwise(0.0)
                )
                / (
                    pl.col("expected_proportion")
                    * (1 - pl.col("expected_proportion"))
                    / n
                ).sqrt()
            ).alias("z_statistic"),
            (
                (pl.col("count") - pl.col("expected_count")) ** 2
                / pl.col("expected_count")
            ).alias("chi_square_contribution"),
        )
        .with_columns((pl.col("z_statistic") > Z_CRITICAL).alias("significant"))
        .select(list(TABLE_SCHEMA))
    )


def table_stats(table: pl.DataFrame, ndig: int) -> dict:
    """MAD, conformity, chi-square, df and p-value of a table (``None`` when n == 0)."""
    n = int(table["count"].sum())
    k = table.height
    stats: dict = {
        "n": n,
        "k": k,
        "df": k - 1,
        "mad": None,
        "conformity": None,
        "chi_square": None,
        "p_value": None,
    }
    if n == 0:
        return stats
    mad = float(table["difference"].abs().sum()) / k
    chi = float(table["chi_square_contribution"].sum())
    stats.update(
        mad=mad,
        conformity=conformity(mad, ndig),
        chi_square=chi,
        p_value=chi2_sf(chi, k - 1),
    )
    return stats


def flagged_digits(table: pl.DataFrame) -> list[int]:
    """Digits that are over-represented and significant (a deficit is only a symptom)."""
    return (
        table.filter(pl.col("significant") & (pl.col("difference") > 0))
        .get_column("digit")
        .to_list()
    )


# ---- chart model --------------------------------------------------------------
@dataclass(frozen=True)
class BenfordChartData:
    digits: tuple[int, ...]
    observed: tuple[float, ...]
    expected: tuple[float, ...]
    flagged: frozenset[int]
    counts: tuple[int, ...]
    z: tuple[float, ...]


def chart_data(table: pl.DataFrame, flagged: list[int]) -> BenfordChartData:
    return BenfordChartData(
        digits=tuple(table["digit"].to_list()),
        observed=tuple(table["proportion"].fill_null(0.0).to_list()),
        expected=tuple(table["expected_proportion"].to_list()),
        flagged=frozenset(int(d) for d in flagged),
        counts=tuple(table["count"].to_list()),
        z=tuple(table["z_statistic"].fill_null(0.0).to_list()),
    )


# ---- the run function ----------------------------------------------------------
def _validate(schema: dict, p: BenfordParams) -> None:
    need(schema, "amount_column", p.amount_column, "amount")
    check_range(
        p.digits in (1, 2), "digits", "Digits", "1 (first digit) or 2 (first two)"
    )
    check_range(p.min_abs_amount >= 0, "min_abs_amount", "Minimum amount", "0 or more")
    if not p.drill_auto:
        valid = set(digit_range(p.digits)) if p.digits in (1, 2) else set()
        bad = [d for d in p.drill_digits if d not in valid]
        check_range(
            not bad,
            "drill_digits",
            "Drill-down digits",
            "between 1 and 9 for the first digit, 10 and 99 for the first two",
        )
    check_reserved(schema, [DIGIT_COLUMN])


def _fmt_rows(n: int) -> str:
    return f"{n:,}"


def run_benford(
    frame, params: BenfordParams, *, row_limit: int | None = None
) -> AuditResult:
    """Outputs: ``T`` digit table, ``S`` one-row summary, ``D`` drill-down rows.

    ``row_limit`` (live evaluation) restricts every output to the first
    ``row_limit`` rows; ``None`` (Run) uses the whole input.
    """
    p = params
    lf = as_lazy(frame)
    schema = lf.collect_schema()
    _validate(schema, p)
    ndig = p.digits
    if row_limit is not None:
        lf = lf.head(row_limit)

    raw = pl.col(p.amount_column)
    parsed = amount_expr(p.amount_column, schema[p.amount_column])
    clean = pl.when(parsed.is_finite()).then(parsed)  # NaN / inf are unreadable
    usable = clean.is_not_null() & (clean != 0) & (clean.abs() >= p.min_abs_amount)
    keyed = lf.with_columns(
        pl.when(usable)
        .then(first_digits_expr(pl.when(usable).then(clean).otherwise(1.0), ndig))
        .otherwise(None)
        .alias(DIGIT_COLUMN),
        clean.abs().alias("__td_abs"),
        (raw.is_not_null() & clean.is_null()).alias("__td_bad"),
    )

    # The only collect: one streaming pass over the data, <= 91 groups out.
    groups = (
        keyed.group_by(DIGIT_COLUMN)
        .agg(
            pl.len().cast(pl.Int64).alias("rows"),
            pl.col("__td_abs").sum().alias("value"),
            pl.col("__td_bad").sum().cast(pl.Int64).alias("bad"),
        )
        .collect(engine="streaming")
    )
    rows_total = int(groups["rows"].sum() or 0)
    unparseable = int(groups["bad"].sum() or 0)
    tested = groups.filter(pl.col(DIGIT_COLUMN).is_not_null())
    counts = dict(zip(tested[DIGIT_COLUMN].to_list(), tested["rows"].to_list()))
    values = dict(zip(tested[DIGIT_COLUMN].to_list(), tested["value"].to_list()))

    table = build_table(counts, ndig)
    stats = table_stats(table, ndig)
    n = stats["n"]
    flagged = flagged_digits(table)
    drill_set = flagged if p.drill_auto else sorted(set(p.drill_digits))

    out_cols = [c for c in schema if c != DIGIT_COLUMN]
    drill = keyed.filter(pl.col(DIGIT_COLUMN).is_in(drill_set)).select(
        [*out_cols, DIGIT_COLUMN]
    )

    # ---- verdict -------------------------------------------------------------
    min_n = MIN_TESTED[ndig]
    code: str | None = None
    if n == 0:
        status = "warn"
        code = "TD-AUDIT-101"
        message = "No row had a usable amount, so nothing was tested."
    else:
        band = stats["conformity"]
        status = _STATUS_OF[band]
        message = (
            f"Mean absolute deviation {stats['mad']:.4f}: "
            f"{_CONFORMITY_LABEL[band]} with Benford's Law "
            f"({_fmt_rows(n)} rows tested, chi-square p-value {stats['p_value']:.4g})."
        )
        if n < min_n:
            code = "TD-AUDIT-101"
            if status == "pass":
                status = "warn"
            message += (
                f" Only {_fmt_rows(n)} rows were tested; at least "
                f"{_fmt_rows(min_n)} are needed for a reliable result."
            )
    limited = row_limit is not None and rows_total >= row_limit
    if limited:
        message += f" Live preview reads the first {_fmt_rows(row_limit)} rows."

    exception_rows = sum(counts.get(d, 0) for d in flagged)
    # The streaming engine adds floats in a varying order; rounding to 1e-6 keeps
    # the gross values identical from run to run (the sums are in currency units).
    exception_value = round(math.fsum(values.get(d) or 0.0 for d in sorted(flagged)), 6)
    population_value = round(math.fsum(values[d] or 0.0 for d in sorted(values)), 6)
    agg = pl.LazyFrame(
        {
            "population_rows": [rows_total],
            "population_value": [population_value],
            "exception_rows": [exception_rows],
            "exception_value": [exception_value],
            "digits": [ndig],
            "tested_rows": [n],
            "mad": [stats["mad"]],
            "conformity": [stats["conformity"]],
            "chi_square": [stats["chi_square"]],
            "chi_square_df": [stats["df"]],
            "p_value": [stats["p_value"]],
            "flagged_digits": [", ".join(str(d) for d in flagged)],
            "unparseable_rows": [unparseable],
        },
        schema={
            "population_rows": pl.Int64,
            "population_value": pl.Float64,
            "exception_rows": pl.Int64,
            "exception_value": pl.Float64,
            "digits": pl.Int64,
            "tested_rows": pl.Int64,
            "mad": pl.Float64,
            "conformity": pl.String,
            "chi_square": pl.Float64,
            "chi_square_df": pl.Int64,
            "p_value": pl.Float64,
            "flagged_digits": pl.String,
            "unparseable_rows": pl.Int64,
        },
    )
    status_e, message_e, code_e = warn_unreadable(
        pl.lit(status),
        pl.lit(message),
        pl.lit(code, dtype=pl.String),
        "unparseable_rows",
        "amounts",
    )
    name = "Benford first digit" if ndig == 1 else "Benford first two digits"
    summary = summary_frame(
        agg,
        test_name=name,
        criteria=(
            f"{'First digit' if ndig == 1 else 'First two digits'} of "
            f"|{p.amount_column}| at least {p.min_abs_amount:g}, compared with Benford's Law."
        ),
        parameters=p.to_dict(),
        status=status_e,
        message=message_e,
        code=code_e,
        extras=(
            "digits",
            "tested_rows",
            "mad",
            "conformity",
            "chi_square",
            "chi_square_df",
            "p_value",
            "flagged_digits",
            "unparseable_rows",
        ),
    )
    return AuditResult(
        frames=(table.lazy(), summary, drill),
        summary_index=1,
        extras={
            "table": table,
            "stats": stats,
            "flagged": flagged,
            "chart": chart_data(table, flagged),
            "unparseable_rows": unparseable,
            "limited": limited,
        },
    )
