"""Transpose core: Name/Value reshape, missing-column policy and dtypes."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.shaping import transpose as core
from trigger_designer.core.shaping.common import ShapingError


def _frame() -> pl.LazyFrame:
    return pl.DataFrame({"id": [1, 2], "a": [10, 20], "b": [30, 40]}).lazy()


def test_no_data_columns_passes_through() -> None:
    out = core.run_node([_frame()], {}).pop()
    assert isinstance(out, pl.LazyFrame)
    assert out.collect().equals(_frame().collect())


def test_key_and_data_columns_reshape_in_order() -> None:
    out = (
        core.run_node([_frame()], {"key_columns": ["id"], "data_columns": ["a", "b"]})
        .pop()
        .collect()
    )
    assert out.columns == ["id", "Name", "Value"]
    assert out.rows() == [
        (1, "a", 10),
        (2, "a", 20),
        (1, "b", 30),
        (2, "b", 40),
    ]


def test_multiple_key_columns() -> None:
    frame = pl.DataFrame({"id": [1], "g": ["x"], "a": [10], "b": [20]}).lazy()
    out = (
        core.run_node([frame], {"key_columns": ["id", "g"], "data_columns": ["a", "b"]})
        .pop()
        .collect()
    )
    assert out.columns == ["id", "g", "Name", "Value"]
    assert out.height == 2


def test_missing_key_column_is_skipped() -> None:
    out = (
        core.run_node(
            [_frame()],
            {
                "key_columns": ["gone", "id"],
                "data_columns": ["a"],
                "missing_action": "error",
            },
        )
        .pop()
        .collect()
    )
    assert out.columns == ["id", "Name", "Value"]
    assert core.describe(
        [_frame()],
        {"key_columns": ["gone"], "data_columns": ["a"]},
    ) == [("1 key column(s) missing", "warning")]


@pytest.mark.parametrize("action", ["warn", "ignore"])
def test_missing_data_columns_are_skipped(action: str) -> None:
    out = (
        core.run_node(
            [_frame()],
            {
                "key_columns": ["id"],
                "data_columns": ["gone", "a"],
                "missing_action": action,
            },
        )
        .pop()
        .collect()
    )
    assert out["Name"].unique().to_list() == ["a"]
    assert core.describe(
        [_frame()],
        {"data_columns": ["gone", "a"]},
    ) == [("1 data column(s) missing", "warning")]


def test_ignore_is_silent_and_warn_shows_the_chip() -> None:
    settings = {"key_columns": ["gone_key"], "data_columns": ["gone", "a"]}
    assert core.describe([_frame()], {**settings, "missing_action": "ignore"}) == []
    assert core.describe([_frame()], {**settings, "missing_action": "warn"}) == [
        ("1 data column(s) missing", "warning"),
        ("1 key column(s) missing", "warning"),
    ]
    # Ignore still drops the missing column from the result.
    out = core.run_node([_frame()], {**settings, "missing_action": "ignore"}).pop()
    assert out.collect()["Name"].unique().to_list() == ["a"]


def test_missing_data_column_with_error_raises() -> None:
    with pytest.raises(ShapingError) as error:
        core.run_node(
            [_frame()],
            {"data_columns": ["gone"], "missing_action": "error"},
        )
    assert error.value.code == "TD-SHAPE-003"


def test_no_valid_data_columns_passes_through_for_warn() -> None:
    out = core.run_node(
        [_frame()], {"data_columns": ["gone"], "missing_action": "warn"}
    ).pop()
    assert out.collect().equals(_frame().collect())


def test_unknown_action_falls_back_to_warn() -> None:
    out = (
        core.run_node(
            [_frame()],
            {
                "key_columns": ["id"],
                "data_columns": ["gone", "a"],
                "missing_action": "bogus",
            },
        )
        .pop()
        .collect()
    )
    assert out["Name"].unique().to_list() == ["a"]


def test_narrow_integers_are_normalised() -> None:
    frame = pl.DataFrame(
        {
            "id": pl.Series([1, 2], dtype=pl.Int32),
            "a": pl.Series([10, 20], dtype=pl.Int32),
        }
    ).lazy()
    out = (
        core.run_node([frame], {"key_columns": ["id"], "data_columns": ["a"]})
        .pop()
        .collect()
    )
    assert out.schema["id"] == pl.Int64
    assert out.schema["Value"] == pl.Int64
