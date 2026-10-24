"""Formula core: chained calculated columns, casts and section errors."""

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


def test_new_column_is_appended() -> None:
    out = _run([_section("double", "[x] * 2")])
    assert out.columns == ["x", "s", "double"]
    assert out["double"].to_list() == [2, 4, 6]


def test_existing_column_is_replaced_in_place() -> None:
    out = _run([_section("x", "[x] + 1")])
    assert out.columns == ["x", "s"]
    assert out["x"].to_list() == [2, 3, 4]


def test_sections_chain_and_see_earlier_targets() -> None:
    out = _run(
        [
            _section("y", "[x] * 2"),
            _section("z", "[y] + 1"),
        ]
    )
    assert out.columns == ["x", "s", "y", "z"]
    assert out["z"].to_list() == [3, 5, 7]


def test_target_dtype_casts_new_columns() -> None:
    out = _run([_section("t", "[x]", dtype="String")])
    assert out["t"].to_list() == ["1", "2", "3"]
    assert out["t"].dtype == pl.String


def test_empty_sections_are_ignored() -> None:
    out = core.run_node(
        [_frame()],
        {"sections": [_section("", ""), _section("y", "  ")]},
    ).pop()
    assert out.collect().equals(_frame().collect())


def test_column_quoting_and_string_literals() -> None:
    out = _run([_section("flag", "[s] = 'a'")])
    assert out["flag"].to_list() == [True, False, False]


def test_invalid_sql_names_the_section() -> None:
    with pytest.raises(ShapingError) as error:
        core.run_node([_frame()], {"sections": [_section("y", "(((")]})
    assert error.value.code == "TD-SHAPE-004"
    assert str(error.value).startswith("[TD-SHAPE-004] Section 1:")


def test_sequential_fallback_identifies_the_second_section() -> None:
    with pytest.raises(ShapingError) as error:
        core.run_node(
            [_frame()],
            {
                "sections": [
                    _section("y", "[x] * 2"),
                    _section("z", "nosuchcol + 1"),
                ]
            },
        )
    assert "Section 2" in str(error.value)


def test_narrow_input_dtypes_are_normalised() -> None:
    frame = pl.DataFrame({"x": pl.Series([1, 2], dtype=pl.Int32)}).lazy()
    out = (
        core.run_node([frame], {"sections": [_section("y", "[x] * 2")]}).pop().collect()
    )
    assert out.schema["y"] == pl.Int64


def test_output_is_lazy() -> None:
    out = core.run_node([_frame()], {"sections": [_section("y", "[x]")]}).pop()
    assert isinstance(out, pl.LazyFrame)


def test_validate_section_reports_bad_formula() -> None:
    frames = [_frame()]
    good = {"sections": [_section("y", "[x] * 2")]}
    assert core.validate_section(frames, good, 0) == []

    bad = {"sections": [_section("y", "(((")]}
    errors = core.validate_section(frames, bad, 0)
    assert errors and errors[0]["message"]
