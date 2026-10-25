#!/usr/bin/env python3
"""File Output: the core writer and the generated-code entry point.

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
import pytest
from qtpy.QtWidgets import QApplication

from trigger_designer.core.shaping import file_output as core

APP = QApplication.instance() or QApplication([])


def _make_content(**overrides):
    """Logic-only content (no scene): get_code reads settings and input_vars."""
    from trigger_designer.qt.widgets.nodes.InOut.file_output import (
        FileOutputContent,
    )

    incoming = overrides.pop("incoming_variable", "var_in")
    content = FileOutputContent.__new__(FileOutputContent)
    content.settings = {**core.DEFAULTS, **overrides}
    content.input_vars = [incoming]
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


def test_generated_code_uses_the_core_writer() -> None:
    code = _make_content().get_code()
    assert "trigger_designer.core.shaping.file_output" in code
    assert "write_node" in code
    assert "collect().write_csv" not in code


def test_no_input_fails_loudly() -> None:
    code = _make_content(incoming_variable="").get_code()
    assert "ValueError" in code


def test_live_runner_never_writes(tmp_path) -> None:
    out = tmp_path / "live.csv"
    outs = core.run_node([pl.DataFrame({"a": [1]}).lazy()], {"filePath": str(out)})
    assert outs == []
    assert not out.exists()


def test_empty_path_is_an_error() -> None:
    with pytest.raises(ValueError):
        core.write_node([pl.DataFrame({"a": [1]})], {})


def test_csv_delimiter_and_bom(tmp_path) -> None:
    out = tmp_path / "out.csv"
    core.write_node(
        [pl.DataFrame({"a": [1], "b": [2]})],
        {"filePath": str(out), "delimiter": ";", "include_bom": True},
    )
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"a;b" in raw


def test_other_formats_write(tmp_path) -> None:
    frame = pl.DataFrame({"a": [1, 2]})
    cases = {
        "parquet": ("out.parquet", pl.read_parquet),
        "json": ("out.json", pl.read_json),
        "ndjson": ("out.ndjson", pl.read_ndjson),
        "ipc": ("out.ipc", pl.read_ipc),
    }
    for file_format, (name, reader) in cases.items():
        out = tmp_path / name
        core.write_node([frame], {"filePath": str(out), "file_format": file_format})
        assert out.exists(), file_format
        assert reader(out)["a"].to_list() == [1, 2], file_format


def test_custom_delimited_uses_separator(tmp_path) -> None:
    out = tmp_path / "out.txt"
    core.write_node(
        [pl.DataFrame({"a": [1], "b": [2]})],
        {
            "filePath": str(out),
            "file_format": "custom_delimited",
            "delimiter": "|",
        },
    )
    assert "a|b" in out.read_text(encoding="utf-8")


def test_input_is_not_modified(tmp_path) -> None:
    frame = pl.DataFrame({"a": [1, 2]})
    before = frame.clone()
    core.write_node([frame], {"filePath": str(tmp_path / "x.csv")})
    assert frame.equals(before)


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


def test_windows_path_survives_generated_code(tmp_path) -> None:
    out = str(tmp_path / "win path.csv").replace("/", "\\")
    code = _make_content(filePath=out).get_code()
    scope = {"var_in": pl.LazyFrame({"a": [1]})}
    exec(compile(code, "<file_output>", "exec"), scope)  # noqa: S102
    assert os.path.exists(out)


def test_check_output_header_puts_src_on_path(tmp_path, monkeypatch) -> None:
    from trigger_designer.qt.design_window import CHECK_OUTPUT_HEADER

    (tmp_path / "src").mkdir()
    fake_script = str(tmp_path / "check_output.py")
    monkeypatch.setattr(sys, "path", list(sys.path))
    exec(compile(CHECK_OUTPUT_HEADER, "<header>", "exec"), {"__file__": fake_script})  # noqa: S102
    assert str(tmp_path / "src") in sys.path
