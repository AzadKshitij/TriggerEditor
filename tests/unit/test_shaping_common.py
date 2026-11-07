"""Shared shaping helpers."""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from trigger_designer.core.shaping.common import (
    ERROR_CODES,
    ShapingError,
    estimate_pairs,
    numeric_expr,
    reject_internal_names,
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


def test_numeric_expr_reads_decimal_commas_like_audit_amounts() -> None:
    frame = pl.DataFrame(
        {"a": ["12,5", "1.234,50", "1 234,50", "1,234.50", "(12.00)", "abc"]}
    )
    values = frame.select(numeric_expr("a", pl.String).alias("v"))["v"].to_list()
    assert values == [12.5, 1234.5, 1234.5, 1234.5, -12.0, None]


def test_numeric_expr_reads_categorical_text() -> None:
    frame = pl.DataFrame({"a": ["1,234.5", "12,5", "x"]}).with_columns(
        pl.col("a").cast(pl.Categorical)
    )
    values = frame.select(numeric_expr("a", frame.schema["a"]).alias("v"))["v"]
    assert values.to_list() == [1234.5, 12.5, None]


def test_numeric_expr_keeps_non_text_non_numbers_empty() -> None:
    frame = pl.DataFrame({"d": [date(2024, 1, 5)]})
    values = frame.select(numeric_expr("d", frame.schema["d"]).alias("v"))["v"]
    assert values.to_list() == [None]


def test_estimate_pairs() -> None:
    left = pl.DataFrame({"k": ["a", "a", "b"]})
    right = pl.DataFrame({"k": ["a", "b", "b"]})
    assert estimate_pairs(left, right, ["k"]) == 4


def test_reject_internal_names_is_silent_without_a_clash() -> None:
    reject_internal_names({"a": pl.String, "b": pl.Int64}, ("__l", "__r"), "left")


def test_reject_internal_names_reports_code_columns_and_side() -> None:
    schema = {"a": pl.String, "__r": pl.Int64}
    with pytest.raises(ShapingError) as info:
        reject_internal_names(schema, ("__l", "__r"), "right")
    assert info.value.code == "TD-SHAPE-002"
    assert info.value.columns == ("__r",)
    assert "'__r'" in str(info.value)
    assert "right input" in str(info.value)
