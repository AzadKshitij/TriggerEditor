"""Shared shaping helpers."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import (
    ERROR_CODES,
    ShapingError,
    estimate_pairs,
    numeric_expr,
    unique_name,
)


def test_error_codes_are_stable_shape() -> None:
    assert all(
        code.startswith("TD-SHAPE-") and code[-3:].isdigit() for code in ERROR_CODES
    )
    error = ShapingError("TD-SHAPE-001", "Missing", ["a"])
    assert error.code == "TD-SHAPE-001"
    assert error.columns == ("a",)
    assert str(error) == "[TD-SHAPE-001] Missing"


def test_unique_name() -> None:
    assert unique_name("a", ["a", "a_2"]) == "a_3"
    assert unique_name("a", []) == "a"


def test_numeric_expr_handles_csv_text() -> None:
    frame = pl.DataFrame({"a": ["1,234.5", "x", None]})
    values = frame.select(numeric_expr("a", pl.String).alias("v"))["v"].to_list()
    assert values == [1234.5, None, None]


def test_estimate_pairs() -> None:
    left = pl.DataFrame({"k": ["a", "a", "b"]})
    right = pl.DataFrame({"k": ["a", "b", "b"]})
    assert estimate_pairs(left, right, ["k"]) == 4
