"""Filter core: builder operations, SQL expressions and the two outputs."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.shaping import filter as core
from trigger_designer.core.shaping.common import ShapingError


def _frame() -> pl.LazyFrame:
    return pl.DataFrame(
        {
            "n": [10, 100, 600, 250],
            "s": ["paid", "pending", "paid", "refunded"],
        }
    ).lazy()


def _rows(frame: pl.LazyFrame) -> list[tuple]:
    return frame.collect().rows()


@pytest.mark.parametrize(
    ("operation", "value", "expected"),
    [
        ("Equals", "100", [100]),
        ("Not Equals", "100", [10, 600, 250]),
        ("Less Than", "100", [10]),
        ("Greater Than", "100", [600, 250]),
        ("Less Than or Equal", "100", [10, 100]),
        ("Greater Than or Equal", "100", [100, 600, 250]),
    ],
)
def test_numeric_operations(operation, value, expected) -> None:
    matched, _other = core.run_node(
        [_frame()], {"column": "n", "operation": operation, "value": value}
    )
    assert matched.collect()["n"].to_list() == expected


def test_text_operations() -> None:
    matched, _other = core.run_node(
        [_frame()], {"column": "s", "operation": "Contains", "value": "pen"}
    )
    assert matched.collect()["s"].to_list() == ["pending"]

    matched, _other = core.run_node(
        [_frame()], {"column": "s", "operation": "Equals", "value": "paid"}
    )
    assert _rows(matched) == [(10, "paid"), (600, "paid")]


def test_incomplete_configuration_passes_through() -> None:
    for settings in (
        {},
        {"column": "n"},
        {"column": "n", "operation": "Equals", "value": ""},
        {"column": "n", "operation": "In Between", "value": "1"},
    ):
        matched, other = core.run_node([_frame()], settings)
        assert _rows(matched) == _rows(_frame())
        assert other.collect().height == 0


def test_in_between_is_inclusive_and_order_free() -> None:
    matched, other = core.run_node(
        [_frame()],
        {"column": "n", "operation": "In Between", "value": "500", "value2": "0"},
    )
    assert matched.collect()["n"].to_list() == [10, 100, 250]
    assert other.collect()["n"].to_list() == [600]


def test_missing_column_is_an_error() -> None:
    with pytest.raises(ShapingError) as error:
        core.run_node(
            [_frame()], {"column": "gone", "value": "1", "operation": "Equals"}
        )
    assert error.value.code == "TD-SHAPE-003"


def test_unsupported_operation_is_an_error() -> None:
    with pytest.raises(ShapingError) as error:
        core.run_node([_frame()], {"column": "n", "operation": "Bogus", "value": "1"})
    assert error.value.code == "TD-SHAPE-004"


def test_empty_expression_passes_through() -> None:
    matched, other = core.run_node([_frame()], {"mode": "expression"})
    assert _rows(matched) == _rows(_frame())
    assert other.collect().height == 0


def test_expression_equals_and_not_equals_partition() -> None:
    matched, other = core.run_node(
        [_frame()],
        {
            "mode": "expression",
            "expression": "[s] = 'paid'",
        },
    )
    assert matched.collect()["n"].to_list() == [10, 600]
    combined = pl.concat([matched.collect(), other.collect()]).sort(["n", "s"])
    assert combined.equals(_frame().collect().sort(["n", "s"]))


def test_expression_in_between_and_function_aliases() -> None:
    matched, _other = core.run_node(
        [_frame()],
        {
            "mode": "expression",
            "expression": "[n] in_between (0, 500) AND strip([s]) = 'paid'",
        },
    )
    assert matched.collect()["n"].to_list() == [10]


def test_expression_string_literals_are_not_column_names() -> None:
    # A quoted identifier is handled; a '...' literal containing [..] is data.
    matched, _other = core.run_node(
        [_frame()],
        {"mode": "expression", "expression": "[s] = 'paid'"},
    )
    assert matched.collect()["n"].to_list() == [10, 600]


def test_bad_expression_is_a_shaping_error() -> None:
    with pytest.raises(ShapingError) as error:
        core.run_node([_frame()], {"mode": "expression", "expression": "(((("})
    assert error.value.code == "TD-SHAPE-004"


def test_outputs_are_lazy_in_both_modes() -> None:
    builder = core.run_node(
        [_frame()], {"column": "n", "operation": "Equals", "value": "10"}
    )
    expression = core.run_node(
        [_frame()], {"mode": "expression", "expression": "[n] = 10"}
    )
    assert all(isinstance(out, pl.LazyFrame) for out in builder + expression)


def _frame_with_nulls() -> pl.LazyFrame:
    return pl.DataFrame({"s": ["x", None, "y"]}).lazy()


def test_builder_null_rows_go_to_the_unmatched_output() -> None:
    matched, unmatched = core.run_node(
        [_frame_with_nulls()], {"column": "s", "operation": "Equals", "value": "x"}
    )
    assert _rows(matched) == [("x",)]
    assert _rows(unmatched) == [(None,), ("y",)]


def test_expression_null_rows_go_to_the_unmatched_output() -> None:
    matched, unmatched = core.run_node(
        [_frame_with_nulls()], {"mode": "expression", "expression": "[s] = 'x'"}
    )
    assert _rows(matched) == [("x",)]
    assert set(_rows(unmatched)) == {(None,), ("y",)}


def _text_frame() -> pl.LazyFrame:
    return pl.DataFrame({"s": ["a(b", "a.b", "axb", "A(B", None]}).lazy()


def test_contains_reads_the_value_as_plain_text() -> None:
    matched, other = core.run_node(
        [_text_frame()], {"column": "s", "operation": "Contains", "value": "("}
    )
    assert matched.collect()["s"].to_list() == ["a(b", "A(B"]
    assert other.collect().height == 3

    matched, _ = core.run_node(
        [_text_frame()], {"column": "s", "operation": "Contains", "value": "a.b"}
    )
    # "." is not a wildcard: only the literal "a.b" matches.
    assert matched.collect()["s"].to_list() == ["a.b"]


def _date_frame() -> pl.LazyFrame:
    from datetime import date, datetime

    return pl.DataFrame(
        {
            "d": [date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1), None],
            "t": [
                datetime(2024, 1, 1, 8),
                datetime(2024, 2, 1, 9),
                datetime(2024, 3, 1, 10),
                None,
            ],
        }
    ).lazy()


@pytest.mark.parametrize("column", ["d", "t"])
def test_date_greater_than_and_in_between(column) -> None:
    matched, other = core.run_node(
        [_date_frame()],
        {"column": column, "operation": "Greater Than", "value": "2024-01-15"},
    )
    assert matched.collect().height == 2
    assert other.collect().height == 2  # earlier row and the empty cell

    matched, _ = core.run_node(
        [_date_frame()],
        {
            "column": column,
            "operation": "In Between",
            "value": "2024-03-01",  # swapped bounds are put in order
            "value2": "2024-01-15",
        },
    )
    assert matched.collect().height == 1 + (1 if column == "d" else 0)


def test_date_equals_and_bad_date() -> None:
    matched, _ = core.run_node(
        [_date_frame()], {"column": "d", "operation": "Equals", "value": "2024-02-01"}
    )
    assert matched.collect().height == 1
    with pytest.raises(ShapingError) as error:
        core.run_node(
            [_date_frame()],
            {"column": "d", "operation": "Greater Than", "value": "last week"},
        )
    assert error.value.code == "TD-SHAPE-004"
    assert "date" in str(error.value)
