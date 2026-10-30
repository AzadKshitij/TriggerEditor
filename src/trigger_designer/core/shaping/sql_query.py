"""SQL Query: run one read-only SELECT over up to three inputs (Qt-free).

The query sees the connected inputs as the tables ``t1``, ``t2`` and ``t3``.
All the safety lives in :mod:`trigger_designer.core.sql_guard`: the text is
checked as a single read-only SELECT and then runs on a fresh in-memory
connection with file access, extensions and configuration locked. This module
only validates the inputs and hands the query to ``run_select``, so the live
preview, the Run path and the generated code all go through the same gate.
"""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import Frame, ShapingError, schema_of
from trigger_designer.core.sql_guard import infer_schema, run_select
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes

DEFAULTS = {"sql": "SELECT *\nFROM t1"}

#: Table names the query can use, in input order.
TABLE_NAMES = ("t1", "t2", "t3")

#: Documented live-preview ceiling. Live evaluation already works on the
#: leading ``LIVE_SAMPLE_ROWS`` rows of each input, so the cap is not reached.
LIVE_CAP_ROWS = 2_000_000


def _settings(settings: dict | None) -> dict:
    return {**DEFAULTS, **(settings or {})}


def _inputs(frames: list) -> dict[str, Frame]:
    """Connected inputs by table name; an unconnected optional one is left out."""
    if not frames or frames[0] is None:
        raise ShapingError("TD-SHAPE-005", "Input 1 has no data")
    return {
        name: frame for name, frame in zip(TABLE_NAMES, frames) if frame is not None
    }


def apply_sql_query(frames: list, settings: dict | None) -> pl.DataFrame:
    """The query result as a DataFrame (validated, read-only, time-limited)."""
    s = _settings(settings)
    inputs = _inputs(frames)
    return normalize_to_supported_dtypes(run_select(s["sql"], inputs))


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    """``frames`` is ``[t1, t2, t3]``; unconnected optional inputs are ``None``."""
    return [apply_sql_query(frames, settings).lazy()]


def diagnostics(sql: str, schemas: dict[str, dict]) -> list[dict]:
    """Editor errors for ``sql`` from zero-row inputs; no real data is read."""
    try:
        infer_schema(sql, schemas)
    except ShapingError as exc:
        return [{"message": exc.detail, "category": "execution"}]
    return []


def output_schema(frames: list, settings: dict | None) -> dict:
    """Result column names and types without running over real rows."""
    s = _settings(settings)
    schemas = {name: schema_of(frame) for name, frame in _inputs(frames).items()}
    return infer_schema(s["sql"], schemas)
