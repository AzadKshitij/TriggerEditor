"""Reconcile two frames: deterministic tolerance matching with four outputs."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from trigger_designer.core.shaping.assign import greedy_one_to_one
from trigger_designer.core.shaping.common import (
    Frame,
    ShapingError,
    as_lazy,
    estimate_pairs,
    require_columns,
    schema_of,
    unique_name,
)
from trigger_designer.core.utils.amounts import amount_expr

MAX_CANDIDATE_PAIRS = 5_000_000
MATCH_TYPES = ("one_to_one", "one_to_many", "many_to_one", "many_to_many")
DEFAULTS = {
    "match_type": "one_to_one",
    "key_pairs": [],
    "amount_left": "",
    "amount_right": "",
    "tolerance_mode": "absolute",
    "tolerance": 0.0,
    "date_left": "",
    "date_right": "",
    "date_window_days": 0,
}
PAIR_COLUMNS = [
    "__mid",
    "__l",
    "__r",
    "__diff",
    "__gap",
    "__within",
    "Match_Status",
]
SUMMARY = {
    "Match_Type": pl.String,
    "Left_Rows": pl.Int64,
    "Right_Rows": pl.Int64,
    "Matched_Groups": pl.Int64,
    "Left_Matched_Rows": pl.Int64,
    "Right_Matched_Rows": pl.Int64,
    "Left_Unmatched_Rows": pl.Int64,
    "Right_Unmatched_Rows": pl.Int64,
    "Left_Match_Rate_Pct": pl.Float64,
    "Right_Match_Rate_Pct": pl.Float64,
    "Left_Total": pl.Float64,
    "Right_Total": pl.Float64,
    "Matched_Left_Total": pl.Float64,
    "Matched_Right_Total": pl.Float64,
    "Matched_Net_Difference": pl.Float64,
    "Matched_Abs_Difference": pl.Float64,
    "Left_Unmatched_Total": pl.Float64,
    "Right_Unmatched_Total": pl.Float64,
    "Net_Difference_Total": pl.Float64,
    "Within_Tolerance_Groups": pl.Int64,
    "Outside_Tolerance_Groups": pl.Int64,
}


@dataclass
class ReconcileResult:
    matched: pl.DataFrame
    left_unmatched: pl.DataFrame
    right_unmatched: pl.DataFrame
    summary: pl.DataFrame


def normalize(settings: dict) -> dict:
    s = {**DEFAULTS, **(settings or {})}
    if s["match_type"] not in MATCH_TYPES:
        raise ShapingError("TD-SHAPE-004", f"Unknown match type {s['match_type']!r}")
    if s["tolerance_mode"] not in ("absolute", "percent"):
        raise ShapingError("TD-SHAPE-004", "Tolerance mode must be absolute or percent")
    s["tolerance"] = float(s["tolerance"])
    s["date_window_days"] = int(s["date_window_days"])
    if s["tolerance"] < 0 or s["date_window_days"] < 0:
        raise ShapingError(
            "TD-SHAPE-004", "Tolerance and date window cannot be negative"
        )
    s["key_pairs"] = [
        pair
        for pair in (s["key_pairs"] or [])
        if pair.get("left") and pair.get("right")
    ]
    if bool(s["amount_left"]) != bool(s["amount_right"]) or bool(
        s["date_left"]
    ) != bool(s["date_right"]):
        raise ShapingError("TD-SHAPE-070", "Pick the amount/date column on both sides")
    s["has_amount"] = bool(s["amount_left"])
    s["has_date"] = bool(s["date_left"]) and s["match_type"] != "many_to_many"
    if not s["key_pairs"] and not s["has_date"]:
        raise ShapingError("TD-SHAPE-071", "Add a key column pair or a date window")
    return s


def _date_int(name: str, dtype: pl.DataType) -> pl.Expr:
    column = pl.col(name)
    if dtype == pl.String:
        column = column.str.to_date(strict=False)
    elif isinstance(dtype, pl.Datetime):
        column = column.dt.date()
    elif dtype != pl.Date:
        raise ShapingError("TD-SHAPE-050", f"Column '{name}' is not a date", [name])
    return column.cast(pl.Int32)


def _slim(frame: pl.DataFrame, side: str, s: dict) -> pl.DataFrame:
    side_name = "left" if side == "l" else "right"
    schema = dict(frame.schema)
    columns = [pl.col(f"__{side}")]
    for index, pair in enumerate(s["key_pairs"]):
        columns.append(
            pl.col(pair[side_name])
            .cast(pl.String)
            .str.strip_chars()
            .str.to_lowercase()
            .alias(f"__k{index}")
        )
    if s[f"amount_{side_name}"]:
        columns.append(
            amount_expr(
                s[f"amount_{side_name}"], schema[s[f"amount_{side_name}"]]
            ).alias(f"__{side}a")
        )
    if s[f"date_{side_name}"] and s["has_date"]:
        columns.append(
            _date_int(s[f"date_{side_name}"], schema[s[f"date_{side_name}"]]).alias(
                f"__{side}d"
            )
        )
    return frame.select(columns)


def _guard(count: int) -> None:
    if count > MAX_CANDIDATE_PAIRS:
        raise ShapingError(
            "TD-SHAPE-072",
            f"{count:,} possible matches (limit {MAX_CANDIDATE_PAIRS:,}); "
            "add a key column or narrow the date window",
        )


def _candidates(ls: pl.DataFrame, rs: pl.DataFrame, s: dict) -> pl.DataFrame:
    keys = [f"__k{index}" for index in range(len(s["key_pairs"]))]
    if keys:
        _guard(estimate_pairs(ls, rs, keys))
        return ls.join(rs, on=keys, how="inner")
    size = max(s["date_window_days"], 1)
    probes = pl.DataFrame({"__off": [-1, 0, 1]}, schema={"__off": pl.Int32})
    left_buckets = ls.filter(pl.col("__ld").is_not_null()).join(probes, how="cross")
    left_buckets = left_buckets.with_columns(
        (pl.col("__ld").floordiv(size) + pl.col("__off")).alias("__b")
    ).drop("__off")
    right_buckets = rs.filter(pl.col("__rd").is_not_null()).with_columns(
        pl.col("__rd").floordiv(size).alias("__b")
    )
    _guard(estimate_pairs(left_buckets, right_buckets, ["__b"]))
    return left_buckets.join(right_buckets, on="__b", how="inner").drop("__b")


def _within(diff: pl.Expr, base: pl.Expr, s: dict) -> pl.Expr:
    limit = (
        pl.lit(s["tolerance"])
        if s["tolerance_mode"] == "absolute"
        else base.abs() * s["tolerance"] / 100.0
    )
    return (diff.abs().round(6) <= limit.round(6)).fill_null(False)


def _metrics(cand: pl.DataFrame, s: dict) -> pl.DataFrame:
    columns = []
    if s["has_amount"]:
        diff = pl.col("__ra") - pl.col("__la")
        columns += [
            diff.round(6).alias("__diff"),
            diff.abs().alias("__adiff"),
            _within(diff, pl.col("__la"), s).alias("__amt_ok"),
        ]
    else:
        columns += [
            pl.lit(None, pl.Float64).alias("__diff"),
            pl.lit(0.0).alias("__adiff"),
            pl.lit(True).alias("__amt_ok"),
        ]
    if s["has_date"]:
        gap = (pl.col("__rd") - pl.col("__ld")).cast(pl.Int64)
        columns += [
            gap.alias("__gap"),
            gap.abs().alias("__agap"),
            (gap.abs() <= s["date_window_days"]).fill_null(False).alias("__date_ok"),
        ]
    else:
        columns += [
            pl.lit(None, pl.Int64).alias("__gap"),
            pl.lit(0, pl.Int64).alias("__agap"),
            pl.lit(True).alias("__date_ok"),
        ]
    return cand.with_columns(columns)


def _status(s: dict) -> pl.Expr:
    if not s["has_amount"]:
        return pl.lit("Matched").alias("Match_Status")
    return (
        pl.when(pl.col("__within"))
        .then(pl.lit("Within tolerance"))
        .otherwise(pl.lit("Outside tolerance"))
        .alias("Match_Status")
    )


def _pairs_one_to_one(cand: pl.DataFrame, s: dict) -> pl.DataFrame:
    ok = cand.filter(pl.col("__amt_ok") & pl.col("__date_ok")).sort(
        ["__adiff", "__agap", "__l", "__r"]
    )
    taken = greedy_one_to_one(ok).sort("__l").with_row_index("__mid", offset=1)
    return taken.select(
        pl.col("__mid").cast(pl.Int64),
        "__l",
        "__r",
        "__diff",
        "__gap",
        pl.lit(True).alias("__within"),
        pl.lit("Within tolerance" if s["has_amount"] else "Matched").alias(
            "Match_Status"
        ),
    )


def _pairs_one_to_many(cand: pl.DataFrame, s: dict) -> pl.DataFrame:
    many = "r" if s["match_type"] == "one_to_many" else "l"
    one = "l" if many == "r" else "r"
    ok = cand.filter(pl.col("__date_ok")).sort(["__agap", f"__{one}", f"__{many}"])
    pairs = ok.unique(f"__{many}", keep="first", maintain_order=True).sort(
        [f"__{one}", f"__{many}"]
    )
    pairs = pairs.with_columns(
        pl.col(f"__{one}").rank("dense").cast(pl.Int64).alias("__mid")
    )
    if s["has_amount"]:
        one_amount = pl.col(f"__{one}a").first()
        many_sum = pl.col(f"__{many}a").sum()
        groups = pairs.group_by("__mid").agg(
            one_amount.alias("__o"), many_sum.alias("__m")
        )
        sign = 1.0 if one == "l" else -1.0
        groups = groups.with_columns(
            ((pl.col("__m") - pl.col("__o")) * sign + 0.0).round(6).alias("__diff"),
            _within(pl.col("__m") - pl.col("__o"), pl.col("__o"), s).alias("__within"),
        )
        pairs = pairs.drop("__diff").join(
            groups.select("__mid", "__diff", "__within"), on="__mid"
        )
    else:
        pairs = pairs.with_columns(
            pl.lit(None, pl.Float64).alias("__diff"),
            pl.lit(True).alias("__within"),
        )
    return pairs.with_columns(_status(s)).select(PAIR_COLUMNS)


def _pairs_many_to_many(ls: pl.DataFrame, rs: pl.DataFrame, s: dict) -> pl.DataFrame:
    keys = [f"__k{index}" for index in range(len(s["key_pairs"]))]
    left_amount = pl.col("__la").sum() if s["has_amount"] else pl.lit(0.0)
    right_amount = pl.col("__ra").sum() if s["has_amount"] else pl.lit(0.0)
    groups = ls.group_by(keys).agg(
        pl.col("__l").min().alias("__lmin"), left_amount.alias("__gla")
    )
    groups = groups.join(
        rs.group_by(keys).agg(right_amount.alias("__gra")), on=keys, how="inner"
    )
    groups = groups.sort("__lmin").with_row_index("__mid", offset=1)
    diff = pl.col("__gra") - pl.col("__gla")
    groups = groups.with_columns(
        pl.col("__mid").cast(pl.Int64),
        (diff.round(6) if s["has_amount"] else pl.lit(None, pl.Float64)).alias(
            "__diff"
        ),
        (_within(diff, pl.col("__gla"), s) if s["has_amount"] else pl.lit(True)).alias(
            "__within"
        ),
    )
    group_keys = groups.select(keys + ["__mid", "__diff", "__within"])
    left_matched = (
        ls.join(group_keys, on=keys)
        .select("__l", "__mid", "__diff", "__within")
        .sort("__mid", "__l")
    )
    right_matched = (
        rs.join(group_keys, on=keys).select("__r", "__mid").sort("__mid", "__r")
    )
    left_matched = left_matched.with_columns(
        pl.int_range(pl.len()).over("__mid").alias("__i")
    )
    right_matched = right_matched.with_columns(
        pl.int_range(pl.len()).over("__mid").alias("__i")
    )
    pairs = left_matched.join(
        right_matched, on=["__mid", "__i"], how="full", coalesce=True
    ).sort("__mid", "__i")
    pairs = pairs.with_columns(
        pl.col("__diff").forward_fill().over("__mid"),
        pl.col("__within").forward_fill().over("__mid"),
        pl.lit(None, pl.Int64).alias("__gap"),
    )
    return pairs.with_columns(_status(s)).select(PAIR_COLUMNS)


def _unmatched(
    frame: pl.DataFrame,
    side: str,
    used: pl.Series,
    key_hit: pl.Series,
    ok_hit: pl.Series,
    s: dict,
) -> pl.DataFrame:
    position = f"__{side}"
    no_candidate = (
        "No candidate with the same key"
        if s["key_pairs"]
        else "No candidate within the date window"
    )
    reason = (
        pl.when(~pl.col(position).is_in(key_hit.implode()))
        .then(pl.lit(no_candidate))
        .when(~pl.col(position).is_in(ok_hit.implode()))
        .then(pl.lit("Candidates outside tolerance"))
        .otherwise(pl.lit("Candidates already matched"))
        .alias("Unmatched_Reason")
    )
    return (
        frame.filter(~pl.col(position).is_in(used.implode()))
        .with_columns(reason)
        .drop(position)
    )


def _sum_amount(frame: pl.DataFrame, column: str) -> float | None:
    if not column or column not in frame.columns:
        return 0.0
    try:
        return float(
            frame.select(amount_expr(column, frame.schema[column]).sum()).item() or 0.0
        )
    except Exception:  # noqa: BLE001
        return 0.0


def _summary(
    left: pl.DataFrame,
    right: pl.DataFrame,
    left_unmatched: pl.DataFrame,
    right_unmatched: pl.DataFrame,
    pairs: pl.DataFrame,
    s: dict,
) -> pl.DataFrame:
    left_rows, right_rows = left.height, right.height

    def unique_count(series: pl.Series) -> int:
        return int(series.drop_nulls().n_unique())

    left_matched = unique_count(pairs["__l"])
    right_matched = unique_count(pairs["__r"])
    groups = unique_count(pairs["__mid"])
    within = outside = 0
    if not pairs.is_empty():
        status = pairs.group_by("__mid").agg(pl.col("Match_Status").first())
        within = int((status["Match_Status"] == "Within tolerance").sum())
        outside = int((status["Match_Status"] == "Outside tolerance").sum())

    left_total = right_total = None
    matched_left = matched_right = None
    matched_net = matched_abs = None
    left_unmatched_total = right_unmatched_total = None
    net_total = None
    if s["has_amount"]:
        left_total = _sum_amount(left, s["amount_left"])
        right_total = _sum_amount(right, s["amount_right"])
        matched_left = _sum_amount(
            left.join(pairs.select(pl.col("__l").unique()), on="__l"),
            s["amount_left"],
        )
        matched_right = _sum_amount(
            right.join(pairs.select(pl.col("__r").drop_nulls().unique()), on="__r"),
            s["amount_right"],
        )
        matched_net = round((matched_right or 0.0) - (matched_left or 0.0), 6)
        if not pairs.is_empty():
            matched_abs = float(
                pairs.unique("__mid", keep="first")
                .select(pl.col("__diff").abs().sum())
                .item()
                or 0.0
            )
        else:
            matched_abs = 0.0
        left_unmatched_total = _sum_amount(left_unmatched, s["amount_left"])
        right_unmatched_total = _sum_amount(right_unmatched, s["amount_right"])
        net_total = round((right_total or 0.0) - (left_total or 0.0), 6)

    row = {
        "Match_Type": s["match_type"],
        "Left_Rows": left_rows,
        "Right_Rows": right_rows,
        "Matched_Groups": groups,
        "Left_Matched_Rows": left_matched,
        "Right_Matched_Rows": right_matched,
        "Left_Unmatched_Rows": left_unmatched.height,
        "Right_Unmatched_Rows": right_unmatched.height,
        "Left_Match_Rate_Pct": (
            round(100 * left_matched / left_rows, 2) if left_rows else None
        ),
        "Right_Match_Rate_Pct": (
            round(100 * right_matched / right_rows, 2) if right_rows else None
        ),
        "Left_Total": left_total,
        "Right_Total": right_total,
        "Matched_Left_Total": matched_left,
        "Matched_Right_Total": matched_right,
        "Matched_Net_Difference": matched_net,
        "Matched_Abs_Difference": matched_abs,
        "Left_Unmatched_Total": left_unmatched_total,
        "Right_Unmatched_Total": right_unmatched_total,
        "Net_Difference_Total": net_total,
        "Within_Tolerance_Groups": within,
        "Outside_Tolerance_Groups": outside,
    }
    return pl.DataFrame([row], schema=SUMMARY)


def apply_reconcile(left: Frame, right: Frame, settings: dict) -> ReconcileResult:
    s = normalize(settings)
    lf, rf = as_lazy(left), as_lazy(right)
    for schema, side in ((schema_of(lf), "left"), (schema_of(rf), "right")):
        names = [pair[side] for pair in s["key_pairs"]] + [
            name for name in (s[f"amount_{side}"], s[f"date_{side}"]) if name
        ]
        require_columns(schema, names)
    left_frame = lf.with_row_index("__l").collect()
    right_frame = rf.with_row_index("__r").collect()
    left_slim = _slim(left_frame, "l", s)
    right_slim = _slim(right_frame, "r", s)

    if s["match_type"] == "many_to_many":
        keys = [f"__k{index}" for index in range(len(s["key_pairs"]))]
        pairs = _pairs_many_to_many(left_slim, right_slim, s)
        left_hit = left_ok = left_slim.join(
            right_slim.select(keys).unique(), on=keys, how="semi"
        )["__l"]
        right_hit = right_ok = right_slim.join(
            left_slim.select(keys).unique(), on=keys, how="semi"
        )["__r"]
    else:
        candidates = _metrics(_candidates(left_slim, right_slim, s), s)
        if s["match_type"] == "one_to_one":
            pairs = _pairs_one_to_one(candidates, s)
            ok = candidates.filter(pl.col("__amt_ok") & pl.col("__date_ok"))
        else:
            pairs = _pairs_one_to_many(candidates, s)
            ok = candidates.filter(pl.col("__date_ok"))
        left_hit, right_hit = candidates["__l"], candidates["__r"]
        left_ok, right_ok = ok["__l"], ok["__r"]

    left_columns = [name for name in left_frame.columns if name != "__l"]
    right_names: dict[str, str] = {}
    for column in [name for name in right_frame.columns if name != "__r"]:
        right_names[column] = unique_name(
            f"{column}_right" if column in left_columns else column,
            left_columns + list(right_names.values()),
        )
    lead = {
        "Match_ID": pl.col("__mid"),
        "Match_Status": pl.col("Match_Status"),
    }
    if s["has_amount"]:
        lead["Amount_Diff"] = pl.col("__diff")
    if s["has_date"]:
        lead["Date_Gap_Days"] = pl.col("__gap")
    matched = (
        pairs.select(
            "__l", "__r", *[expression.alias(name) for name, expression in lead.items()]
        )
        .join(left_frame, on="__l", how="left")
        .join(right_frame.rename(right_names), on="__r", how="left")
        .sort(["Match_ID", "__l", "__r"], nulls_last=True)
        .select(list(lead) + left_columns + list(right_names.values()))
    )
    left_unmatched = _unmatched(
        left_frame, "l", pairs["__l"].drop_nulls(), left_hit, left_ok, s
    )
    right_unmatched = _unmatched(
        right_frame, "r", pairs["__r"].drop_nulls(), right_hit, right_ok, s
    )
    return ReconcileResult(
        matched,
        left_unmatched,
        right_unmatched,
        _summary(
            left_frame,
            right_frame,
            left_unmatched,
            right_unmatched,
            pairs,
            s,
        ),
    )


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    result = apply_reconcile(frames[0], frames[1], settings)
    return [
        result.matched.lazy(),
        result.left_unmatched.lazy(),
        result.right_unmatched.lazy(),
        result.summary.lazy(),
    ]
