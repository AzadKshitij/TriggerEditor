"""Aggregate core: group keys, measures, naming and validation."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.shaping import aggregate as core
from trigger_designer.core.shaping.common import ShapingError


def _frame() -> pl.LazyFrame:
    return pl.DataFrame(
        {"g": ["a", "a", "b"], "x": [1, 2, 3], "s": ["p", "q", "r"]}
    ).lazy()


def _run(actions: list[dict]) -> pl.DataFrame:
    return core.run_node([_frame()], {"actions": actions}).pop().collect()


def _action(field: str, action: str, output: str = "") -> dict:
    return {"field": field, "action": action, "output_name": output}


def test_no_actions_passes_through() -> None:
    out = core.run_node([_frame()], {}).pop()
    assert isinstance(out, pl.LazyFrame)
    assert out.collect().equals(_frame().collect())


def test_group_by_only_counts() -> None:
    out = _run([_action("g", "GroupBy")]).sort("g")
    assert out.columns == ["g", "count"]
    assert out.rows() == [("a", 2), ("b", 1)]


def test_group_by_with_sum_count_and_mean() -> None:
    out = _run(
        [
            _action("g", "GroupBy"),
            _action("x", "Sum"),
            _action("s", "Count", "Rows"),
        ]
    ).sort("g")
    assert out.columns == ["g", "Sum_x", "Rows"]
    assert out.rows() == [("a", 3, 2), ("b", 3, 1)]


def test_aggregation_without_group_keys() -> None:
    # A later action for the same field overwrites the earlier one.
    out = _run([_action("x", "Sum"), _action("x", "Mean", "Avg")])
    assert out.columns == ["Avg"]
    assert out.rows() == [(2.0,)]


def test_count_uses_len_and_aliases_the_field() -> None:
    out = _run([_action("s", "Count")])
    assert out.columns == ["Count_s"]
    assert out.rows() == [(3,)]


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("Sum", 6),
        ("Mean", 2.0),
        ("Min", 1),
        ("Max", 3),
        ("Std", 1.0),
        ("Var", 1.0),
        ("Median", 2),
        ("First", 1),
        ("Last", 3),
        ("N_Unique", 3),
    ],
)
def test_action_functions(action: str, expected) -> None:
    out = _run([_action("x", action)])
    assert out.row(0)[0] == expected


def test_list_output_is_normalised() -> None:
    out = _run([_action("x", "List")])
    assert out["List_x"].to_list() == [[1, 2, 3]]
    assert out.schema["List_x"] == pl.List(pl.Int64)


def test_later_action_for_the_same_field_wins() -> None:
    out = _run(
        [
            _action("x", "Sum", "First"),
            _action("x", "Max", "Second"),
        ]
    )
    assert out.columns == ["Second"]
    assert out.rows() == [(3,)]


def test_missing_fields_are_skipped_and_described() -> None:
    out = _run([_action("g", "GroupBy"), _action("gone", "Sum")])
    assert out.columns == ["g", "count"]
    assert core.describe([_frame()], {"actions": [_action("gone", "Sum")]}) == [
        ("1 field(s) missing", "warning")
    ]


def test_all_fields_missing_passes_through() -> None:
    out = _run([_action("gone", "Sum")])
    assert out.equals(_frame().collect())


def test_duplicate_output_names_are_an_error() -> None:
    with pytest.raises(ShapingError) as error:
        core.run_node(
            [_frame()],
            {
                "actions": [
                    _action("x", "Sum", "Same"),
                    _action("g", "Count", "Same"),
                ]
            },
        )
    assert error.value.code == "TD-SHAPE-002"


def test_unknown_action_is_an_error() -> None:
    with pytest.raises(ShapingError) as error:
        core.run_node([_frame()], {"actions": [_action("x", "Bogus")]})
    assert error.value.code == "TD-SHAPE-004"


def test_legacy_group_by_spelling_is_normalized() -> None:
    normalized = core.normalize({"actions": [_action("g", "Group By")]})
    assert normalized["actions"][0]["action"] == "GroupBy"
