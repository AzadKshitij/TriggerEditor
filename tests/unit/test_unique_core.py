"""Unique core: first occurrence, every duplicate, nulls and lazy output."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping import unique as core


def test_no_selection_passes_through_with_empty_duplicates() -> None:
    frame = pl.DataFrame({"a": [1, 1]}).lazy()
    unique, duplicates = core.run_node([frame], {})
    assert isinstance(unique, pl.LazyFrame)
    assert isinstance(duplicates, pl.LazyFrame)
    assert unique.collect().equals(frame.collect())
    assert duplicates.collect().height == 0
    assert duplicates.collect().schema == frame.collect().schema


def test_one_key_keeps_the_first_occurrence_in_order() -> None:
    frame = pl.DataFrame({"a": [1, 1, 2], "b": ["x", "y", "z"]}).lazy()
    unique, duplicates = core.run_node([frame], {"selected_columns": ["a"]})
    assert unique.collect().rows() == [(1, "x"), (2, "z")]
    assert duplicates.collect().rows() == [(1, "x"), (1, "y")]


def test_multi_column_key() -> None:
    frame = pl.DataFrame({"a": [1, 1, 1], "b": ["x", "x", "y"], "id": [1, 2, 3]}).lazy()
    unique, duplicates = core.run_node([frame], {"selected_columns": ["a", "b"]})
    assert unique.collect()["id"].to_list() == [1, 3]
    assert duplicates.collect()["id"].to_list() == [1, 2]


def test_null_keys_participate() -> None:
    frame = pl.DataFrame({"a": [None, None, 1]}).lazy()
    unique, duplicates = core.run_node([frame], {"selected_columns": ["a"]})
    assert unique.collect()["a"].to_list() == [None, 1]
    assert duplicates.collect().height == 2


def test_missing_columns_are_ignored() -> None:
    frame = pl.DataFrame({"a": [1, 1], "b": ["x", "y"]}).lazy()
    unique, duplicates = core.run_node([frame], {"selected_columns": ["gone", "a"]})
    assert unique.collect()["b"].to_list() == ["x"]
    assert duplicates.collect()["b"].to_list() == ["x", "y"]


def test_all_selected_columns_missing_passes_through() -> None:
    frame = pl.DataFrame({"a": [1, 1]}).lazy()
    unique, duplicates = core.run_node([frame], {"selected_columns": ["gone"]})
    assert unique.collect()["a"].to_list() == [1, 1]
    assert duplicates.collect().height == 0
