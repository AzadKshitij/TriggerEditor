"""Duplicates audit test (docs/plan/04-audit-test-nodes.md section 4.1). Qt-free.

*Exact*: rows whose key columns are equal. *Near*: key columns equal **and**, when
chosen, amounts within a tolerance and dates within a window of days.

Near matching clusters one dimension at a time (key, then date, then amount) on a
sorted frame, so it is O(N log N) and cannot blow up on a coarse key. Every pair
that satisfies *both* thresholds lands in the same group; a group can also hold
rows linked only through a chain of in-tolerance neighbours.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

from trigger_designer.core.audit.common import (
    ROW,
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
    key_expr,
    need,
    need_many,
    summary_frame,
    unreadable,
    warn_unreadable,
)

__all__ = ["DuplicatesParams", "run_duplicates"]

TEST_NAME = "Duplicates"
GROUP_COLUMN = "dup_group_id"
COUNT_COLUMN = "dup_count"
MODES = ("exact", "near")
TOLERANCE_KINDS = ("absolute", "percent")
#: Absorbs float noise so 100.00 vs 100.50 at tolerance 0.5 still groups.
_EPSILON = 1e-9


@dataclass
class DuplicatesParams(ParamsBase):
    key_columns: list = field(default_factory=list)
    mode: str = "exact"  # "exact" | "near"
    trim_text: bool = True  # trailing spaces are the commonest false negative
    ignore_case: bool = False  # case can be meaningful in IDs
    amount_column: str = ""  # near
    tolerance_kind: str = "absolute"  # "absolute" | "percent" (of the larger |amount|)
    tolerance: float = 0.0
    date_column: str = ""  # near
    date_format: str = "%Y-%m-%d"  # ignored when the column is Date/Datetime
    window_days: int = 0
    value_column: str = ""  # optional Summary value; near mode falls back to amount


def validate(schema: dict, p: DuplicatesParams) -> None:
    """Raise the first configuration problem (order: plan 4.1 table)."""
    need_many(schema, "key_columns", list(p.key_columns), "key")
    if p.mode not in MODES:
        raise AuditConfigError(
            "TD-AUDIT-004", "Match type must be exact or near.", field="mode"
        )
    near = p.mode == "near"
    if near:
        for name, label in (("amount_column", "amount"), ("date_column", "date")):
            if getattr(p, name):
                need(schema, name, getattr(p, name), label)
        if not p.amount_column and not p.date_column:
            raise AuditConfigError(
                "TD-AUDIT-001",
                "Choose the amount column or the date column for near matching.",
                field="amount_column",
            )
    if p.value_column:
        need(schema, "value_column", p.value_column, "value")
    check_range(
        p.tolerance == p.tolerance and p.tolerance >= 0,
        "tolerance",
        "Tolerance",
        "0 or more",
    )
    check_range(
        p.tolerance_kind in TOLERANCE_KINDS,
        "tolerance_kind",
        "Tolerance type",
        "absolute or percent",
    )
    check_range(p.window_days >= 0, "window_days", "Window", "0 days or more")
    check_date_format(p.date_format)
    check_reserved(
        schema,
        [GROUP_COLUMN, COUNT_COLUMN] + [c for c in schema if c.startswith("__td_")],
    )


def _number(name: str, dtype: pl.DataType) -> pl.Expr:
    """Amount as Float64; NaN and infinity count as unreadable (null)."""
    parsed = amount_expr(name, dtype)
    return pl.when(parsed.is_finite()).then(parsed)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def criteria_text(p: DuplicatesParams) -> str:
    keys = join_and(list(p.key_columns))
    notes = []
    if p.trim_text:
        notes.append("spaces around text trimmed")
    notes.append("upper/lower case ignored" if p.ignore_case else "case-sensitive")
    tail = f" ({', '.join(notes)})."
    if p.mode != "near":
        return f"Rows with the same {keys} are duplicates{tail}"
    clauses = []
    if p.amount_column:
        if p.tolerance_kind == "percent":
            limit = f"{p.tolerance:g}%"
        else:
            limit = f"{p.tolerance:,.2f}"
        clauses.append(f"whose {p.amount_column} differs by at most {limit}")
    if p.date_column:
        days = _plural(int(p.window_days), "day")
        clauses.append(f"whose {p.date_column} differs by at most {days}")
    return (
        f"Rows with the same {keys} {' and '.join(clauses)} are near-duplicates{tail}"
    )


def _near_groups(
    lf: pl.LazyFrame, p: DuplicatesParams, kc: list[str], has_a: bool, has_d: bool
) -> pl.LazyFrame:
    """``ROW`` + ``__td_gid`` for every eligible row (hierarchical 1-D clustering)."""
    part = lf.filter(pl.col("__td_elig")).sort(
        kc + (["__td_dt"] if has_d else []) + [ROW]
    )
    part = part.with_columns(pl.struct(kc).rle_id().alias("__td_p"))
    cluster = pl.col("__td_p")
    if has_d:
        # New date cluster when the key run changes or the day gap exceeds the window.
        gap = pl.col("__td_dt").diff().dt.total_days()
        new_d = (pl.col("__td_p") != pl.col("__td_p").shift(1)).fill_null(True) | (
            gap > p.window_days
        ).fill_null(True)
        part = part.with_columns(new_d.cum_sum().alias("__td_c1"))
        cluster = pl.col("__td_c1")
    if has_a:
        part = part.sort(
            ["__td_p"] + (["__td_c1"] if has_d else []) + ["__td_amt", ROW]
        )
        prev = pl.col("__td_amt").shift(1)
        if p.tolerance_kind == "percent":
            limit = (
                pl.max_horizontal(pl.col("__td_amt").abs(), prev.abs())
                * (p.tolerance / 100.0)
                + _EPSILON
            )
        else:
            limit = pl.lit(p.tolerance + _EPSILON)
        new_a = (cluster != cluster.shift(1)).fill_null(True) | (
            (pl.col("__td_amt") - prev) > limit
        ).fill_null(True)
        part = part.with_columns(new_a.cum_sum().alias("__td_gid"))
    else:
        part = part.with_columns(cluster.alias("__td_gid"))
    return part.select(ROW, "__td_gid")


def run_duplicates(frame, params: DuplicatesParams) -> AuditResult:
    """Outputs: ``Duplicates``, ``Unique`` and a one-row ``Summary``."""
    p = params
    lf = as_lazy(frame)
    schema = lf.collect_schema()
    validate(schema, p)
    originals = schema.names()
    near = p.mode == "near"
    has_a = near and bool(p.amount_column)
    has_d = near and bool(p.date_column)
    kc = [f"__td_k{i}" for i in range(len(p.key_columns))]

    lf = lf.with_row_index(ROW)
    derived = [
        key_expr(name, schema[name], p.trim_text, p.ignore_case).alias(alias)
        for name, alias in zip(p.key_columns, kc)
    ]
    if has_a:
        derived.append(
            _number(p.amount_column, schema[p.amount_column]).alias("__td_amt")
        )
    if has_d:
        derived.append(
            date_expr(p.date_column, schema[p.date_column], p.date_format).alias(
                "__td_dt"
            )
        )
    value_name = ""
    if p.value_column and not (has_a and p.value_column == p.amount_column):
        derived.append(
            _number(p.value_column, schema[p.value_column]).alias("__td_val")
        )
        value_name = "__td_val"
    elif p.value_column or has_a:
        value_name = "__td_amt"
    lf = lf.with_columns(*derived)

    eligible = pl.all_horizontal(*[pl.col(k).is_not_null() for k in kc])
    bad_parts = []
    if has_a:
        eligible = eligible & pl.col("__td_amt").is_not_null()
        bad_parts.append(unreadable(p.amount_column, pl.col("__td_amt")))
    if has_d:
        eligible = eligible & pl.col("__td_dt").is_not_null()
        bad_parts.append(unreadable(p.date_column, pl.col("__td_dt")))
    bad = pl.any_horizontal(*bad_parts) if bad_parts else pl.lit(False)
    lf = lf.with_columns(eligible.alias("__td_elig"), bad.alias("__td_bad"))

    if near:
        groups = _near_groups(lf, p, kc, has_a, has_d)
        lf = lf.join(groups, on=ROW, how="left", maintain_order="left")
        gid = pl.col("__td_gid")
        count = pl.when(gid.is_not_null()).then(pl.len().over("__td_gid")).otherwise(1)
        first = (
            pl.when(gid.is_not_null())
            .then(pl.col(ROW).min().over("__td_gid"))
            .otherwise(pl.col(ROW))
        )
    else:
        elig = pl.col("__td_elig")
        count = pl.when(elig).then(pl.len().over(kc)).otherwise(1)
        first = pl.when(elig).then(pl.col(ROW).min().over(kc)).otherwise(pl.col(ROW))
    lf = lf.with_columns(
        count.cast(pl.Int64).alias("__td_cnt"), first.cast(pl.Int64).alias("__td_first")
    )
    flagged = pl.col("__td_cnt") > 1

    duplicates = (
        lf.filter(flagged)
        .with_columns(
            pl.col("__td_first").rank("dense").cast(pl.Int64).alias(GROUP_COLUMN),
            pl.col("__td_cnt").alias(COUNT_COLUMN),
        )
        .sort([GROUP_COLUMN, ROW])
        .select(originals + [GROUP_COLUMN, COUNT_COLUMN])
    )
    unique = lf.filter(~flagged).sort(ROW).select(originals)

    if value_name:
        value = pl.col(value_name).abs()
        population_value = value.sum().cast(pl.Float64)
        exception_value = value.filter(flagged).sum().cast(pl.Float64)
    else:
        population_value = pl.lit(None, dtype=pl.Float64)
        exception_value = pl.lit(None, dtype=pl.Float64)
    agg = lf.select(
        pl.len().cast(pl.Int64).alias("population_rows"),
        population_value.alias("population_value"),
        flagged.sum().cast(pl.Int64).alias("exception_rows"),
        exception_value.alias("exception_value"),
        pl.col("__td_first").filter(flagged).n_unique().cast(pl.Int64).alias("groups"),
        (~pl.col("__td_elig")).sum().cast(pl.Int64).alias("skipped_rows"),
        pl.col("__td_bad").sum().cast(pl.Int64).alias("unparseable_rows"),
    )
    status = (
        pl.when(pl.col("exception_rows") > 0)
        .then(pl.lit("fail"))
        .otherwise(pl.lit("pass"))
    )
    message = pl.format(
        "{} of {} rows are in {} duplicate {}.",
        pl.col("exception_rows"),
        pl.col("population_rows"),
        pl.col("groups"),
        pl.when(pl.col("groups") == 1)
        .then(pl.lit("group"))
        .otherwise(pl.lit("groups")),
    )
    status, message, code = warn_unreadable(
        status,
        message,
        pl.lit(None, dtype=pl.String),
        "unparseable_rows",
        "numbers or dates",
    )
    summary = summary_frame(
        agg,
        test_name=TEST_NAME,
        criteria=criteria_text(p),
        parameters=p.to_dict(),
        status=status,
        message=message,
        code=code,
        extras=("groups", "skipped_rows", "unparseable_rows"),
    )
    return AuditResult(frames=(duplicates, unique, summary), summary_index=2)
