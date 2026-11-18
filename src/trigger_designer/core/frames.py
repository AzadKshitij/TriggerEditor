"""Frame shape/schema helpers shared by nodes and preview code."""

from __future__ import annotations


def frame_schema(frame) -> dict:
    """Column names and dtypes without collecting (lazy-safe).

    Live data may be a LazyFrame (e.g. downstream of Append/Join) - use
    this anywhere only names/types are needed instead of ``.columns``/``.dtype``.

    Polars is imported here, not at module level: this module is reached from
    the node base class at startup, and these helpers only run once there is
    a table to look at (so Polars is loaded by then).
    """
    import polars as pl

    if frame is None:
        return {}
    if isinstance(frame, pl.LazyFrame):
        schema = frame.collect_schema()
    else:
        schema = frame.schema
    return {name: dtype for name, dtype in schema.items()}


def frame_shape(frame) -> tuple:
    """(height, width) for logs; height is ``"lazy"`` without collecting."""
    import polars as pl

    width = len(frame_schema(frame))
    if isinstance(frame, pl.LazyFrame):
        return ("lazy", width)
    try:
        return (frame.height, width)
    except Exception:  # noqa: BLE001 - shape reporting is best effort
        return ("?", width)
