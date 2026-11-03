"""Fuzzy Match two frames on similar text: blocked, scored, deterministic."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from trigger_designer.core.shaping.assign import greedy_one_to_one
from trigger_designer.core.shaping.common import (
    Frame,
    ShapingError,
    as_lazy,
    connect_duckdb,
    estimate_pairs,
    require_columns,
    schema_of,
    unique_name,
)

MAX_CANDIDATE_PAIRS = 5_000_000
#: ``blocking="none"`` compares every left row with every right row.
MAX_UNBLOCKED_PAIRS = 1_000_000
MAX_BLOCK_COLUMNS = 5
ALGORITHMS = ("jaro_winkler", "levenshtein")
BLOCKINGS = ("prefix", "first_token", "none")
ASSIGNMENTS = ("one_to_one", "best_per_left", "all_pairs")
SUFFIX_WORDS = (
    "inc|incorporated|ltd|limited|llc|plc|corp|corporation|co|company|"
    "gmbh|ag|sa|pty|pvt|bv|nv|lp|llp"
)
DEFAULTS = {
    "left_column": "",
    "right_column": "",
    "algorithm": "jaro_winkler",
    "threshold": 0.85,
    "blocking": "prefix",
    "prefix_length": 3,
    "block_columns": [],
    "strip_suffixes": True,
    "assignment": "one_to_one",
}


@dataclass
class FuzzyResult:
    matched: pl.DataFrame
    left_unmatched: pl.DataFrame
    right_unmatched: pl.DataFrame


def normalize(settings: dict) -> dict:
    """Validated settings with defaults; raises ``ShapingError`` (001/004)."""
    s = {**DEFAULTS, **(settings or {})}
    if not s["left_column"] or not s["right_column"]:
        raise ShapingError("TD-SHAPE-001", "Pick the text column on both sides")
    for key, allowed in (
        ("algorithm", ALGORITHMS),
        ("blocking", BLOCKINGS),
        ("assignment", ASSIGNMENTS),
    ):
        if s[key] not in allowed:
            raise ShapingError("TD-SHAPE-004", f"Unknown {key} {s[key]!r}")
    try:
        s["threshold"] = float(s["threshold"])
        s["prefix_length"] = int(s["prefix_length"])
    except (TypeError, ValueError) as exc:
        raise ShapingError(
            "TD-SHAPE-004", "Threshold and prefix length must be numbers"
        ) from exc
    if not 0 < s["threshold"] <= 1:
        raise ShapingError("TD-SHAPE-004", "Threshold must be above 0 and at most 1")
    if not 1 <= s["prefix_length"] <= 10:
        raise ShapingError("TD-SHAPE-004", "Prefix length must be 1-10")
    s["strip_suffixes"] = bool(s["strip_suffixes"])
    # A half-filled pair is a row the user has not finished; it is ignored,
    # like Reconcile's key pairs.
    s["block_columns"] = [
        {"left": pair["left"], "right": pair["right"]}
        for pair in (s["block_columns"] or [])
        if pair.get("left") and pair.get("right")
    ]
    if len(s["block_columns"]) > MAX_BLOCK_COLUMNS:
        raise ShapingError("TD-SHAPE-004", f"At most {MAX_BLOCK_COLUMNS} block columns")
    return s


def normalize_text(expr: pl.Expr, strip_suffixes: bool) -> pl.Expr:
    """Lower-case, punctuation to spaces, optional company suffixes removed."""
    e = expr.cast(pl.String).str.to_lowercase()
    e = e.str.replace_all(r"[^\p{L}\p{N}]+", " ")
    if strip_suffixes:
        e = e.str.replace_all(rf"\b(?:{SUFFIX_WORDS})\b", " ")
    return e.str.replace_all(r"\s+", " ").str.strip_chars()


def _block_expr(norm: pl.Expr, s: dict) -> pl.Expr:
    if s["blocking"] == "prefix":
        return norm.str.slice(0, s["prefix_length"])
    if s["blocking"] == "first_token":
        return norm.str.split(" ").list.first()
    return pl.lit("")


def _slim(frame: pl.DataFrame, side: str, s: dict) -> pl.DataFrame:
    """Only what matching needs: position, normalised text, block keys."""
    name = "left" if side == "l" else "right"
    norm = normalize_text(pl.col(s[f"{name}_column"]), s["strip_suffixes"])
    columns = [
        pl.col(f"__{side}"),
        norm.alias(f"__{side}n"),
        _block_expr(norm, s).alias("__blk"),
    ]
    for index, pair in enumerate(s["block_columns"]):
        key = pl.col(pair[name]).cast(pl.String).str.strip_chars().str.to_lowercase()
        columns.append(
            pl.when(key == "").then(None).otherwise(key).alias(f"__x{index}")
        )
    slim = frame.select(columns)
    return slim.filter(
        pl.col(f"__{side}n").is_not_null() & (pl.col(f"__{side}n") != "")
    )


def score_pairs(cand: pl.DataFrame, algorithm: str) -> pl.DataFrame:
    """Add ``__score`` using DuckDB string functions (in-memory, no files)."""
    if cand.is_empty():
        return cand.select("__l", "__r").with_columns(
            pl.lit(None, pl.Float64).alias("__score")
        )
    if algorithm == "jaro_winkler":
        score = "jaro_winkler_similarity(__ln, __rn)"
    else:
        score = (
            "1.0 - levenshtein(__ln, __rn)::DOUBLE"
            " / greatest(length(__ln), length(__rn))"
        )
    with connect_duckdb() as duck:
        duck.register("cand", cand)
        return duck.sql(f"SELECT __l, __r, {score} AS __score FROM cand").pl()


def _candidates(ls: pl.DataFrame, rs: pl.DataFrame, s: dict) -> pl.DataFrame:
    if s["blocking"] == "none" and ls.height * rs.height > MAX_UNBLOCKED_PAIRS:
        raise ShapingError(
            "TD-SHAPE-082",
            "Too many rows to compare without a blocking key; "
            "choose prefix or first-token blocking",
        )
    keys = ["__blk"] + [f"__x{index}" for index in range(len(s["block_columns"]))]
    count = estimate_pairs(ls, rs, keys)
    if count > MAX_CANDIDATE_PAIRS:
        raise ShapingError(
            "TD-SHAPE-081",
            f"{count:,} possible pairs (limit {MAX_CANDIDATE_PAIRS:,}); "
            "use a longer prefix or add a block column",
        )
    return ls.join(rs, on=keys, how="inner").select("__l", "__r", "__ln", "__rn")


def _assign(scored: pl.DataFrame, s: dict) -> pl.DataFrame:
    """Pairs at or above the threshold, ranked, then reduced per ``assignment``."""
    kept = scored.filter(pl.col("__score").round(9) >= round(s["threshold"], 9)).sort(
        ["__score", "__l", "__r"], descending=[True, False, False]
    )
    if s["assignment"] == "one_to_one":
        kept = greedy_one_to_one(kept)
    elif s["assignment"] == "best_per_left":
        kept = kept.unique("__l", keep="first", maintain_order=True)
    return kept.sort(["__l", "__r"]).with_row_index("__mid", offset=1)


def _output_names(
    left_columns: list[str], right_columns: list[str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Output names: ``Match_*`` are reserved (``_2``); a right clash gets ``_right``."""
    taken = ["Match_ID", "Match_Score"]
    left_names: dict[str, str] = {}
    for column in left_columns:
        left_names[column] = unique_name(column, taken)
        taken.append(left_names[column])
    right_names: dict[str, str] = {}
    for column in right_columns:
        base = f"{column}_right" if column in left_names.values() else column
        right_names[column] = unique_name(base, taken)
        taken.append(right_names[column])
    return left_names, right_names


def apply_fuzzy(left: Frame, right: Frame, settings: dict) -> FuzzyResult:
    s = normalize(settings)
    lf, rf = as_lazy(left), as_lazy(right)
    require_columns(
        schema_of(lf),
        [s["left_column"]] + [pair["left"] for pair in s["block_columns"]],
    )
    require_columns(
        schema_of(rf),
        [s["right_column"]] + [pair["right"] for pair in s["block_columns"]],
    )
    left_frame = lf.with_row_index("__l").collect()
    right_frame = rf.with_row_index("__r").collect()

    ls = _slim(left_frame, "l", s)
    rs = _slim(right_frame, "r", s)
    cand = _candidates(ls, rs, s)
    pairs = _assign(score_pairs(cand, s["algorithm"]), s)

    left_columns = [name for name in left_frame.columns if name != "__l"]
    right_columns = [name for name in right_frame.columns if name != "__r"]
    left_names, right_names = _output_names(left_columns, right_columns)
    matched = (
        pairs.select(
            "__l",
            "__r",
            pl.col("__mid").cast(pl.Int64).alias("Match_ID"),
            pl.col("__score").round(4).alias("Match_Score"),
        )
        .join(left_frame.rename(left_names), on="__l", how="left")
        .join(right_frame.rename(right_names), on="__r", how="left")
        .sort("Match_ID")
        .select(
            ["Match_ID", "Match_Score"]
            + list(left_names.values())
            + list(right_names.values())
        )
    )
    left_unmatched = left_frame.filter(
        ~pl.col("__l").is_in(pairs["__l"].implode())
    ).drop("__l")
    right_unmatched = right_frame.filter(
        ~pl.col("__r").is_in(pairs["__r"].implode())
    ).drop("__r")
    return FuzzyResult(matched, left_unmatched, right_unmatched)


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    result = apply_fuzzy(frames[0], frames[1], settings)
    return [
        result.matched.lazy(),
        result.left_unmatched.lazy(),
        result.right_unmatched.lazy(),
    ]
