"""Sort: ordered multi-column sort (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import as_lazy, schema_of

DEFAULTS = {"keys": []}


def _keys(settings: dict) -> list[dict]:
    return [
        item
        for item in (settings or {}).get("keys") or []
        if isinstance(item, dict) and str(item.get("column") or "").strip()
    ]


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    frame = as_lazy(frames[0])
    schema = schema_of(frame)
    keys = [item for item in _keys(settings) if item["column"] in schema]
    if not keys:
        return [frame]
    columns = [item["column"] for item in keys]
    descending = [item.get("order") == "Descending" for item in keys]
    return [frame.sort(columns, descending=descending)]


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    schema = schema_of(as_lazy(frames[0]))
    missing = [
        item["column"] for item in _keys(settings) if item["column"] not in schema
    ]
    return [(f"{len(missing)} sort key(s) missing", "warning")] if missing else []
