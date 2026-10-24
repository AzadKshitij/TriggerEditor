"""Unique: first occurrence per key plus all duplicate rows (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import as_lazy, schema_of

DEFAULTS = {"selected_columns": []}


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    """Return unique rows first, then every row in a duplicated key group."""
    frame = as_lazy(frames[0])
    schema = schema_of(frame)
    columns = [
        str(name)
        for name in (settings or {}).get("selected_columns") or []
        if str(name) in schema
    ]
    if not columns:
        return [frame, frame.head(0)]
    duplicates = frame.filter(pl.struct(columns).is_duplicated())
    unique = frame.unique(subset=columns, maintain_order=True)
    return [unique, duplicates]
