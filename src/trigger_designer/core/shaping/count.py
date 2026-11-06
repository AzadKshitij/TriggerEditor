"""Count: total rows as a one-row frame (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import LIVE_SAMPLE_ROWS, as_lazy

DEFAULTS: dict = {}


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    """Return one row holding the number of input rows, as a lazy frame.

    ``settings`` is accepted for the shared runner API but Count has no
    options. Nothing runs until the returned frame is collected.
    """
    del settings
    frame = as_lazy(frames[0])
    return [frame.select(pl.len().cast(pl.Int64).alias("Count"))]


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    """Live evaluation counts only the sample; Run counts the whole input."""
    del frames, settings
    return [(f"First {LIVE_SAMPLE_ROWS} rows only: full count at Run", "warning")]
