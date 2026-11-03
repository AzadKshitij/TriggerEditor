"""Cleansing core: operation order, scope and text rules."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping import cleansing as core


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
