"""Rows: generate a typed column of rows (Qt-free)."""

from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl

from trigger_designer.core.shaping.common import ShapingError, as_lazy

MAX_ITERATIONS = 10000

DEFAULTS = {
    "field_name": "counter",
    "field_type": "int",
    "initial_value": 1,
    "increment_value": 1,
    "max_value": 10,
}

_TYPES = ("int", "float", "string", "datetime")


def _typed(value, field_type: str):
    if field_type == "int":
        return int(value)
    if field_type == "float":
        return float(value)
    if field_type == "datetime":
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))
    return str(value)


def _generate(settings: dict) -> tuple[list, bool]:
    field_type = str(settings.get("field_type") or "int")
    if field_type not in _TYPES:
        raise ShapingError("TD-SHAPE-004", f"Unknown field type '{field_type}'")

    current = _typed(settings.get("initial_value"), field_type)
    maximum = _typed(settings.get("max_value"), field_type)
    # Datetime increments are seconds; the other types increment by value.
    increment = (
        float(settings.get("increment_value"))
        if field_type == "datetime"
        else _typed(settings.get("increment_value"), field_type)
    )

    values: list = []
    for _ in range(MAX_ITERATIONS):
        if field_type != "string" and current > maximum:
            break
        values.append(current)
        if field_type == "datetime":
            current = current + timedelta(seconds=increment)
        elif field_type in ("int", "float"):
            current = current + increment
        else:
            current = f"{current}{increment}"
    return values, len(values) >= MAX_ITERATIONS


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    settings = {**DEFAULTS, **(settings or {})}
    name = str(settings.get("field_name") or "").strip()
    if not name:
        raise ShapingError("TD-SHAPE-001", "Field name is empty")

    values, _capped = _generate(settings)
    generated = pl.DataFrame({name: values}).lazy()
    if frames and frames[0] is not None:
        return [pl.concat([as_lazy(frames[0]), generated], how="horizontal")]
    return [generated]


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    settings = {**DEFAULTS, **(settings or {})}
    if str(settings.get("field_type") or "int") not in _TYPES:
        return []
    if not str(settings.get("field_name") or "").strip():
        return []
    _values, capped = _generate(settings)
    return [("Reached 10,000 rows", "warning")] if capped else []
