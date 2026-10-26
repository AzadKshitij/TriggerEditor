"""Count: total rows as a one-row frame (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import LIVE_SAMPLE_ROWS, as_lazy

DEFAULTS: dict = {}


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    """Return one row holding the number of input rows.

    ``settings`` is accepted for the shared runner API but Count has no
    options. Counting a lazy frame collects it; that is the work this node
    exists to do.
    """
    del settings
    frame = as_lazy(frames[0])
    total = frame.select(pl.len()).collect().item()
    return [pl.DataFrame({"Count": [int(total)]}, schema={"Count": pl.Int64}).lazy()]


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    """Live evaluation counts only the sample; Run counts the whole input."""
    del frames, settings
    return [(f"First {LIVE_SAMPLE_ROWS} rows only: full count at Run", "warning")]
