"""Record ID: stable numbered rows, optionally per group."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import (
    Frame,
    ShapingError,
    as_lazy,
    require_columns,
    schema_of,
)

POS = "__pos"

DEFAULTS = {
    "name": "RecordID",
    "start": 1,
    "position": "first",
    "group_by": [],
    "order_by": [],
}


def normalize(settings: dict) -> dict:
    out = {**DEFAULTS, **(settings or {})}
    out["start"] = int(out["start"])
    out["name"] = str(out["name"]).strip()
    out["group_by"] = list(out["group_by"] or [])
    out["order_by"] = list(out["order_by"] or [])
    return out


def apply_record_id(frame: Frame, settings: dict) -> pl.LazyFrame:
    s = normalize(settings)
    lf = as_lazy(frame)
    schema = schema_of(lf)
    if not s["name"]:
        raise ShapingError("TD-SHAPE-001", "Record ID column name is empty")
    if s["name"] in schema or s["name"] == POS:
        raise ShapingError(
            "TD-SHAPE-002", f"Column '{s['name']}' already exists", [s["name"]]
        )
    order_cols = [item["column"] for item in s["order_by"]]
    require_columns(schema, s["group_by"] + order_cols)

    number = pl.int_range(pl.len(), dtype=pl.Int64) + s["start"]
    if not s["group_by"] and not order_cols:
        out = lf.with_columns(number.alias(s["name"]))
    else:
        lf = lf.with_row_index(POS)
        keys = order_cols + [POS]
        descending = [bool(item.get("descending")) for item in s["order_by"]] + [False]
        if s["group_by"]:
            number = number.over(s["group_by"])
        out = (
            lf.sort(keys, descending=descending, nulls_last=True, maintain_order=True)
            .with_columns(number.alias(s["name"]))
            .sort(POS, maintain_order=True)
            .drop(POS)
        )
    columns = list(schema)
    order = [s["name"], *columns] if s["position"] == "first" else [*columns, s["name"]]
    return out.select(order)


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return [apply_record_id(frames[0], settings)]
