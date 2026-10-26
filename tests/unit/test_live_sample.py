"""Live evaluation works on the leading rows of each input."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import LIVE_SAMPLE_ROWS, live_sample


def test_lazy_frame_is_cut_to_the_sample_and_stays_lazy() -> None:
    frame = pl.LazyFrame({"a": list(range(1_000)), "b": ["x"] * 1_000})
    sample = live_sample(frame)
    assert isinstance(sample, pl.LazyFrame)
    assert sample.collect_schema() == frame.collect_schema()
    assert sample.select(pl.len()).collect().item() == LIVE_SAMPLE_ROWS


def test_short_frame_is_unchanged() -> None:
    frame = pl.DataFrame({"a": [1, 2, 3]})
    assert live_sample(frame).equals(frame)


def test_none_passes_through() -> None:
    assert live_sample(None) is None
