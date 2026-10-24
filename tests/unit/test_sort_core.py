"""Sort core: ordered keys, missing columns and lazy input."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping import sort as core


def test_no_keys_passes_through() -> None:
    frame = pl.DataFrame({"a": [2, 1]}).lazy()
    out = core.run_node([frame], {}).pop()
    assert isinstance(out, pl.LazyFrame)
    assert out.collect()["a"].to_list() == [2, 1]


def test_ascending_and_descending() -> None:
    frame = pl.DataFrame({"a": [2, 1, 3]}).lazy()
    asc = (
        core.run_node([frame], {"keys": [{"column": "a", "order": "Ascending"}]})
        .pop()
        .collect()
    )
    assert asc["a"].to_list() == [1, 2, 3]

    desc = (
        core.run_node([frame], {"keys": [{"column": "a", "order": "Descending"}]})
        .pop()
        .collect()
    )
    assert desc["a"].to_list() == [3, 2, 1]


def test_multiple_keys_apply_in_list_order() -> None:
    frame = pl.DataFrame(
        {"g": ["b", "a", "a", "b"], "v": [1, 2, 1, 2], "id": [1, 2, 3, 4]}
    ).lazy()
    out = (
        core.run_node(
            [frame],
            {
                "keys": [
                    {"column": "g", "order": "Ascending"},
                    {"column": "v", "order": "Descending"},
                ]
            },
        )
        .pop()
        .collect()
    )
    assert out["id"].to_list() == [2, 3, 4, 1]


def test_missing_keys_are_skipped_and_described() -> None:
    frame = pl.DataFrame({"a": [2, 1]}).lazy()
    out = (
        core.run_node(
            [frame],
            {
                "keys": [
                    {"column": "gone", "order": "Ascending"},
                    {"column": "a", "order": "Ascending"},
                ]
            },
        )
        .pop()
        .collect()
    )
    assert out["a"].to_list() == [1, 2]

    untouched = core.run_node(
        [frame], {"keys": [{"column": "gone", "order": "Ascending"}]}
    ).pop()
    assert untouched.collect()["a"].to_list() == [2, 1]
    assert core.describe([frame], {"keys": [{"column": "gone"}]}) == [
        ("1 sort key(s) missing", "warning")
    ]
    assert core.describe([frame], {}) == []


def test_blank_keys_are_ignored() -> None:
    frame = pl.DataFrame({"a": [2, 1]}).lazy()
    out = (
        core.run_node([frame], {"keys": [{"column": "", "order": "Ascending"}]})
        .pop()
        .collect()
    )
    assert out["a"].to_list() == [2, 1]
