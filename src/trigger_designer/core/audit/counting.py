"""Row counting and schema capture (docs/plan/02-audit-trail.md 3.5).

Three effective modes, chosen once per run:

``all``   collect each lazy output once and hand the materialised frame
          downstream, so every plan executes exactly once;
``sink``  no materialisation; only source nodes are counted (one cheap pass);
``off``   nothing is counted.

Qt-free. ``count_frame`` raises :class:`CountError` on failure; the recorder
turns that into a warning and keeps the original frame, so the audit layer can
never change a run's outcome.
"""

from __future__ import annotations

from typing import Any

MAX_COLUMNS = 500
MODES = ("auto", "all", "sink", "off")


class CountError(Exception):
    """Counting or materialising one frame failed; the frame is unchanged."""


def decide_row_count_mode(
    requested: str, total_input_bytes: int, threshold_mb: int
) -> str:
    """Resolve the preference to ``all`` / ``sink`` / ``off``."""
    if requested in ("off", "all", "sink"):
        return requested
    limit = int(threshold_mb) * 1024 * 1024
    return "all" if total_input_bytes <= limit else "sink"


def _is_lazy(frame: Any) -> bool:
    import polars as pl

    return isinstance(frame, pl.LazyFrame)


def _is_eager(frame: Any) -> bool:
    import polars as pl

    return isinstance(frame, pl.DataFrame)


def is_frame(value: Any) -> bool:
    return _is_lazy(value) or _is_eager(value)


def schema_of(frame: Any) -> tuple[list[str], list[str]]:
    """``(column names, dtype strings)`` capped at 500, ending in ``"..."``."""
    schema = frame.collect_schema() if _is_lazy(frame) else frame.schema
    names = [str(name) for name in schema.names()]
    dtypes = [str(dtype) for dtype in schema.dtypes()]
    if len(names) > MAX_COLUMNS:
        names = [*names[:MAX_COLUMNS], "..."]
        dtypes = [*dtypes[:MAX_COLUMNS], "..."]
    return names, dtypes


def count_frame(frame: Any, mode: str, *, is_source: bool) -> tuple[Any, str, Any]:
    """``(rows, method, frame_to_store)`` for one declared output.

    ``rows`` is ``None`` when the mode does not count this frame. The returned
    frame replaces the variable only in ``all`` mode (the materialised one).
    """
    if mode == "off" or not is_frame(frame):
        return None, "none", frame
    try:
        if _is_eager(frame):
            return int(frame.height), "eager", frame
        if mode == "all":
            import polars as pl

            collected = frame.collect()
            return int(collected.height), "materialized", collected.lazy()
        if mode == "sink" and is_source:
            import polars as pl

            rows = frame.select(pl.len()).collect(engine="streaming").item()
            return int(rows), "scan_plan", frame
    except Exception as exc:
        raise CountError(f"{type(exc).__name__}: {exc}") from exc
    return None, "none", frame
