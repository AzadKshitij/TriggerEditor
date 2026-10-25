#!/usr/bin/env python3
"""Bounded preview sampling: row/memory caps, totals and the lazy contract."""

import os
import sys

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
import pytest

from trigger_designer.qt.models.preview_sampling import (
    PreviewWindow,
    collect_preview,
    estimate_frame_bytes,
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
