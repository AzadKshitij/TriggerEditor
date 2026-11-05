"""Split: estimation/validation partition by row index (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import (
    ShapingError,
    as_lazy,
    schema_of,
    unique_name,
)

DEFAULTS = {"estimation_percent": 70, "random_seed": 42, "is_random": True}
SPLIT_COL = "__split_idx"


def _percent(settings: dict) -> int:
    try:
        percent = int(settings.get("estimation_percent", 70))
    except TypeError, ValueError:
        raise ShapingError(
            "TD-SHAPE-004", "Estimation percent must be between 1 and 99"
        ) from None
    if not 1 <= percent <= 99:
        raise ShapingError(
            "TD-SHAPE-004", "Estimation percent must be between 1 and 99"
        )
    return percent


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    """Split rows into estimation and validation, preserving the old formula.

    The cut is ``row_index < max(row_index) * percent`` on the (optionally
    shuffled) row index, not a row count. That is the algorithm the saved
    golden pins.
    """
    settings = settings or {}
    percent = _percent(settings)
    frame = as_lazy(frames[0])
    col = unique_name(SPLIT_COL, schema_of(frame))
    indexed = frame.with_row_index(col)
    if bool(settings.get("is_random", True)):
        seed = int(settings.get("random_seed", 42))
        indexed = indexed.sort(pl.col(col).shuffle(seed=seed))

    threshold = percent / 100.0
    estimation = indexed.filter(pl.col(col) < pl.col(col).max() * threshold).drop(col)
    validation = indexed.filter(pl.col(col) >= pl.col(col).max() * threshold).drop(col)
    return [estimation, validation]


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    settings = settings or {}
    percent = int(settings.get("estimation_percent", 70))
    chips: list[tuple[str, str]] = [(f"{percent}% / {100 - percent}%", "accent")]
    if bool(settings.get("is_random", True)):
        chips.append((f"random \u00b7 seed {int(settings.get('random_seed', 42))}", ""))
    else:
        chips.append(("sequential", ""))
    return chips
