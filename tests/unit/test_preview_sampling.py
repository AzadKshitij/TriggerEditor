#!/usr/bin/env python3
"""Bounded preview sampling: row/memory caps, totals and the lazy contract."""

import polars as pl
import pytest

from trigger_designer.qt.models.preview_sampling import (
    CachedPreview,
    PreviewWindow,
    collect_preview,
    estimate_frame_bytes,
    is_previewable,
    snapshot_for_cache,
)


def _heavy_frame(rows: int = 2000, chars: int = 5000) -> pl.DataFrame:
    """A frame that exceeds the 2 MB budget long before its row cap matters."""
    return pl.DataFrame({"payload": ["x" * chars] * rows, "n": range(rows)})


def test_eager_cap_and_exact_total():
    df = pl.DataFrame({"n": range(5000)})
    window = collect_preview(df, max_rows=1000)
    assert isinstance(window, PreviewWindow)
    assert window.frame.height == 1000
    assert window.total_rows == 5000
    assert window.limited is True
    assert window.is_lazy is False


def test_eager_short_frame_is_not_limited():
    window = collect_preview(pl.DataFrame({"n": range(10)}), max_rows=1000)
    assert window.frame.height == 10
    assert window.total_rows == 10
    assert window.limited is False


def test_empty_eager_frame():
    window = collect_preview(pl.DataFrame(), max_rows=1000)
    assert window.frame.height == 0
    assert window.total_rows == 0
    assert window.limited is False


def test_memory_cap_applies_even_below_the_row_cap():
    # The old code only applied the memory cap when height <= max_rows, so a
    # frame under the row cap could still blow past the byte budget.
    df = _heavy_frame()
    window = collect_preview(df, max_rows=100_000, max_size_mb=2.0)
    assert window.frame.height < df.height
    assert window.limited is True
    assert window.total_rows == df.height


def test_memory_cap_applies_in_the_lazy_branch():
    window = collect_preview(_heavy_frame().lazy(), max_rows=100_000, max_size_mb=2.0)
    assert window.frame.height < 2000
    assert window.limited is True
    assert window.is_lazy is True
    assert window.total_rows is None


def test_lazy_short_frame_not_limited_and_never_counts():
    window = collect_preview(pl.DataFrame({"n": range(10)}).lazy(), max_rows=1000)
    assert window.frame.height == 10
    assert window.total_rows is None
    assert window.limited is False
    assert window.is_lazy is True


def test_lazy_height_equal_to_cap_is_called_limited():
    # Equality is ambiguous: the source may hold exactly this many rows or
    # more; the deferred count resolves it, so call it limited here.
    window = collect_preview(pl.DataFrame({"n": range(1000)}).lazy(), max_rows=1000)
    assert window.frame.height == 1000
    assert window.limited is True


def test_empty_lazy_frame():
    empty = pl.DataFrame(schema={"n": pl.Int64}).lazy()
    window = collect_preview(empty, max_rows=1000)
    assert window.frame.height == 0
    assert window.total_rows is None
    assert window.limited is False


def test_pandas_path_converts_and_caps(monkeypatch):
    """The duck-typed pandas branch works without pandas being installed.

    ``collect_preview`` recognizes a foreign frame by its ``DataFrame``
    name plus a ``pandas`` module prefix (no import), then hands it to
    ``pl.from_pandas``. The stub satisfies the detection half; the
    conversion is the external boundary polars owns, so it is stubbed to
    return a real frame of the same shape pandas would have carried.
    """

    class DataFrame:  # name and module must satisfy _is_pandas_dataframe
        pass

    DataFrame.__module__ = "pandas.core.frame"

    converted = pl.DataFrame({"n": range(5000)})
    monkeypatch.setattr(pl, "from_pandas", lambda df: converted)

    window = collect_preview(DataFrame(), max_rows=1000)
    assert isinstance(window.frame, pl.DataFrame)
    assert window.frame.height == 1000
    assert window.total_rows == 5000
    assert window.limited is True
    assert window.is_lazy is False


def test_unsupported_input_raises_type_error():
    with pytest.raises(TypeError):
        collect_preview([1, 2, 3])


def test_estimate_frame_bytes_is_bytes_not_megabytes():
    df = pl.DataFrame({"n": range(10_000)})
    estimated = estimate_frame_bytes(df)
    assert estimated >= 10_000 * 8  # 8 bytes per Int64 value


def test_estimate_frame_bytes_fallback_when_polars_raises(monkeypatch):
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["abc", "de", "f"]})

    def _boom(self, *args, **kwargs):
        raise RuntimeError("no size for you")

    monkeypatch.setattr(pl.DataFrame, "estimated_size", _boom)
    estimated = estimate_frame_bytes(df)
    # Int64 column (3 x 8 B) + string column (3 rows x avg 2 chars x 2 B)
    assert estimated == 3 * 8 + 3 * 2 * 2


# --- cached run results (CachedPreview / snapshot_for_cache) -----------------


def test_snapshot_keeps_rows_and_exact_total_for_an_eager_frame():
    df = pl.DataFrame({"n": range(5000)})
    cached = snapshot_for_cache(df)
    assert isinstance(cached, CachedPreview)
    assert cached.frame.height == 1000
    assert cached.total_rows == 5000
    assert cached.frame["n"].to_list() == list(range(1000))


def test_snapshot_counts_an_in_memory_lazy_plan():
    lazy = pl.DataFrame({"n": range(300)}).lazy().filter(pl.col("n") % 2 == 0)
    cached = snapshot_for_cache(lazy)
    assert cached is not None
    assert cached.total_rows == 150
    assert cached.frame.height == 150


def test_snapshot_leaves_a_file_scan_plan_alone(tmp_path):
    path = tmp_path / "data.csv"
    pl.DataFrame({"n": range(10)}).write_csv(path)
    assert snapshot_for_cache(pl.scan_csv(path)) is None


def test_snapshot_ignores_values_that_are_not_tables():
    assert snapshot_for_cache(5) is None
    assert snapshot_for_cache(pl.Series("n", [1, 2])) is None


def test_snapshot_respects_the_memory_budget():
    cached = snapshot_for_cache(_heavy_frame(rows=2000, chars=5000), max_size_mb=2.0)
    assert cached is not None
    assert cached.frame.height < 2000
    assert cached.total_rows == 2000


def test_snapshot_does_not_keep_the_parent_table_alive():
    # A Polars slice shares its parent's buffers, and so does a gather by
    # position once strings are longer than the 12 bytes a view can inline. The
    # snapshot must hold only its own small copy, whatever the column types.
    import gc
    import os

    import psutil

    process = psutil.Process(os.getpid())
    n = 2_000_000
    ids = pl.int_range(n, eager=True)
    big = pl.DataFrame(
        {
            "n": ids,
            "name": "customer-account-reference-" + ids.cast(pl.String),
        }
    )
    del ids
    gc.collect()
    before = process.memory_info().rss
    cached = snapshot_for_cache(big)
    del big
    gc.collect()
    held_mb = (process.memory_info().rss - before) / 1048576
    assert cached is not None
    assert held_mb < 10


def test_snapshot_round_trips_values_and_dtypes():
    import datetime as dt

    df = pl.DataFrame(
        {
            "i": [1, None, 3],
            "f": [1.5, float("nan"), None],
            "s": ["a", None, "a-long-string-over-twelve-bytes"],
            "b": [True, False, None],
            "d": [dt.date(2026, 1, 1), None, dt.date(2026, 3, 1)],
            "t": [dt.datetime(2026, 1, 1, 12), None, dt.datetime(2026, 3, 1)],
            "l": [[1, 2], None, []],
            "c": pl.Series(["x", "y", "x"]).cast(pl.Categorical),
        }
    )
    cached = snapshot_for_cache(df)
    assert cached is not None
    assert cached.frame.schema == df.schema
    assert cached.frame.equals(df, null_equal=True)
    assert cached.total_rows == 3


def test_snapshot_of_an_empty_frame_keeps_the_schema():
    df = pl.DataFrame({"a": [], "b": []}, schema={"a": pl.Int64, "b": pl.String})
    cached = snapshot_for_cache(df)
    assert cached is not None
    assert cached.total_rows == 0
    assert cached.frame.schema == df.schema


def test_cached_preview_is_previewable_and_collects_exactly():
    cached = snapshot_for_cache(pl.DataFrame({"n": range(5000)}))
    assert cached is not None
    assert is_previewable(cached)
    window = collect_preview(cached)
    assert window.frame.height == 1000
    assert window.total_rows == 5000
    assert window.limited is True
    assert window.is_lazy is False


def test_cached_preview_reapplies_a_smaller_cap():
    cached = snapshot_for_cache(pl.DataFrame({"n": range(5000)}))
    window = collect_preview(cached, max_rows=100)
    assert window.frame.height == 100
    assert window.total_rows == 5000
