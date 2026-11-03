"""Deterministic one-to-one assignment shared by Reconcile and Fuzzy Match."""

from __future__ import annotations

import polars as pl

MAX_ROUNDS = 200


def greedy_one_to_one(cand: pl.DataFrame) -> pl.DataFrame:
    """Pick pairs so that no ``__l`` and no ``__r`` is used twice."""
    remaining = cand.with_row_index("__rank")
    accepted: list[pl.DataFrame] = []
    for _ in range(MAX_ROUNDS):
        if remaining.is_empty():
            break
        best_l = remaining.unique("__l", keep="first", maintain_order=True)
        best_r = remaining.unique("__r", keep="first", maintain_order=True)
        mutual = best_l.filter(pl.col("__rank").is_in(best_r["__rank"].implode()))
        accepted.append(mutual)
        remaining = remaining.filter(
            ~pl.col("__l").is_in(mutual["__l"].implode())
            & ~pl.col("__r").is_in(mutual["__r"].implode())
        )
    if not remaining.is_empty():
        accepted.append(_sequential(remaining))
    if not accepted:
        return cand.head(0)
    return pl.concat(accepted).sort("__rank").drop("__rank")


def _sequential(ranked: pl.DataFrame) -> pl.DataFrame:
    used_l: set[int] = set()
    used_r: set[int] = set()
    keep: list[int] = []
    for rank, left_id, right_id in zip(ranked["__rank"], ranked["__l"], ranked["__r"]):
        if left_id not in used_l and right_id not in used_r:
            used_l.add(left_id)
            used_r.add(right_id)
            keep.append(rank)
    return ranked.filter(
        pl.col("__rank").is_in(pl.Series(keep, dtype=pl.UInt32).implode())
    )
