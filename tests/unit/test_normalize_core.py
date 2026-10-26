"""Normalize core: rule order, scope, duplicates and lazy rename."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.shaping import normalize as core
from trigger_designer.core.shaping.common import ShapingError


def test_default_rules_trim_and_underscore() -> None:
    frame = pl.DataFrame({" Order ID ": [1], "a  b\tc": [2]}).lazy()
    out = core.run_node([frame], {}).pop()
    assert isinstance(out, pl.LazyFrame)
    assert out.collect().columns == ["Order_ID", "a_b_c"]


def test_remove_all_whitespace_wins_over_underscores() -> None:
    assert (
        core.normalize_column_name(
            "a b", spaces_to_underscore=True, remove_all_whitespace=True
        )
        == "ab"
    )


def test_case_rules() -> None:
    assert core.normalize_column_name("Mixed Case", case_modification="lower") == (
        "mixed_case"
    )
    assert core.normalize_column_name("Mixed Case", case_modification="upper") == (
        "MIXED_CASE"
    )
    assert core.normalize_column_name("mixed case", case_modification="title") == (
        "Mixed_Case"
    )


def test_empty_selection_means_every_column() -> None:
    frame = pl.DataFrame({"a b": [1], "c d": [2]}).lazy()
    out = core.run_node([frame], {"selected_columns": []}).pop().collect()
    assert out.columns == ["a_b", "c_d"]


def test_selected_subset_only() -> None:
    frame = pl.DataFrame({"a b": [1], "c d": [2]}).lazy()
    out = core.run_node([frame], {"selected_columns": ["c d"]}).pop().collect()
    assert out.columns == ["a b", "c_d"]


def test_unchanged_names_are_absent_from_the_mapping() -> None:
    mapping = core.build_rename_mapping(["Customer_Id", " Order ID "], [])
    assert mapping == {" Order ID ": "Order_ID"}


def test_duplicate_final_names_raise() -> None:
    frame = pl.DataFrame({"a b": [1], "a_b": [2]}).lazy()
    with pytest.raises(ShapingError) as error:
        core.run_node([frame], {})
    assert error.value.code == "TD-SHAPE-002"


def test_empty_normalized_name_keeps_the_original() -> None:
    assert core.normalize_column_name("   ") == "   "
    frame = pl.DataFrame({"   ": [1]}).lazy()
    out = core.run_node([frame], {}).pop().collect()
    assert out.columns == ["   "]


def test_missing_selected_column_is_ignored() -> None:
    frame = pl.DataFrame({"a b": [1]}).lazy()
    out = core.run_node([frame], {"selected_columns": ["gone", "a b"]}).pop().collect()
    assert out.columns == ["a_b"]
