"""Bounded preview sampling for the Data Preview surfaces.

Pure Polars/pandas - no Qt, no widgets - so the collector worker and its tests
can run without a QApplication.
"""

import sys
from dataclasses import dataclass
from typing import Any

import polars as pl
from loguru import logger

# Rows collected from a LazyFrame to measure its per-row memory footprint.
_SAMPLE_ROWS = 10


def _is_pandas_dataframe(data: Any) -> bool:
    """True for a pandas DataFrame, without importing pandas."""
    data_type = type(data)
    return data_type.__name__ == "DataFrame" and data_type.__module__.startswith(
        "pandas"
    )


def is_previewable(data: Any) -> bool:
    """True when ``collect_preview`` can render ``data``.

    Hosts use this to tell "no data on this socket" apart from "a value the
    preview cannot show" (a Series, a graph payload) before requesting.
    """
    return isinstance(data, (pl.DataFrame, pl.LazyFrame)) or _is_pandas_dataframe(data)


@dataclass
class PreviewWindow:
    """One bounded collect: the frame to show and what the cap did to it.

    ``total_rows`` is known for eager sources only; a lazy source reports
    ``None`` until the deferred count resolves it. ``limited`` states that the
    source may hold more rows than ``frame`` shows.
    """

    frame: pl.DataFrame
    total_rows: int | None
    limited: bool
    is_lazy: bool


def estimate_frame_bytes(frame: pl.DataFrame) -> int:
    """Byte size of ``frame``, via Polars when it can, per-dtype otherwise.

    Polars' ``estimated_size()`` already walks the real buffers; the fallback
    covers exotic schemas by dtype widths plus a string-length sample. Units
    matter here: the value is bytes, and the memory cap compares it against
    bytes (an earlier estimator returned megabytes and made the cap inert).
    """
    try:
        return int(frame.estimated_size())
    except Exception as e:  # noqa: BLE001 - size estimate is best effort
        logger.warning(f"estimated_size() unavailable ({e}); estimating by dtype")

    estimated_bytes = 0
    for column_name, dtype in frame.schema.items():
        column_data = frame[column_name]

        if dtype in [pl.Boolean, pl.Int8, pl.UInt8]:
            estimated_bytes += frame.height * 1
        elif dtype in [pl.Int16, pl.UInt16]:
            estimated_bytes += frame.height * 2
        elif dtype in [pl.Int32, pl.UInt32, pl.Float32]:
            estimated_bytes += frame.height * 4
        elif dtype in [pl.Int64, pl.UInt64, pl.Float64]:
            estimated_bytes += frame.height * 8
        elif dtype in [pl.Utf8, pl.String]:
            try:
                sample = column_data.head(min(100, frame.height))
                avg_length = sample.str.len_chars().mean() or 10
                estimated_bytes += frame.height * int(avg_length) * 2
            except Exception as e:  # noqa: BLE001 - sampling is best effort
                logger.debug(f"String length sampling failed ({e}); assuming 20 B")
                estimated_bytes += frame.height * 20
        else:
            estimated_bytes += frame.height * 8

    return int(estimated_bytes)


def _memory_row_cap(frame: pl.DataFrame, max_size_bytes: float) -> int:
    """Rows of ``frame`` that fit the byte budget, from its own per-row size.

    ``sys.maxsize`` when the frame has no rows to measure - the caller's
    absolute row cap still applies.
    """
    if frame.height == 0:
        return sys.maxsize
    bytes_per_row = estimate_frame_bytes(frame) / frame.height
    if bytes_per_row <= 0:
        return sys.maxsize
    return int(max_size_bytes / bytes_per_row)


def collect_preview(
    data: Any,
    max_rows: int = 1000,
    max_size_mb: float = 2.0,
) -> PreviewWindow:
    """Collect a bounded window of ``data`` for display.

    ``data`` is a Polars ``DataFrame``/``LazyFrame`` or a pandas ``DataFrame``
    (converted first). The effective row cap is ``min(max_rows,
    rows_within_memory_budget)`` in every branch: the budget comes from the
    frame itself when eager, from a ``head(10)`` sample when lazy.
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    max_rows = max(0, max_rows)

    if _is_pandas_dataframe(data):
        data = pl.from_pandas(data)

    if isinstance(data, pl.LazyFrame):
        sample = data.head(_SAMPLE_ROWS).collect()
        effective = min(max_rows, _memory_row_cap(sample, max_size_bytes))
        frame = data.head(effective).collect()
        # Equality is ambiguous (the source may hold more rows); the deferred
        # count resolves it, and a running scan cannot be cancelled.
        return PreviewWindow(
            frame=frame,
            total_rows=None,
            limited=frame.height >= effective,
            is_lazy=True,
        )

    if isinstance(data, pl.DataFrame):
        effective = min(max_rows, _memory_row_cap(data, max_size_bytes))
        frame = data.head(effective)
        return PreviewWindow(
            frame=frame,
            total_rows=data.height,
            limited=data.height > frame.height,
            is_lazy=False,
        )

    raise TypeError(
        "collect_preview expects a Polars DataFrame/LazyFrame or pandas "
        f"DataFrame, got {type(data).__name__}"
    )
