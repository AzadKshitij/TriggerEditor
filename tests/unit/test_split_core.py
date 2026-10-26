"""Split core: deterministic partition, bounds and lazy output."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.shaping import split as core
from trigger_designer.core.shaping.common import ShapingError


def _frame(rows: int = 10) -> pl.LazyFrame:
    return pl.DataFrame({"v": list(range(rows))}).lazy()


def test_sequential_split_uses_the_old_index_threshold() -> None:
    estimation, validation = core.run_node(
        [_frame(10)], {"is_random": False, "estimation_percent": 70}
    )
    assert isinstance(estimation, pl.LazyFrame)
    assert isinstance(validation, pl.LazyFrame)
    assert estimation.collect()["v"].to_list() == [0, 1, 2, 3, 4, 5, 6]
    assert validation.collect()["v"].to_list() == [7, 8, 9]


def test_random_split_is_deterministic_for_one_seed() -> None:
    settings = {"is_random": True, "estimation_percent": 70, "random_seed": 7}
    first = core.run_node([_frame(20)], settings)
    second = core.run_node([_frame(20)], settings)
    assert first[0].collect().equals(second[0].collect())
    assert first[1].collect().equals(second[1].collect())

    other = core.run_node([_frame(20)], {**settings, "random_seed": 8})
    assert not first[1].collect().equals(other[1].collect())


def test_outputs_partition_the_input() -> None:
    estimation, validation = core.run_node(
        [_frame(23)], {"is_random": True, "estimation_percent": 60}
    )
    combined = pl.concat([estimation.collect(), validation.collect()]).sort("v")
    assert combined["v"].to_list() == list(range(23))


def test_empty_input_gives_two_empty_frames() -> None:
    empty = pl.DataFrame(schema={"v": pl.Int64}).lazy()
    estimation, validation = core.run_node([empty], {})
    assert estimation.collect().height == 0
    assert validation.collect().height == 0
    assert estimation.collect().schema == {"v": pl.Int64}


@pytest.mark.parametrize("percent", [0, -1, 100, 101])
def test_percent_out_of_range_is_an_error(percent: int) -> None:
    with pytest.raises(ShapingError) as error:
        core.run_node([_frame(5)], {"estimation_percent": percent})
    assert error.value.code == "TD-SHAPE-004"


@pytest.mark.parametrize("percent", [1, 99])
def test_percent_bounds_are_accepted(percent: int) -> None:
    estimation, validation = core.run_node(
        [_frame(10)], {"is_random": False, "estimation_percent": percent}
    )
    assert estimation.collect().height + validation.collect().height == 10


def test_describe_reports_percent_and_mode() -> None:
    assert core.describe([_frame(5)], {}) == [
        ("70% / 30%", "accent"),
        ("random \u00b7 seed 42", ""),
    ]
    assert core.describe([_frame(5)], {"is_random": False})[1] == (
        "sequential",
        "",
    )
