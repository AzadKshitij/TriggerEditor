"""P1 shaping cores: hand-computed expectations."""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from trigger_designer.core.shaping import (
    date_helper,
    find_replace,
    reconcile,
    record_id,
    reshape,
    select_records,
)
from trigger_designer.core.shaping.common import ShapingError


def test_record_id_first_and_grouped() -> None:
    frame = pl.DataFrame({"g": ["b", "a", "a"], "v": [1, 2, 3]}).lazy()
    out = record_id.apply_record_id(frame, {"name": "ID", "start": 10}).collect()
    assert out.columns == ["ID", "g", "v"]
    assert out["ID"].to_list() == [10, 11, 12]

    grouped = record_id.apply_record_id(
        frame,
        {
            "name": "ID",
            "start": 1,
            "position": "last",
            "group_by": ["g"],
            "order_by": [{"column": "v", "descending": True}],
        },
    ).collect()
    assert grouped.columns == ["g", "v", "ID"]
    assert grouped.rows() == [("b", 1, 1), ("a", 2, 2), ("a", 3, 1)]


def test_record_id_errors() -> None:
    frame = pl.DataFrame({"a": [1]}).lazy()
    with pytest.raises(ShapingError) as error:
        record_id.apply_record_id(frame, {"name": ""})
    assert error.value.code == "TD-SHAPE-001"
    with pytest.raises(ShapingError) as error:
        record_id.apply_record_id(frame, {"name": "a"})
    assert error.value.code == "TD-SHAPE-002"
    with pytest.raises(ShapingError) as error:
        record_id.apply_record_id(frame, {"group_by": ["zzz"]})
    assert error.value.code == "TD-SHAPE-003"


def test_record_id_accepts_negative_and_huge_start() -> None:
    frame = pl.DataFrame({"v": [1, 2, 3]}).lazy()
    negative = record_id.apply_record_id(frame, {"name": "ID", "start": -1})
    assert negative.collect()["ID"].to_list() == [-1, 0, 1]
    huge = record_id.apply_record_id(frame, {"name": "ID", "start": 4294967295})
    assert huge.collect()["ID"].to_list() == [4294967295, 4294967296, 4294967297]


def test_select_records_first_and_rest() -> None:
    frame = pl.DataFrame({"v": list(range(1, 6))}).lazy()
    selected, rest = select_records.apply_select_records(
        frame, {"mode": "first_n", "n": 2}
    )
    assert selected.collect()["v"].to_list() == [1, 2]
    assert rest.collect()["v"].to_list() == [3, 4, 5]


def test_select_records_range_and_ranked_ties() -> None:
    frame = pl.DataFrame({"v": [3, 1, 2, 2]}).lazy()
    selected, rest = select_records.apply_select_records(
        frame, {"mode": "row_range", "range_start": 2, "range_end": 3}
    )
    assert selected.collect()["v"].to_list() == [1, 2]
    assert rest.collect()["v"].to_list() == [3, 2]

    selected, _rest = select_records.apply_select_records(
        frame, {"mode": "largest_n", "n": 2, "by": "v", "ties": "include_ties"}
    )
    assert selected.collect()["v"].to_list() == [3, 2, 2]


def test_find_replace_literal_regex_suffix() -> None:
    frame = pl.DataFrame({"s": ["Alpha", "beta", None]}).lazy()
    out = find_replace.apply_find_replace(
        frame,
        {
            "columns": ["s"],
            "rules": [{"find": "a", "replace": "X"}],
        },
    ).collect()
    assert out["s"].to_list() == ["XlphX", "betX", None]

    regex = find_replace.apply_find_replace(
        frame,
        {
            "columns": ["s"],
            "rules": [{"find": "(a)", "replace": "[$1]", "mode": "regex"}],
            "suffix": "_new",
        },
    ).collect()
    assert regex.columns == ["s", "s_new"]
    assert regex["s_new"].to_list() == ["[A]lph[a]", "bet[a]", None]


def test_find_replace_errors() -> None:
    frame = pl.DataFrame({"s": ["a"], "n": [1]}).lazy()
    with pytest.raises(ShapingError) as error:
        find_replace.apply_find_replace(frame, {"columns": []})
    assert error.value.code == "TD-SHAPE-001"
    with pytest.raises(ShapingError) as error:
        find_replace.apply_find_replace(
            frame, {"columns": ["n"], "rules": [{"find": "x"}]}
        )
    assert error.value.code == "TD-SHAPE-044"
    with pytest.raises(ShapingError) as error:
        find_replace.apply_find_replace(
            frame, {"columns": ["s"], "rules": [{"find": "(", "mode": "regex"}]}
        )
    assert error.value.code == "TD-SHAPE-040"


def test_date_helper_calendar_and_fiscal() -> None:
    frame = pl.DataFrame({"d": [date(2024, 4, 1), date(2024, 12, 31)]}).lazy()
    out = date_helper.apply_date_helper(
        frame,
        {
            "fiscal_start_month": 4,
            "ops": [
                {"op": "weekday_name", "source": "d"},
                {"op": "fiscal_year", "source": "d"},
                {"op": "fiscal_period", "source": "d"},
                {"op": "is_month_end", "source": "d"},
            ],
        },
    ).collect()
    assert out["d_weekday_name"].to_list() == ["Monday", "Tuesday"]
    assert out["d_fiscal_year"].to_list() == [2025, 2025]
    assert out["d_fiscal_period"].to_list() == [1, 9]
    assert out["d_is_month_end"].to_list() == [False, True]


def test_date_helper_add_days_and_business() -> None:
    frame = pl.DataFrame({"d": [date(2024, 4, 5)]}).lazy()
    out = date_helper.apply_date_helper(
        frame,
        {
            "holidays": "2024-04-08",
            "ops": [
                {"op": "add_days", "source": "d", "n": 3},
                {"op": "add_business_days", "source": "d", "n": 1},
            ],
        },
    ).collect()
    assert out["d_add_days"].to_list() == [date(2024, 4, 8)]
    assert out["d_add_business_days"].to_list() == [date(2024, 4, 9)]


def test_pivot_unpivot_roundtrip() -> None:
    frame = pl.DataFrame(
        {"id": [1, 1, 2], "attr": ["x", "y", "x"], "value": [10, 20, 30]}
    ).lazy()
    wide = reshape.apply_pivot(
        frame,
        {"index_columns": ["id"], "header_column": "attr", "value_column": "value"},
    )
    long = reshape.apply_unpivot(
        wide.lazy(),
        {
            "id_columns": ["id"],
            "value_columns": ["x", "y"],
            "drop_nulls": True,
        },
    ).collect()
    assert long.sort(["id", "Attribute"]).rows() == [
        (1, "x", 10.0),
        (1, "y", 20.0),
        (2, "x", 30.0),
    ]


def test_reconcile_one_to_one_summary() -> None:
    left = pl.DataFrame({"k": ["a", "b"], "amt": [10.0, 20.0]}).lazy()
    right = pl.DataFrame({"k": ["a", "c"], "amt": [10.5, 20.0]}).lazy()
    result = reconcile.apply_reconcile(
        left,
        right,
        {
            "key_pairs": [{"left": "k", "right": "k"}],
            "amount_left": "amt",
            "amount_right": "amt",
            "tolerance": 1.0,
        },
    )
    assert result.matched.rows() == [(1, "Within tolerance", 0.5, "a", 10.0, "a", 10.5)]
    assert result.left_unmatched.height == 1
    assert result.right_unmatched.height == 1
    row = result.summary.row(0, named=True)
    assert row["Matched_Groups"] == 1
    assert row["Left_Matched_Rows"] == 1
    assert row["Left_Match_Rate_Pct"] == 50.0
    assert row["Within_Tolerance_Groups"] == 1


def test_reconcile_without_amounts_labels_matches() -> None:
    left = pl.DataFrame({"k": ["a"]}).lazy()
    right = pl.DataFrame({"k": ["a"]}).lazy()
    result = reconcile.apply_reconcile(
        left,
        right,
        {"key_pairs": [{"left": "k", "right": "k"}]},
    )
    assert result.matched["Match_Status"].to_list() == ["Matched"]


def test_reconcile_requires_key_or_date() -> None:
    left = pl.DataFrame({"k": ["a"]}).lazy()
    with pytest.raises(ShapingError) as error:
        reconcile.apply_reconcile(left, left, {})
    assert error.value.code == "TD-SHAPE-071"
