"""Formula core: more sections than allowed, and Data type on a replaced column."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.shaping import formula as core
from trigger_designer.core.shaping.common import ShapingError


def _frame() -> pl.LazyFrame:
    return pl.DataFrame({"x": [1, 2, 3]}).lazy()


def _section(target: str, formula: str, dtype: str = "") -> dict:
    return {
        "target_column": target,
        "formula_text": formula,
        "editor_height": 120,
        "target_dtype": dtype,
    }


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
