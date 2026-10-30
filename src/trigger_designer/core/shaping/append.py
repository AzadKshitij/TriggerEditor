"""Append: stack two inputs with a Polars concat method (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import ShapingError, as_lazy, schema_of

DEFAULTS = {"how": "diagonal_relaxed"}
HOW_VALUES = ("vertical", "horizontal", "diagonal", "diagonal_relaxed")


def _schema_difference(left: dict, right: dict) -> str:
    """Say what differs: missing columns, different types, or only the order."""
    parts: list[str] = []
    left_only = [name for name in left if name not in right]
    right_only = [name for name in right if name not in left]
    if left_only:
        parts.append(f"left-only: {left_only}")
    if right_only:
        parts.append(f"right-only: {right_only}")
    for name, dtype in left.items():
        if name in right and right[name] != dtype:
            parts.append(
                f"'{name}' is {dtype} on the left but {right[name]} on the right"
            )
    if not parts:
        parts.append("the same columns and types, but in a different order")
    return "; ".join(parts)


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    left = as_lazy(frames[0])
    right = as_lazy(frames[1])
    how = str((settings or {}).get("how") or "diagonal_relaxed")
    if how not in HOW_VALUES:
        raise ShapingError("TD-SHAPE-004", f"Unknown Append method '{how}'")

    if how == "vertical":
        left_schema = schema_of(left)
        right_schema = schema_of(right)
        if list(left_schema.items()) != list(right_schema.items()):
            raise ShapingError(
                "TD-SHAPE-004",
                f"schemas differ ({_schema_difference(left_schema, right_schema)}). "
                "Try 'diagonal_relaxed'.",
            )

    return [pl.concat([left, right], how=how)]
