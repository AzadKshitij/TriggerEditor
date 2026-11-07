"""Reconcile reads text amounts like the Audit nodes: a decimal comma is a decimal."""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from trigger_designer.core.audit.common import amount_expr as audit_amount_expr
from trigger_designer.core.shaping import reconcile
from trigger_designer.core.shaping.common import ShapingError
from trigger_designer.core.utils.amounts import amount_expr


def _reconcile(left_amounts: list[str], right_amounts: list[str], tolerance=0.0):
    keys = [f"k{i}" for i in range(len(left_amounts))]
    left = pl.DataFrame({"k": keys, "amt": left_amounts}).lazy()
    right = pl.DataFrame({"k": keys, "amt": right_amounts}).lazy()
    return reconcile.apply_reconcile(
        left,
        right,
        {
            "key_pairs": [{"left": "k", "right": "k"}],
            "amount_left": "amt",
            "amount_right": "amt",
            "tolerance": tolerance,
        },
    )


def test_one_helper_serves_audit_and_reconcile() -> None:
    assert audit_amount_expr is amount_expr


def test_decimal_comma_is_a_decimal_not_a_thousand_times_larger() -> None:
    result = _reconcile(["1,50"], ["1.50"])
    assert result.matched["Match_Status"].to_list() == ["Within tolerance"]
    assert result.left_unmatched.height == 0


def test_150_does_not_match_1_comma_50() -> None:
    result = _reconcile(["1,50"], ["150"])
    # 1.5 against 150 is a real difference, no longer hidden by stripping commas.
    assert result.matched.height == 0
    assert result.left_unmatched.height == 1


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1,234.50", 1234.5),
        ("1.234,50", 1234.5),
        ("(1,234.50)", -1234.5),
        ("$5", 5.0),
        ("1,234", 1234.0),
        ("1234,5", 1234.5),
        ("1,2,3", None),
        ("abc", None),
    ],
)
def test_text_amount_forms(text, expected) -> None:
    out = pl.DataFrame({"a": [text]}).select(amount_expr("a", pl.String))["a"]
    assert out.to_list() == [expected]


@pytest.mark.parametrize("side", ["left", "right"])
@pytest.mark.parametrize("name", ["__l", "__r"])
def test_internal_names_are_002_on_either_side(side: str, name: str) -> None:
    left = pl.DataFrame({"k": ["k0"], "amt": ["1.00"]})
    right = pl.DataFrame({"k": ["k0"], "amt": ["1.00"]})
    if side == "left":
        left = left.with_columns(pl.lit("x").alias(name))
    else:
        right = right.with_columns(pl.lit("x").alias(name))
    with pytest.raises(ShapingError) as info:
        reconcile.apply_reconcile(
            left.lazy(),
            right.lazy(),
            {
                "key_pairs": [{"left": "k", "right": "k"}],
                "amount_left": "amt",
                "amount_right": "amt",
                "tolerance": 0.0,
            },
        )
    assert info.value.code == "TD-SHAPE-002"
    assert info.value.columns == (name,)
    assert f"'{name}'" in str(info.value)


def test_left_match_id_clash_is_renamed_and_lead_keeps_match_numbers() -> None:
    left = pl.DataFrame({"k": ["a", "b"], "amt": [1.0, 2.0], "Match_ID": ["x", "y"]})
    right = pl.DataFrame({"k": ["a", "b"], "amt": [1.0, 2.5]})
    result = reconcile.apply_reconcile(
        left,
        right,
        {
            "key_pairs": [{"left": "k", "right": "k"}],
            "amount_left": "amt",
            "amount_right": "amt",
        },
    )
    assert result.matched.columns == [
        "Match_ID",
        "Match_Status",
        "Amount_Diff",
        "k",
        "amt",
        "Match_ID_2",
        "k_right",
        "amt_right",
    ]
    assert result.matched["Match_ID"].to_list() == [1]
    assert result.matched["Match_ID_2"].to_list() == ["x"]


def test_left_match_status_clash_is_renamed() -> None:
    left = pl.DataFrame(
        {"k": ["a", "b"], "amt": [1.0, 2.0], "Match_Status": ["s1", "s2"]}
    )
    right = pl.DataFrame({"k": ["a", "b"], "amt": [1.0, 2.5]})
    result = reconcile.apply_reconcile(
        left,
        right,
        {
            "key_pairs": [{"left": "k", "right": "k"}],
            "amount_left": "amt",
            "amount_right": "amt",
        },
    )
    assert result.matched.columns == [
        "Match_ID",
        "Match_Status",
        "Amount_Diff",
        "k",
        "amt",
        "Match_Status_2",
        "k_right",
        "amt_right",
    ]
    assert result.matched["Match_Status"].to_list() == ["Within tolerance"]
    assert result.matched["Match_Status_2"].to_list() == ["s1"]


def test_left_amount_diff_clash_is_renamed_when_amounts_are_set() -> None:
    left = pl.DataFrame(
        {"k": ["a", "b"], "amt": [1.0, 2.0], "Amount_Diff": ["d1", "d2"]}
    )
    right = pl.DataFrame({"k": ["a", "b"], "amt": [1.0, 2.5]})
    result = reconcile.apply_reconcile(
        left,
        right,
        {
            "key_pairs": [{"left": "k", "right": "k"}],
            "amount_left": "amt",
            "amount_right": "amt",
        },
    )
    assert result.matched.columns == [
        "Match_ID",
        "Match_Status",
        "Amount_Diff",
        "k",
        "amt",
        "Amount_Diff_2",
        "k_right",
        "amt_right",
    ]
    assert result.matched["Amount_Diff"].to_list() == [0.0]
    assert result.matched["Amount_Diff_2"].to_list() == ["d1"]


def test_left_date_gap_clash_is_renamed_when_dates_are_set() -> None:
    left = pl.DataFrame({"k": ["a"], "d": [date(2025, 1, 3)], "Date_Gap_Days": ["g1"]})
    right = pl.DataFrame({"k": ["a"], "d": [date(2025, 1, 5)]})
    result = reconcile.apply_reconcile(
        left,
        right,
        {
            "key_pairs": [{"left": "k", "right": "k"}],
            "date_left": "d",
            "date_right": "d",
            "date_window_days": 3,
        },
    )
    assert result.matched.columns == [
        "Match_ID",
        "Match_Status",
        "Date_Gap_Days",
        "k",
        "d",
        "Date_Gap_Days_2",
        "k_right",
        "d_right",
    ]
    assert result.matched["Date_Gap_Days"].to_list() == [2]
    assert result.matched["Date_Gap_Days_2"].to_list() == ["g1"]


def test_left_amount_diff_keeps_its_name_without_amounts() -> None:
    left = pl.DataFrame({"k": ["a"], "Amount_Diff": ["keep me"]})
    right = pl.DataFrame({"k": ["a"]})
    result = reconcile.apply_reconcile(
        left,
        right,
        {"key_pairs": [{"left": "k", "right": "k"}]},
    )
    assert result.matched.columns == [
        "Match_ID",
        "Match_Status",
        "k",
        "Amount_Diff",
        "k_right",
    ]
    assert result.matched["Amount_Diff"].to_list() == ["keep me"]


def test_right_column_named_like_a_lead_column_does_not_crash() -> None:
    left = pl.DataFrame({"k": ["a"], "amt": [1.0]})
    right = pl.DataFrame({"k": ["a"], "amt": [1.0], "Match_ID": ["r1"]})
    result = reconcile.apply_reconcile(
        left,
        right,
        {
            "key_pairs": [{"left": "k", "right": "k"}],
            "amount_left": "amt",
            "amount_right": "amt",
        },
    )
    assert result.matched.columns == [
        "Match_ID",
        "Match_Status",
        "Amount_Diff",
        "k",
        "amt",
        "k_right",
        "amt_right",
        "Match_ID_2",
    ]
    assert result.matched["Match_ID"].to_list() == [1]
    assert result.matched["Match_ID_2"].to_list() == ["r1"]


def test_renamed_left_values_stay_on_their_rows() -> None:
    left = pl.DataFrame(
        {"k": ["c", "a", "b"], "amt": [3.0, 1.0, 2.0], "Match_ID": ["z", "x", "y"]}
    )
    right = pl.DataFrame({"k": ["a", "b", "c"], "amt": [1.0, 2.0, 3.0]})
    result = reconcile.apply_reconcile(
        left,
        right,
        {
            "key_pairs": [{"left": "k", "right": "k"}],
            "amount_left": "amt",
            "amount_right": "amt",
        },
    )
    rows = result.matched.rows(named=True)
    assert sorted(row["Match_ID"] for row in rows) == [1, 2, 3]
    assert {row["k"]: row["Match_ID_2"] for row in rows} == {
        "a": "x",
        "b": "y",
        "c": "z",
    }
    assert {row["k"]: row["amt"] for row in rows} == {"a": 1.0, "b": 2.0, "c": 3.0}
    assert {row["k"]: row["amt_right"] for row in rows} == {
        "a": 1.0,
        "b": 2.0,
        "c": 3.0,
    }


def test_left_and_right_clashes_together_get_distinct_names() -> None:
    left = pl.DataFrame({"k": ["a"], "amt": [1.0], "Match_ID": ["x"]})
    right = pl.DataFrame({"k": ["a"], "amt": [1.0], "Match_ID": ["r1"]})
    result = reconcile.apply_reconcile(
        left,
        right,
        {
            "key_pairs": [{"left": "k", "right": "k"}],
            "amount_left": "amt",
            "amount_right": "amt",
        },
    )
    assert result.matched.columns == [
        "Match_ID",
        "Match_Status",
        "Amount_Diff",
        "k",
        "amt",
        "Match_ID_2",
        "k_right",
        "amt_right",
        "Match_ID_3",
    ]
    assert result.matched["Match_ID_2"].to_list() == ["x"]
    assert result.matched["Match_ID_3"].to_list() == ["r1"]
