"""Upstream attribution by plan and by data."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.errors.attribution import Ancestor, attribute_upstream


def test_schema_pass_finds_first_failing_ancestor() -> None:
    ok = pl.LazyFrame({"a": [1]})
    broken = ok.select("zz")
    ancestors = (Ancestor(1, ok), Ancestor(2, broken), Ancestor(3, ok))
    assert attribute_upstream("TD-SCH-001", "ColumnNotFoundError", ancestors) == 2


def test_data_pass_finds_cast_ancestor() -> None:
    raw = pl.LazyFrame({"a": ["1", "bad"]})
    broken = raw.select(pl.col("a").cast(pl.Int64))
    ancestors = (Ancestor(1, raw), Ancestor(2, broken))
    assert attribute_upstream("TD-TYP-001", "InvalidOperationError", ancestors) == 2


def test_returns_none_when_all_ancestors_ok() -> None:
    ancestors = (Ancestor(1, pl.LazyFrame({"a": [1]})),)
    assert attribute_upstream("TD-TYP-001", "InvalidOperationError", ancestors) is None


def test_data_pass_respects_budget() -> None:
    raw = pl.LazyFrame({"a": ["bad"]})
    broken = raw.select(pl.col("a").cast(pl.Int64))
    assert (
        attribute_upstream(
            "TD-TYP-001",
            "InvalidOperationError",
            (Ancestor(1, broken),),
            budget_s=0,
        )
        is None
    )


def test_none_frames_are_skipped() -> None:
    ancestors = (Ancestor(1, None), Ancestor(2, pl.LazyFrame({"a": [1]})))
    assert attribute_upstream("TD-SCH-001", "ColumnNotFoundError", ancestors) is None


def test_attribution_ignores_ancestors_with_different_exception_type() -> None:
    raw = pl.LazyFrame({"a": ["bad"]})
    broken = raw.select(pl.col("a").cast(pl.Int64))
    assert (
        attribute_upstream("TD-TYP-001", "SomeOtherError", (Ancestor(1, broken),))
        is None
    )
