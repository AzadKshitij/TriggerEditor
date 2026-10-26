"""Running Total core: cumulative sums, grouping and dtype normalisation."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping import running_total as core


def test_no_sum_columns_passes_through() -> None:
    frame = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]}).lazy()
    out = core.run_node([frame], {}).pop()
    assert isinstance(out, pl.LazyFrame)
    assert out.collect().equals(frame.collect())


def test_single_sum_is_cumulative_in_input_order() -> None:
    frame = pl.DataFrame({"a": [3, 1, 2]}).lazy()
    out = core.run_node([frame], {"sum_columns": ["a"]}).pop().collect()
    assert out["RunTot_a"].to_list() == [3, 4, 6]


def test_grouped_sum_restarts_per_group() -> None:
    frame = pl.DataFrame({"g": ["a", "a", "b"], "v": [1, 2, 5]}).lazy()
    out = (
        core.run_node([frame], {"sum_columns": ["v"], "group_by_columns": ["g"]})
        .pop()
        .collect()
    )
    assert out["RunTot_v"].to_list() == [1, 3, 5]


def test_multiple_sum_columns() -> None:
    frame = pl.DataFrame({"a": [1, 2], "b": [10, 20]}).lazy()
    out = core.run_node([frame], {"sum_columns": ["a", "b"]}).pop().collect()
    assert out["RunTot_a"].to_list() == [1, 3]
    assert out["RunTot_b"].to_list() == [10, 30]


def test_missing_and_non_numeric_columns_are_ignored() -> None:
    frame = pl.DataFrame({"a": [1, 2], "s": ["x", "y"]}).lazy()
    out = core.run_node([frame], {"sum_columns": ["s", "gone"]}).pop()
    assert isinstance(out, pl.LazyFrame)
    assert out.collect().columns == ["a", "s"]

    out = (
        core.run_node([frame], {"sum_columns": ["a"], "group_by_columns": ["gone"]})
        .pop()
        .collect()
    )
    assert out["RunTot_a"].to_list() == [1, 3]


def test_existing_run_tot_column_is_replaced_not_duplicated() -> None:
    frame = pl.DataFrame({"a": [1, 2], "RunTot_a": [99, 99]}).lazy()
    out = core.run_node([frame], {"sum_columns": ["a"]}).pop().collect()
    assert out.columns == ["a", "RunTot_a"]
    assert out["RunTot_a"].to_list() == [1, 3]


def test_narrow_integers_are_normalised() -> None:
    frame = pl.DataFrame({"a": pl.Series([1, 2], dtype=pl.Int32)}).lazy()
    out = core.run_node([frame], {"sum_columns": ["a"]}).pop().collect()
    assert out.schema["RunTot_a"] == pl.Int64
    assert out["RunTot_a"].to_list() == [1, 3]
