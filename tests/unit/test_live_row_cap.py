"""The live row cap decides from a bounded count, never a full scan."""

from __future__ import annotations

from types import SimpleNamespace

import polars as pl

from trigger_designer.qt.helpers.shaping_support import ShapingContent


def _stub(*frames):
    return SimpleNamespace(frames=list(frames))


def test_capped_count_reads_only_past_the_limit() -> None:
    stub = _stub(
        pl.LazyFrame({"a": list(range(100))}), pl.LazyFrame({"a": [1, 2]}), None
    )
    assert ShapingContent._rows_in(stub, 10) > 10


def test_uncapped_count_is_exact() -> None:
    stub = _stub(
        pl.LazyFrame({"a": list(range(100))}), pl.DataFrame({"a": [1, 2]}), None
    )
    assert ShapingContent._rows_in(stub) == 102
    assert ShapingContent._rows_in(stub, 200) == 102


def test_capped_decision_matches_the_exact_count() -> None:
    for rows in (0, 3, 10, 11, 25):
        stub = _stub(
            pl.LazyFrame({"a": list(range(rows))}),
            pl.LazyFrame({"a": list(range(rows))}),
        )
        exact = 2 * rows
        for limit in (5, 10, 20):
            assert (ShapingContent._rows_in(stub, limit) > limit) == (exact > limit)
