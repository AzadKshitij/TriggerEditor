"""Frame shape/schema helpers shared by nodes and preview code."""

from __future__ import annotations

import polars as pl


def frame_schema(frame) -> dict:
    """Column names and dtypes without collecting (lazy-safe).

    Live data may be a LazyFrame (e.g. downstream of Append/Join) - use
    this anywhere only names/types are needed instead of ``.columns``/``.dtype``.
    """
    if frame is None:
        return {}
    if isinstance(frame, pl.LazyFrame):
        schema = frame.collect_schema()
    else:
        schema = frame.schema
    return {name: dtype for name, dtype in schema.items()}


def frame_shape(frame) -> tuple:
    """(height, width) for logs; height is ``"lazy"`` without collecting."""
    width = len(frame_schema(frame))
    if isinstance(frame, pl.LazyFrame):
        return ("lazy", width)
    try:
        return (frame.height, width)
    except Exception:  # noqa: BLE001 - shape reporting is best effort
        return ("?", width)
