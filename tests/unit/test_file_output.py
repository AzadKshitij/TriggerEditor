#!/usr/bin/env python3
"""File Output node codegen tests.

The streaming `sink_*` calls require a polars with the streaming-engine
"dtype is unknown" fix (see `_join_union_plan`, which panicked on
polars 1.33.1 and sinks cleanly on 1.44.2+).
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
from qtpy.QtWidgets import QApplication

APP = QApplication.instance() or QApplication([])


def _make_content(**kwargs):
    """Logic-only content (no scene): get_code is pure."""
    from trigger_designer.qt.widgets.nodes.InOut.file_output import (
        FileOutputContent,
    )

    content = FileOutputContent.__new__(FileOutputContent)
    content.incoming_variable = kwargs.get("incoming_variable", "var_in")
    content.filePath = kwargs.get("filePath", "out.csv")
    content.file_format = kwargs.get("file_format", "csv")
    content.delimiter = kwargs.get("delimiter", ",")
    content.use_streaming = kwargs.get("use_streaming", True)
    content.include_bom = kwargs.get("include_bom", False)
    return content


def _join_union_plan():
    """Join + filter + diagonal concat: panicked under sink on polars 1.33.1."""
    orders = pl.LazyFrame({"oid": ["o1", "o2"], "cid": [1, 2], "amt": [10.0, 20.0]})
    cust = pl.LazyFrame({"cid": [1, 3], "name": ["a", "c"]})
    joined = orders.with_columns(pl.lit(1).alias("__l")).join(
        cust.with_columns(pl.lit(1).alias("__r")),
        left_on=["cid"],
        right_on=["cid"],
        how="full",
        coalesce=True,
    )
    matched = joined.filter(
        pl.col("__l").is_not_null() & pl.col("__r").is_not_null()
    ).select(["oid", "cid", "amt", "name"])
    left_only = joined.filter(pl.col("__r").is_null()).select(["oid", "cid", "amt"])
    return pl.concat([matched, left_only], how="diagonal_relaxed")


def test_csv_codegen_uses_streaming_sink() -> None:
    code = _make_content().get_code()
    assert "sink_csv" in code
    assert "collect().write_csv" not in code


def test_csv_options_reach_sink() -> None:
    code = _make_content(delimiter=";", include_bom=True).get_code()
    assert code.count('separator=";"') == 1
    assert code.count("include_bom=True") == 1


def test_other_formats_use_streaming_sinks() -> None:
    assert "sink_csv" in _make_content(file_format="custom_delimited").get_code()
    assert "sink_parquet" in _make_content(file_format="parquet").get_code()
    assert "sink_ndjson" in _make_content(file_format="ndjson").get_code()
    assert "sink_ipc" in _make_content(file_format="ipc").get_code()


def test_no_input_fails_loudly() -> None:
    code = _make_content(incoming_variable="").get_code()
    assert "ValueError" in code


def test_backslash_path_is_exported_forward_slash() -> None:
    code = _make_content(filePath=r"C:\data\out.csv").get_code()
    assert "C:/data/out.csv" in code
    assert "\\" not in code.split("if var_in is not None:")[1]


def test_generated_csv_code_writes_join_union_plan(tmp_path) -> None:
    """Exec the emitted code against the former panicking plan."""
    out = str(tmp_path / "out.csv")
    code = _make_content(filePath=out).get_code()
    scope = {"var_in": _join_union_plan()}
    exec(compile(code, "<file_output>", "exec"), scope)  # noqa: S102
    result = pl.read_csv(out)
    assert result.shape == (2, 4)
    assert result["oid"].to_list() == ["o1", "o2"]


def test_generated_csv_code_writes_plain_plan(tmp_path) -> None:
    out = str(tmp_path / "plain.csv")
    code = _make_content(filePath=out).get_code()
    scope = {"var_in": pl.LazyFrame({"a": [1, 2]})}
    exec(compile(code, "<file_output>", "exec"), scope)  # noqa: S102
    assert pl.read_csv(out)["a"].to_list() == [1, 2]


def test_check_output_header_puts_src_on_path(tmp_path, monkeypatch) -> None:
    from trigger_designer.qt.design_window import CHECK_OUTPUT_HEADER

    (tmp_path / "src").mkdir()
    fake_script = str(tmp_path / "check_output.py")
    monkeypatch.setattr(sys, "path", list(sys.path))
    exec(compile(CHECK_OUTPUT_HEADER, "<header>", "exec"), {"__file__": fake_script})  # noqa: S102
    assert str(tmp_path / "src") in sys.path
