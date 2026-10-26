"""Bounded row/value locator."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.errors.locator import (
    locate_conversion_failures,
    polars_dtype_from_name,
    probe_expr,
)


def test_locator_matches_example_row_4210() -> None:
    values = [str(index) for index in range(5000)]
    values[4209] = "1,2O0.50"
    frame = pl.LazyFrame({"Amount": values})
    result = locate_conversion_failures((frame,), "Amount", pl.Int64)
    assert result.status == "found"
    assert result.row_index == 4210
    assert result.values == ("1,2O0.50",)


def test_locator_returns_up_to_five_distinct_values_in_row_order() -> None:
    values = ["1", "bad-a", "2", "bad-b", "bad-a", "bad-c", "bad-d", "bad-e", "bad-f"]
    result = locate_conversion_failures(
        (pl.LazyFrame({"Amount": values}),), "Amount", pl.Int64
    )
    assert result.row_index == 2
    assert len(result.values) == 5
    assert result.values[0] == "bad-a"


def test_locator_cap_respected_and_reports_not_found() -> None:
    values = ["1"] * 200
    values[150] = "bad"
    result = locate_conversion_failures(
        (pl.LazyFrame({"Amount": values}),), "Amount", pl.Int64, row_cap=100
    )
    assert result.status == "not_found"
    assert result.cap_hit is True


def test_locator_known_value_exact_row() -> None:
    frame = pl.LazyFrame({"Amount": [" 12", "x"]})
    result = locate_conversion_failures((frame,), "Amount", pl.Int64, known_value="x")
    assert result.status == "found"
    assert result.row_index == 2


def test_locator_decimal_date_and_overflow_targets() -> None:
    decimal = locate_conversion_failures(
        (pl.LazyFrame({"Amount": ["1.00", "nope"]}),),
        "Amount",
        polars_dtype_from_name("decimal[18,2]"),
    )
    assert decimal.row_index == 2

    date = locate_conversion_failures(
        (pl.LazyFrame({"d": ["2024-01-01", "31/12/2024"]}),),
        "d",
        pl.Date,
        date_format="%Y-%m-%d",
    )
    assert date.row_index == 2

    overflow = locate_conversion_failures(
        (pl.LazyFrame({"a": [1, 300, 2]}),), "a", pl.Int8
    )
    assert overflow.row_index == 2
    assert overflow.values == ("300",)


def test_locator_handles_nulls_and_empty_frame() -> None:
    frame = pl.LazyFrame({"Amount": ["1", None, "bad"]})
    result = locate_conversion_failures((frame,), "Amount", pl.Int64)
    assert result.row_index == 3

    empty = locate_conversion_failures(
        (pl.LazyFrame({"Amount": []}),), "Amount", pl.Int64
    )
    assert empty.status == "not_found"


def test_locator_skips_when_column_missing() -> None:
    result = locate_conversion_failures(
        (pl.LazyFrame({"other": [1]}),), "Amount", pl.Int64
    )
    assert result.status == "skipped"


def test_locator_display_escapes_control_chars_and_truncates() -> None:
    value = "x" * 500 + "\n"
    result = locate_conversion_failures(
        (pl.LazyFrame({"Amount": [value]}),), "Amount", pl.Int64
    )
    shown = result.values[0]
    assert len(shown) <= 80
    assert "\n" not in shown
    assert shown.endswith("…")


def test_locator_never_raises_on_broken_plan() -> None:
    result = locate_conversion_failures(
        (pl.LazyFrame({"Amount": ["1"]}).select("zz"),), "Amount", pl.Int64
    )
    assert result.status == "error"


def test_polars_dtype_from_name() -> None:
    assert polars_dtype_from_name("i64") == pl.Int64
    assert polars_dtype_from_name("INT32") == pl.Int32
    assert polars_dtype_from_name("decimal[18,2]") == pl.Decimal(18, 2)
    assert polars_dtype_from_name("DATE") == pl.Date
    assert polars_dtype_from_name("nonsense") is None


def test_probe_expr_is_non_strict() -> None:
    frame = pl.DataFrame({"Amount": [" 1 ", "bad"]})
    out = frame.select(probe_expr("Amount", pl.Int64).alias("v"))
    assert out["v"].to_list() == [1, None]
