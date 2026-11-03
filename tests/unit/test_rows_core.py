"""Rows core: typed loops, the cap and horizontal concatenation."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.shaping import rows as core
from trigger_designer.core.shaping.common import ShapingError


def _values(settings: dict) -> list:
    return core.run_node([None], settings).pop().collect()["counter"].to_list()


def test_int_range_is_inclusive() -> None:
    assert _values({"initial_value": 1, "increment_value": 1, "max_value": 5}) == [
        1,
        2,
        3,
        4,
        5,
    ]


def test_float_range_with_fractional_increment() -> None:
    assert _values(
        {
            "field_type": "float",
            "initial_value": 1.0,
            "increment_value": 0.5,
            "max_value": 2.0,
        }
    ) == [1.0, 1.5, 2.0]


def test_string_concatenation_and_cap(monkeypatch) -> None:
    monkeypatch.setattr(core, "MAX_ITERATIONS", 3)
    settings = {
        "field_type": "string",
        "initial_value": "A",
        "increment_value": "1",
        "max_value": "Z",
    }
    assert _values(settings) == ["A", "A1", "A11"]
    assert core.describe([None], settings) == [("Reached 10,000 rows", "warning")]


def test_datetime_range_uses_seconds() -> None:
    settings = {
        "field_type": "datetime",
        "initial_value": "2024-01-01T00:00:00",
        "increment_value": 3600,
        "max_value": "2024-01-01T02:00:00",
    }
    values = _values(settings)
    assert [value.isoformat() for value in values] == [
        "2024-01-01T00:00:00",
        "2024-01-01T01:00:00",
        "2024-01-01T02:00:00",
    ]


def test_zero_increment_hits_the_cap(monkeypatch) -> None:
    monkeypatch.setattr(core, "MAX_ITERATIONS", 4)
    settings = {
        "initial_value": 1,
        "increment_value": 0,
        "max_value": 10,
    }
    assert _values(settings) == [1, 1, 1, 1]
    assert core.describe([None], settings) == [("Reached 10,000 rows", "warning")]


def test_empty_field_name_is_an_error() -> None:
    with pytest.raises(ShapingError) as error:
        core.run_node([None], {"field_name": "  "})
    assert error.value.code == "TD-SHAPE-001"


def test_unknown_field_type_is_an_error() -> None:
    with pytest.raises(ShapingError) as error:
        core.run_node([None], {"field_type": "bogus"})
    assert error.value.code == "TD-SHAPE-004"


def test_horizontal_concat_with_input() -> None:
    frame = pl.DataFrame({"a": [1, 2, 3]}).lazy()
    out = core.run_node(
        [frame], {"initial_value": 1, "increment_value": 1, "max_value": 3}
    ).pop()
    assert isinstance(out, pl.LazyFrame)
    assert out.collect().rows() == [
        (1, 1),
        (2, 2),
        (3, 3),
    ]


@pytest.mark.parametrize("stop", [2, 5])
def test_row_count_mismatch_is_a_plain_error(stop) -> None:
    frame = pl.DataFrame({"a": [1, 2, 3]}).lazy()
    with pytest.raises(ShapingError) as error:
        core.run_node(
            [frame], {"initial_value": 1, "increment_value": 1, "max_value": stop}
        )
    assert error.value.code == "TD-SHAPE-130"
    assert "zip" not in str(error.value)


def test_custom_column_name() -> None:
    out = core.run_node(
        [None],
        {
            "field_name": "item",
            "initial_value": 1,
            "increment_value": 1,
            "max_value": 2,
        },
    ).pop()
    assert out.collect().columns == ["item"]
