"""Append core: concat modes, vertical schema check and lazy output."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.shaping import append as core
from trigger_designer.core.shaping.common import ShapingError


def _left() -> pl.DataFrame:
    return pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})


def _right() -> pl.DataFrame:
    return pl.DataFrame({"a": [3], "b": ["z"]})


def _run(left, right, how: str = "diagonal_relaxed") -> pl.DataFrame:
    return core.run_node([left, right], {"how": how}).pop().collect()


def test_vertical_stacks_identical_schemas() -> None:
    out = _run(_left(), _right(), "vertical")
    assert out.rows() == [(1, "x"), (2, "y"), (3, "z")]


def test_diagonal_relaxed_unions_columns() -> None:
    right = pl.DataFrame({"a": [3], "c": [9]})
    out = _run(_left(), right)
    assert out.columns == ["a", "b", "c"]
    assert out.rows() == [(1, "x", None), (2, "y", None), (3, None, 9)]


def test_horizontal_places_frames_side_by_side() -> None:
    right = pl.DataFrame({"c": [9, 8]})
    out = _run(_left(), right, "horizontal")
    assert out.columns == ["a", "b", "c"]
    assert out.rows() == [(1, "x", 9), (2, "y", 8)]


def test_vertical_schema_mismatch_is_readable() -> None:
    right = pl.DataFrame({"a": [3], "c": [9]})
    with pytest.raises(ShapingError) as error:
        core.run_node([_left(), right], {"how": "vertical"})
    assert error.value.code == "TD-SHAPE-004"
    assert "left-only: ['b']" in str(error.value)
    assert "right-only: ['c']" in str(error.value)
    assert "diagonal_relaxed" in str(error.value)


def test_unknown_method_is_an_error() -> None:
    with pytest.raises(ShapingError) as error:
        core.run_node([_left(), _right()], {"how": "bogus"})
    assert error.value.code == "TD-SHAPE-004"


def test_eager_and_lazy_inputs_mix() -> None:
    out = core.run_node([_left(), _right().lazy()], {}).pop()
    assert isinstance(out, pl.LazyFrame)
    assert out.collect().height == 3


def test_empty_frames() -> None:
    empty = pl.DataFrame(schema={"a": pl.Int64})
    out = core.run_node([empty, empty], {"how": "vertical"}).pop().collect()
    assert out.height == 0
    assert out.columns == ["a"]
