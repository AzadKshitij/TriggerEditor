"""Row-count modes, collect-once-and-reuse and schema capture (plan 02 3.5)."""

from __future__ import annotations

import itertools

import polars as pl
import pytest

from trigger_designer.core.audit.counting import (
    CountError,
    count_frame,
    decide_row_count_mode,
    schema_of,
)

MB = 1024 * 1024


@pytest.mark.parametrize(
    ("requested", "size", "expected"),
    [
        ("off", 1, "off"),
        ("off", 10**12, "off"),
        ("all", 10**12, "all"),
        ("all", 1, "all"),
        ("sink", 1, "sink"),
        ("sink", 10**12, "sink"),
        ("auto", 256 * MB - 1, "all"),
        ("auto", 256 * MB, "all"),  # boundary is inclusive
        ("auto", 256 * MB + 1, "sink"),
        ("auto", 0, "all"),
    ],
)
def test_decide_mode_table(requested, size, expected):
    assert decide_row_count_mode(requested, size, 256) == expected


def test_unknown_requested_value_behaves_as_auto():
    assert decide_row_count_mode("whatever", 1, 256) == "all"


def test_count_all_materialises_once():
    calls = itertools.count()

    def spy(series: pl.Series) -> pl.Series:
        next(calls)
        return series

    lazy = pl.LazyFrame({"a": [1, 2, 3]}).select(
        pl.col("a").map_batches(spy, return_dtype=pl.Int64)
    )
    rows, method, stored = count_frame(lazy, "all", is_source=False)
    assert (rows, method) == (3, "materialized")
    assert isinstance(stored, pl.LazyFrame)
    stored.collect()
    stored.select(pl.len()).collect()
    assert next(calls) == 1  # the spy ran once (the counter is now at 1)


def test_count_sink_mode_only_counts_sources():
    lazy = pl.LazyFrame({"a": [1, 2, 3, 4]})
    assert count_frame(lazy, "sink", is_source=True)[:2] == (4, "scan_plan")
    rows, method, stored = count_frame(lazy, "sink", is_source=False)
    assert (rows, method) == (None, "none") and stored is lazy


def test_count_off_returns_none():
    lazy = pl.LazyFrame({"a": [1]})
    assert count_frame(lazy, "off", is_source=True) == (None, "none", lazy)
    eager = pl.DataFrame({"a": [1]})
    assert count_frame(eager, "off", is_source=True)[0] is None


def test_eager_frame_counts_height():
    eager = pl.DataFrame({"a": [1, 2]})
    for mode in ("all", "sink"):
        rows, method, stored = count_frame(eager, mode, is_source=False)
        assert (rows, method) == (2, "eager") and stored is eager


def test_non_frame_values_are_ignored():
    assert count_frame("text", "all", is_source=False) == (None, "none", "text")
    assert count_frame(None, "all", is_source=True) == (None, "none", None)


def test_schema_of_lazy_and_eager():
    names, dtypes = schema_of(pl.LazyFrame({"a": [1], "b": ["x"]}))
    assert names == ["a", "b"] and dtypes == ["Int64", "String"]
    assert schema_of(pl.DataFrame({"a": [1.5]})) == (["a"], ["Float64"])


def test_schema_of_caps_columns_at_500():
    frame = pl.DataFrame({f"c{i}": [i] for i in range(600)})
    names, dtypes = schema_of(frame)
    assert len(names) == 501 and names[-1] == "..."
    assert len(dtypes) == 501 and dtypes[-1] == "..."


def test_count_failure_raises_counterror():
    bad = pl.LazyFrame({"a": ["x"]}).select(pl.col("a").cast(pl.Int64))
    with pytest.raises(CountError):
        count_frame(bad, "all", is_source=False)
