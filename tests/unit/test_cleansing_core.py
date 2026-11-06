"""Cleansing core: operation order, scope and text rules."""

from __future__ import annotations

import warnings
from collections.abc import Callable

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from trigger_designer.core.shaping import cleansing as core
from trigger_designer.core.shaping.common import ShapingError
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy


def _run(frame: pl.DataFrame, **settings) -> pl.DataFrame:
    return core.run_node([frame.lazy()], settings).pop().collect()


def test_remove_all_null_rows() -> None:
    frame = pl.DataFrame({"a": [1, None], "b": ["x", None]})
    out = _run(frame, remove_null_rows=True)
    assert out.rows() == [(1, "x")]


def test_remove_all_null_columns() -> None:
    frame = pl.DataFrame({"a": [None, None], "b": [1, 2]})
    out = _run(frame, remove_null_columns=True)
    assert out.columns == ["b"]


def test_remove_all_null_columns_keeps_every_row() -> None:
    frame = pl.DataFrame({"a": [None, None], "b": [1, 2]})
    assert _run(frame, remove_null_columns=True).height == 2


def test_remove_all_null_columns_errors_when_nothing_would_be_left() -> None:
    frame = pl.DataFrame({"a": [None, None], "b": [None, None]})
    with pytest.raises(ShapingError) as error:
        _run(frame, remove_null_columns=True)
    assert error.value.code == "TD-SHAPE-005"


def test_remove_rows_null_in_selected_fields() -> None:
    frame = pl.DataFrame({"a": [1, None, 3], "b": ["x", "y", None]})
    out = _run(
        frame,
        remove_null_rows_from_selected_columns=True,
        selected_fields=["a"],
    )
    assert out["a"].to_list() == [1, 3]

    untouched = _run(frame, remove_null_rows_from_selected_columns=True)
    assert untouched.height == 3


def test_replace_null_defaults() -> None:
    frame = pl.DataFrame({"s": [None, "x"], "n": [None, 2]})
    out = _run(frame)
    assert out["s"].to_list() == ["", "x"]
    assert out["n"].to_list() == [0, 2]


def test_whitespace_rules() -> None:
    frame = pl.DataFrame({"c": ["  a  ", "a  b"]})
    out = _run(frame, selected_fields=["c"])
    assert out["c"].to_list() == ["a", "a b"]

    out = _run(frame, selected_fields=["c"], remove_all_whitespace=True)
    assert out["c"].to_list() == ["a", "ab"]


def test_character_removal() -> None:
    frame = pl.DataFrame({"c": ["a1!b"]})
    assert _run(frame, selected_fields=["c"], remove_letters=True)["c"].to_list() == [
        "1!"
    ]
    assert _run(frame, selected_fields=["c"], remove_numbers=True)["c"].to_list() == [
        "a!b"
    ]
    assert _run(frame, selected_fields=["c"], remove_punctuation=True)[
        "c"
    ].to_list() == ["a1b"]


def test_case_modification() -> None:
    frame = pl.DataFrame({"c": ["ab cd"]})
    assert _run(frame, selected_fields=["c"], case_modification="upper")[
        "c"
    ].to_list() == ["AB CD"]
    assert _run(frame, selected_fields=["c"], case_modification="lower")[
        "c"
    ].to_list() == ["ab cd"]
    assert _run(frame, selected_fields=["c"], case_modification="title")[
        "c"
    ].to_list() == ["Ab Cd"]


def test_selected_fields_limit_text_cleanup() -> None:
    frame = pl.DataFrame({"a": [" x "], "b": [" y "]})
    out = _run(frame, selected_fields=["a"])
    assert out["a"].to_list() == ["x"]
    assert out["b"].to_list() == [" y "]


def test_missing_selected_field_is_ignored() -> None:
    frame = pl.DataFrame({"a": [" x "]})
    out = _run(frame, selected_fields=["gone", "a"])
    assert out["a"].to_list() == ["x"]


def test_empty_selection_leaves_text_alone() -> None:
    frame = pl.DataFrame({"a": [" x "]})
    out = _run(frame, selected_fields=[], case_modification="upper")
    assert out["a"].to_list() == [" x "]


def test_empty_input_and_lazy_output() -> None:
    empty = pl.DataFrame(schema={"a": pl.String})
    outs = core.run_node([empty.lazy()], {"selected_fields": ["a"]})
    assert isinstance(outs[0], pl.LazyFrame)
    out = outs[0].collect()
    assert out.height == 0
    assert out.columns == ["a"]


def test_collapse_does_not_trim_when_trim_is_off() -> None:
    frame = pl.DataFrame({"c": ["  a   b  "]})
    out = _run(
        frame, selected_fields=["c"], strip_whitespace=False, normalize_spaces=True
    )
    assert out["c"].to_list() == [" a b "]


def test_trim_alone_keeps_inner_runs() -> None:
    frame = pl.DataFrame({"c": ["  a   b  "]})
    out = _run(
        frame, selected_fields=["c"], strip_whitespace=True, normalize_spaces=False
    )
    assert out["c"].to_list() == ["a   b"]


def test_trim_and_collapse_together() -> None:
    frame = pl.DataFrame({"c": ["  a   b  "]})
    assert _run(frame, selected_fields=["c"])["c"].to_list() == ["a b"]


def test_chip_warns_when_text_rules_have_no_column() -> None:
    assert core.describe([None], {}) == [
        ("No columns ticked: the text rules do nothing", "warning")
    ]
    assert core.describe([None], {"selected_fields": ["c"]}) == []
    quiet = {"strip_whitespace": False, "normalize_spaces": False}
    assert core.describe([None], quiet) == []
    assert core.describe([None], {**quiet, "case_modification": "upper"})


def test_strip_whitespace_takes_trim_as_a_parameter() -> None:
    # The Cleansing node passes ``trim=`` into the cleaner; the keyword must be a
    # real parameter (it was once left as a body statement, which raised
    # NameError on every call).
    from trigger_designer.core.utils.cleansing_util import DataCleansing

    frame = pl.DataFrame({"c": ["  a   b  ", " x "]})
    trimmed = DataCleansing(frame).strip_whitespace(fields=["c"], trim=True)
    kept = DataCleansing(frame).strip_whitespace(
        fields=["c"], trim=False, normalize_spaces=True
    )
    assert trimmed.df["c"].to_list() == ["a b", "x"]
    assert kept.df["c"].to_list() == [" a b ", " x "]


def _counted(frame: pl.DataFrame, calls: list[int]) -> pl.LazyFrame:
    """A LazyFrame whose plan appends to ``calls`` each time it is executed."""

    def record(batch: pl.DataFrame) -> pl.DataFrame:
        calls.append(1)
        return batch

    return frame.lazy().map_batches(record)


def test_text_and_replace_rules_do_not_read_the_input() -> None:
    calls: list[int] = []
    source = _counted(pl.DataFrame({"s": [" a  b ", None], "n": [None, 2]}), calls)
    with warnings.catch_warnings():
        warnings.simplefilter("error", pl.exceptions.PerformanceWarning)
        outs = core.run_node(
            [source], {"selected_fields": ["s"], "case_modification": "upper"}
        )
    assert calls == []
    assert outs[0].collect().rows() == [("A B", 0), ("", 2)]
    assert len(calls) == 1


def test_remove_null_rows_does_not_read_the_input() -> None:
    calls: list[int] = []
    source = _counted(
        pl.DataFrame({"s": ["x", None, None], "n": [1, None, None]}), calls
    )
    outs = core.run_node([source], {"remove_null_rows": True})
    assert calls == []
    assert outs[0].collect().rows() == [("x", 1)]
    assert len(calls) == 1


def test_remove_null_columns_reads_one_summary_then_stays_lazy() -> None:
    calls: list[int] = []
    source = _counted(pl.DataFrame({"gone": [None, None], "kept": [1, 2]}), calls)
    outs = core.run_node([source], {"remove_null_columns": True})
    # Only the one-row null summary runs inside run_node.
    assert len(calls) == 1
    assert_frame_equal(outs[0].collect(), pl.DataFrame({"kept": [1, 2]}))
    # The output is still a plan over the input, so collecting reads it again.
    assert len(calls) == 2


MIXED = pl.DataFrame(
    {
        "name": ["  Ann ", None, "Bob  Lee", None],
        "city": ["  Paris", "Rome  ", None, None],
        "qty": [1, None, 3, None],
        "price": [2.5, None, 1.0, None],
        "gone": [None, None, None, None],
        "full": [" x ", "y  z", "w", " v"],
    },
    schema={
        "name": pl.String,
        "city": pl.String,
        "qty": pl.Int64,
        "price": pl.Float64,
        "gone": pl.String,
        "full": pl.String,
    },
)


@pytest.mark.parametrize("strategy", list(NullStrategy), ids=lambda s: s.value)
def test_lazy_handle_nulls_matches_dataframe(strategy: NullStrategy) -> None:
    eager = DataCleansing(MIXED).handle_nulls(strategy).get_result()
    lazy = DataCleansing(MIXED.lazy()).handle_nulls(strategy).get_result()
    assert isinstance(eager, pl.DataFrame)
    assert isinstance(lazy, pl.LazyFrame)
    assert_frame_equal(lazy.collect(), eager)


STEPS: list[Callable[[DataCleansing], DataCleansing]] = [
    lambda c: c.replace_null_defaults(),
    lambda c: c.replace_null_defaults(replace_strings=False, default_num=-1),
    lambda c: c.strip_whitespace(fields=["name", "city"]),
    lambda c: c.strip_whitespace(remove_all=True),
    lambda c: c.remove_characters(remove_letters=True),
    lambda c: c.remove_characters(remove_numbers=True, fields=["full"]),
    lambda c: c.modify_case("title"),
    lambda c: c.modify_case("lower", fields=["city"]),
    lambda c: c.handle_nulls(NullStrategy.REMOVE_ALL_NULL_COLS).strip_whitespace(),
]


@pytest.mark.parametrize("step", STEPS)
def test_lazy_text_and_default_steps_match_dataframe(step) -> None:
    eager = step(DataCleansing(MIXED)).get_result()
    lazy = step(DataCleansing(MIXED.lazy())).get_result()
    assert isinstance(lazy, pl.LazyFrame)
    assert_frame_equal(lazy.collect(), eager)


def test_set_data_accepts_a_lazyframe() -> None:
    cleaner = DataCleansing().set_data(MIXED.lazy())
    assert isinstance(cleaner.get_result(), pl.LazyFrame)
