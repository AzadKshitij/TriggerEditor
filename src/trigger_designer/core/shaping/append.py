"""Append: stack two inputs with a Polars concat method (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import ShapingError, as_lazy, schema_of

DEFAULTS = {"how": "diagonal_relaxed"}
HOW_VALUES = ("vertical", "horizontal", "diagonal", "diagonal_relaxed")


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    left = as_lazy(frames[0])
    right = as_lazy(frames[1])
    how = str((settings or {}).get("how") or "diagonal_relaxed")
    if how not in HOW_VALUES:
        raise ShapingError("TD-SHAPE-004", f"Unknown Append method '{how}'")

    if how == "vertical":
        left_schema = schema_of(left)
        right_schema = schema_of(right)
        if left_schema != right_schema:
            left_only = [name for name in left_schema if name not in right_schema]
            right_only = [name for name in right_schema if name not in left_schema]
            raise ShapingError(
                "TD-SHAPE-004",
                f"schemas differ (left-only: {left_only}, "
                f"right-only: {right_only}). Try 'diagonal_relaxed'.",
            )

    return [pl.concat([left, right], how=how)]
