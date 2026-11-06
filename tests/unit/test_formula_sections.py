"""Formula core: more sections than allowed, and Data type on a replaced column."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.shaping import formula as core
from trigger_designer.core.shaping.common import ShapingError


def _frame() -> pl.LazyFrame:
    return pl.DataFrame({"x": [1, 2, 3], "s": ["a", "b", "c"]}).lazy()


def _section(target: str, formula: str, dtype: str = "") -> dict:
    return {
        "target_column": target,
        "formula_text": formula,
        "editor_height": 120,
        "target_dtype": dtype,
    }


def _run(sections: list[dict]) -> pl.DataFrame:
    return core.run_node([_frame()], {"sections": sections}).pop().collect()


def test_more_than_the_maximum_sections_is_an_error_not_a_silent_drop() -> None:
    sections = [_section(f"c{i}", "[x]") for i in range(core.MAX_FORMULA_SECTIONS + 1)]
    with pytest.raises(ShapingError) as error:
        core.run_node([_frame()], {"sections": sections})
    assert error.value.code == "TD-SHAPE-004"
    assert str(core.MAX_FORMULA_SECTIONS) in str(error.value)


def test_the_maximum_number_of_sections_still_runs() -> None:
    sections = [_section(f"c{i}", "[x]") for i in range(core.MAX_FORMULA_SECTIONS)]
    out = core.run_node([_frame()], {"sections": sections}).pop().collect()
    assert out.columns[-1] == f"c{core.MAX_FORMULA_SECTIONS - 1}"


def test_data_type_applies_when_replacing_a_column_made_by_an_earlier_section() -> None:
    out = (
        core.run_node(
            [_frame()],
            {
                "sections": [
                    _section("y", "[x] * 2"),
                    _section("y", "[y] + 1", dtype="String"),
                ]
            },
        )
        .pop()
        .collect()
    )
    assert out["y"].dtype == pl.String
    assert out["y"].to_list() == ["3", "5", "7"]


def test_data_type_applies_when_replacing_an_input_column() -> None:
    out = (
        core.run_node([_frame()], {"sections": [_section("x", "[x]", dtype="Float")]})
        .pop()
        .collect()
    )
    assert out["x"].dtype == pl.Float64


def test_auto_keeps_what_the_sql_produces_on_replace() -> None:
    out = core.run_node([_frame()], {"sections": [_section("x", "[x] * 2")]}).pop()
    assert out.collect()["x"].dtype == pl.Int64


def test_categorical_data_type_gives_categorical_on_a_new_column() -> None:
    out = _run([_section("t", "[s]", dtype="Categorical")])
    assert out.columns == ["x", "s", "t"]
    assert out.schema["t"] == pl.Categorical
    assert out["t"].to_list() == ["a", "b", "c"]


def test_categorical_data_type_gives_categorical_on_a_replaced_column() -> None:
    out = _run([_section("s", "[s]", dtype="Categorical")])
    assert out.columns == ["x", "s"]
    assert out.schema["s"] == pl.Categorical
    assert out["s"].to_list() == ["a", "b", "c"]


def test_later_section_data_type_wins_over_an_earlier_categorical() -> None:
    out = _run(
        [
            _section("t", "[s]", dtype="Categorical"),
            _section("t", "[t]", dtype="String"),
        ]
    )
    assert out.schema["t"] == pl.String
    assert out["t"].to_list() == ["a", "b", "c"]


def test_time_data_type_is_kept_as_text() -> None:
    out = _run([_section("t", "TIME '13:30:00'", dtype="Time")])
    assert out.schema["t"] == pl.String
    assert out["t"].to_list() == ["13:30:00"] * 3


@pytest.mark.parametrize("dtype", ["Auto", "String"])
def test_auto_and_string_data_types_stay_string(dtype: str) -> None:
    out = _run([_section("t", "[s]", dtype=dtype)])
    assert out.schema["t"] == pl.String
