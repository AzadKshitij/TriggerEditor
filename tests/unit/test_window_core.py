"""Window core: hand-computed expectations, errors, and live/generated agreement."""

from __future__ import annotations

import ast
import json
import random
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from trigger_designer.core.shaping import window as core
from trigger_designer.core.shaping.common import ERROR_CODES, ShapingError
from trigger_designer.core.shaping.window import apply_window, run_node

# acct  d  v
# A     3  "10"     partition A by d: d1 null, d2 "7", d3 "10"
# A     1  null     partition B by d: d1 "5",  d2 "8", d3 "9"
# B     1  "5"
# A     2  "7"
# B     2  "8"
# B     3  "9"
WN = pl.DataFrame(
    {
        "acct": ["A", "A", "B", "A", "B", "B"],
        "d": [3, 1, 1, 2, 2, 3],
        "v": ["10", None, "5", "7", "8", "9"],
    }
)
PART = {"partition_by": ["acct"], "order_by": [{"column": "d"}]}


def _op(op: str, **kw) -> dict:
    return {"op": op, "source": "v", **kw}


def _run(settings: dict, frame: pl.DataFrame = WN) -> pl.DataFrame:
    return apply_window(frame, settings).collect()


def _col(name: str, ops: list[dict], **extra) -> list:
    return _run({**PART, **extra, "ops": ops})[name].to_list()


def test_lag_and_lead_keep_text_and_input_order() -> None:
    out = _run({**PART, "ops": [_op("lag"), _op("lead")]})
    assert out.columns == ["acct", "d", "v", "v_lag1", "v_lead1"]
    assert out["d"].to_list() == [3, 1, 1, 2, 2, 3]
    assert out["v_lag1"].to_list() == ["7", None, None, None, "5", "8"]
    assert out["v_lead1"].to_list() == [None, "7", "8", "10", "9", None]
    assert out.schema["v_lag1"] == pl.String


def test_lag_offset_two_and_default_name() -> None:
    out = _run({"ops": [{"op": "lag", "source": "d", "offset": 2}]})
    assert out["d_lag2"].to_list() == [None, None, 3, 1, 1, 2]
    assert out.schema["d_lag2"] == pl.Int64


def test_row_number_ignores_source_and_is_int64() -> None:
    out = _run({**PART, "ops": [{"op": "row_number", "source": "nonexistent"}]})
    assert out["Row_Number"].to_list() == [3, 1, 1, 2, 2, 3]
    assert out.schema["Row_Number"] == pl.Int64
    plain = _run({"ops": [{"op": "row_number"}]})
    assert plain["Row_Number"].to_list() == [1, 2, 3, 4, 5, 6]


def test_rank_descending_null_stays_null() -> None:
    assert _col("v_rank", [_op("rank", descending=True)]) == [1, None, 3, 2, 2, 1]
    assert _col("v_rank", [_op("rank")]) == [2, None, 1, 1, 2, 3]


def test_rank_ties_share_rank_and_dense_rank_has_no_gaps() -> None:
    frame = pl.DataFrame({"v": ["5", "5", "9", "1"]})
    out = _run(
        {
            "ops": [
                {"op": "rank", "source": "v", "name": "r"},
                {"op": "dense_rank", "source": "v", "name": "dr"},
            ]
        },
        frame,
    )
    assert out["r"].to_list() == [2, 2, 4, 1]
    assert out["dr"].to_list() == [2, 2, 3, 1]


def test_rank_reads_text_as_numbers_and_accepts_dates() -> None:
    frame = pl.DataFrame({"t": ["10", "9", "1,000"]})
    out = _run({"ops": [{"op": "rank", "source": "t"}]}, frame)
    assert out["t_rank"].to_list() == [2, 1, 3]  # numeric, not lexicographic
    dates = pl.DataFrame({"d": [date(2024, 3, 1), date(2024, 1, 1)]})
    out = _run({"ops": [{"op": "rank", "source": "d"}]}, dates)
    assert out["d_rank"].to_list() == [2, 1]


def test_cumulative_ops_skip_nulls_by_default() -> None:
    assert _col("v_cum_sum", [_op("cum_sum")]) == [17.0, None, 5.0, 7.0, 13.0, 22.0]
    assert _col("v_cum_min", [_op("cum_min")]) == [7, None, 5, 7, 5, 5]
    assert _col("v_cum_max", [_op("cum_max")]) == [10, None, 5, 7, 8, 9]
    mean = _col("v_cum_mean", [_op("cum_mean")])
    assert mean[0] == 8.5 and mean[1] is None and mean[2] == 5.0
    assert mean[5] == pytest.approx(22 / 3)
    assert _run({**PART, "ops": [_op("cum_sum")]}).schema["v_cum_sum"] == pl.Float64


def test_nulls_zero_mode_counts_nulls_as_zero() -> None:
    assert _col("cs", [_op("cum_sum", name="cs", nulls="zero")]) == [
        17.0,
        0.0,
        5.0,
        7.0,
        13.0,
        22.0,
    ]
    mean = _col("cm", [_op("cum_mean", name="cm", nulls="zero")])
    assert mean[0] == pytest.approx(17 / 3) and mean[1] == 0.0


def test_rolling_sum_strict_and_partial() -> None:
    assert _col("r", [_op("rolling_sum", name="r", window=2)]) == [
        17.0,
        None,
        None,
        None,
        13.0,
        17.0,
    ]
    assert _col("r", [_op("rolling_sum", name="r", window=2, partial=True)]) == [
        17.0,
        None,
        5.0,
        7.0,
        13.0,
        17.0,
    ]
    assert _col("r", [_op("rolling_sum", name="r", window=10)]) == [None] * 6


def test_default_names_for_every_op() -> None:
    out = _run(
        {
            "ops": [
                _op("lag", offset=3),
                _op("lead"),
                {"op": "row_number"},
                _op("rank"),
                _op("dense_rank"),
                _op("cum_sum"),
                _op("cum_min"),
                _op("cum_max"),
                _op("cum_mean"),
                _op("rolling_sum", window=4),
            ]
        }
    )
    assert out.columns[3:] == [
        "v_lag3",
        "v_lead1",
        "Row_Number",
        "v_rank",
        "v_dense_rank",
        "v_cum_sum",
        "v_cum_min",
        "v_cum_max",
        "v_cum_mean",
        "v_roll4",
    ]


def test_no_partition_is_one_window_and_order_descending() -> None:
    out = _run(
        {
            "order_by": [{"column": "d", "descending": True}],
            "ops": [{"op": "row_number"}],
        }
    )
    # d = [3,1,1,2,2,3] sorted high to low, ties by position: rows 0,5,3,4,1,2
    assert out["Row_Number"].to_list() == [1, 5, 6, 3, 4, 2]


def test_order_nulls_last_and_ties_by_position() -> None:
    frame = pl.DataFrame({"k": [None, 2, 2, 1]})
    ops = [{"op": "row_number", "name": "n"}]
    asc = _run({"order_by": [{"column": "k"}], "ops": ops}, frame)
    assert asc["n"].to_list() == [4, 2, 3, 1]
    desc = _run({"order_by": [{"column": "k", "descending": True}], "ops": ops}, frame)
    assert desc["n"].to_list() == [4, 1, 2, 3]  # nulls still last


def test_multiple_order_keys_use_their_own_direction() -> None:
    frame = pl.DataFrame({"a": [1, 1, 2, 2], "b": [1, 2, 1, 2]})
    out = _run(
        {
            "order_by": [{"column": "a"}, {"column": "b", "descending": True}],
            "ops": [{"op": "row_number", "name": "n"}],
        },
        frame,
    )
    assert out["n"].to_list() == [2, 1, 4, 3]


def test_without_order_by_partition_uses_input_order() -> None:
    out = _run({"partition_by": ["acct"], "ops": [_op("lag")]})
    assert out["v_lag1"].to_list() == [None, "10", None, None, "5", "8"]


def test_text_with_junk_is_null_never_an_error() -> None:
    frame = pl.DataFrame({"v": ["1", "x", "3"]})
    out = _run({"ops": [{"op": "cum_sum", "source": "v"}]}, frame)
    assert out["v_cum_sum"].to_list() == [1.0, None, 4.0]


def test_empty_frame_is_typed() -> None:
    empty = pl.DataFrame(schema={"g": pl.String, "x": pl.Int64})
    out = _run(
        {
            "partition_by": ["g"],
            "order_by": [{"column": "x"}],
            "ops": [
                {"op": "lag", "source": "x"},
                {"op": "cum_sum", "source": "x"},
                {"op": "row_number"},
                {"op": "rank", "source": "x"},
            ],
        },
        empty,
    )
    assert out.height == 0
    assert out.schema["x_lag1"] == pl.Int64
    assert out.schema["x_cum_sum"] == pl.Float64
    assert out.schema["Row_Number"] == pl.Int64
    assert out.schema["x_rank"] == pl.Int64


def test_no_ops_returns_input_unchanged() -> None:
    assert _run({"partition_by": ["acct"]}).equals(WN)


def test_input_columns_are_preserved() -> None:
    out = _run({**PART, "ops": [_op("lag")]})
    assert out.select("acct", "d", "v").equals(WN)


# ----------------------------------------------------------------- errors
def _code(settings: dict, frame: pl.DataFrame = WN) -> str:
    with pytest.raises(ShapingError) as info:
        apply_window(frame, settings).collect_schema()
    return info.value.code


def test_error_missing_source_001() -> None:
    assert _code({"ops": [{"op": "lag"}]}) == "TD-SHAPE-001"
    assert _code({"order_by": [{"column": ""}], "ops": []}) == "TD-SHAPE-001"


def test_error_output_name_clash_002() -> None:
    assert _code({"ops": [_op("lag", name="v")]}) == "TD-SHAPE-002"
    assert _code({"ops": [_op("lag"), _op("lag")]}) == "TD-SHAPE-002"
    assert _code({"ops": [_op("lag", name="__pos")]}) == "TD-SHAPE-002"
    assert _code({"ops": [{"op": "row_number"}, {"op": "row_number"}]}) == (
        "TD-SHAPE-002"
    )
    clash = pl.DataFrame({"v": ["1"], "v_lag1": ["2"]})
    assert _code({"ops": [_op("lag")]}, clash) == "TD-SHAPE-002"


def test_error_missing_column_003() -> None:
    assert _code({"partition_by": ["zz"], "ops": []}) == "TD-SHAPE-003"
    assert _code({"order_by": [{"column": "zz"}], "ops": []}) == "TD-SHAPE-003"
    assert _code({"ops": [{"op": "lag", "source": "zz"}]}) == "TD-SHAPE-003"


def test_error_out_of_range_004() -> None:
    assert _code({"ops": [_op("lag", offset=0)]}) == "TD-SHAPE-004"
    assert _code({"ops": [_op("lead", offset=-1)]}) == "TD-SHAPE-004"
    assert _code({"ops": [_op("rolling_sum", window=0)]}) == "TD-SHAPE-004"
    assert _code({"ops": [_op("bogus")]}) == "TD-SHAPE-004"
    assert _code({"ops": [_op("cum_sum", nulls="maybe")]}) == "TD-SHAPE-004"
    assert _code({"ops": [_op("lag", offset="x")]}) == "TD-SHAPE-004"


def test_offset_and_window_are_ignored_by_ops_that_do_not_use_them() -> None:
    out = _run({"ops": [_op("cum_sum", offset=0, window=0)]})
    assert "v_cum_sum" in out.columns


def test_error_not_numeric_091() -> None:
    frame = pl.DataFrame({"d": [date(2024, 1, 1)], "b": [True]})
    for op in ("cum_sum", "rolling_sum"):
        assert _code({"ops": [{"op": op, "source": "d"}]}, frame) == "TD-SHAPE-091"
    assert _code({"ops": [{"op": "rank", "source": "b"}]}, frame) == "TD-SHAPE-091"
    out = _run({"ops": [{"op": "lag", "source": "d"}]}, frame)  # lag takes anything
    assert out.schema["d_lag1"] == pl.Date


def test_error_message_has_code_prefix_for_live_and_run() -> None:
    with pytest.raises(ShapingError, match=r"^\[TD-SHAPE-001\]"):
        run_node([WN.lazy()], {"ops": [{"op": "lag"}]})


def test_code_091_is_registered_in_both_tables() -> None:
    from trigger_designer.core.errors.catalogue import CATALOGUE

    assert "TD-SHAPE-091" in ERROR_CODES
    assert "TD-SHAPE-091" in CATALOGUE


# ------------------------------------------------- run_node, lazy, no Qt
def test_run_node_returns_one_lazyframe_and_accepts_dataframe() -> None:
    outs = run_node([WN], {"ops": [{"op": "row_number"}]})
    assert len(outs) == 1 and isinstance(outs[0], pl.LazyFrame)


def test_settings_are_not_mutated() -> None:
    settings = {"ops": [{"op": "lag", "source": "v"}]}
    before = json.dumps(settings)
    run_node([WN.lazy()], settings)
    assert json.dumps(settings) == before


def test_core_module_has_no_qt_import() -> None:
    roots = set()
    for node in ast.walk(ast.parse(Path(core.__file__).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert not ({"PySide6", "PyQt5", "PyQt6", "qtpy"} & roots)


def test_seeded_random_matches_row_by_row_reference() -> None:
    rng = random.Random(7)
    rows = [
        (rng.choice("ab"), rng.randint(0, 5), rng.choice([None, 1, 2, 3]))
        for _ in range(60)
    ]
    frame = pl.DataFrame(
        {
            "g": [r[0] for r in rows],
            "k": [r[1] for r in rows],
            "x": [r[2] for r in rows],
        },
        schema={"g": pl.String, "k": pl.Int64, "x": pl.Int64},
    )
    out = _run(
        {
            "partition_by": ["g"],
            "order_by": [{"column": "k"}],
            "ops": [
                {"op": "lag", "source": "x", "name": "lag"},
                {"op": "cum_sum", "source": "x", "name": "cs"},
                {"op": "row_number", "name": "rn"},
            ],
        },
        frame,
    )
    for group in "ab":
        idx = sorted(
            (i for i, r in enumerate(rows) if r[0] == group),
            key=lambda i: (rows[i][1], i),
        )
        total = 0.0
        for n, i in enumerate(idx):
            assert out["rn"][i] == n + 1
            assert out["lag"][i] == (rows[idx[n - 1]][2] if n else None)
            x = rows[i][2]
            if x is not None:
                total += x
            assert out["cs"][i] == (total if x is not None else None), (group, n)
