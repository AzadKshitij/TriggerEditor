"""Transpose: selected columns become Name/Value rows (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import ShapingError, as_lazy, schema_of
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes

DEFAULTS = {
    "key_columns": [],
    "data_columns": [],
    "missing_action": "warn",
}

_ACTIONS = ("warn", "error", "ignore")


def _action(settings: dict) -> str:
    value = str(settings.get("missing_action") or "warn")
    return value if value in _ACTIONS else "warn"


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    settings = settings or {}
    frame = as_lazy(frames[0])
    if not settings.get("data_columns"):
        return [frame]

    schema = schema_of(frame)
    key_columns = [name for name in settings.get("key_columns") or [] if name in schema]
    data_columns = [
        name for name in settings.get("data_columns") or [] if name in schema
    ]
    missing = [
        name for name in settings.get("data_columns") or [] if name not in schema
    ]
    action = _action(settings)
    if missing and action == "error":
        raise ShapingError("TD-SHAPE-003", f"Column(s) not found: {', '.join(missing)}")
    if not data_columns:
        # Warn/ignore with nothing left to transpose: keep downstream usable.
        return [frame]

    out = frame.unpivot(
        index=key_columns,
        on=data_columns,
        variable_name="Name",
        value_name="Value",
    )
    # Unpivot widens Value to a common supertype that is often outside the
    # Select dropdown (e.g. all-UInt32 in -> UInt32 out).
    return [normalize_to_supported_dtypes(out)]


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    schema = schema_of(as_lazy(frames[0]))
    settings = settings or {}
    chips: list[tuple[str, str]] = []
    missing_data = [
        name for name in settings.get("data_columns") or [] if name not in schema
    ]
    if missing_data:
        chips.append((f"{len(missing_data)} data column(s) missing", "warning"))
    missing_keys = [
        name for name in settings.get("key_columns") or [] if name not in schema
    ]
    if missing_keys:
        chips.append((f"{len(missing_keys)} key column(s) missing", "warning"))
    return chips
