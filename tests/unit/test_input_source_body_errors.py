"""File Input: errors in a file's body under "Skip and report", and who they blame."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.input_source import (
    build_source,
    diagnose_collect_error,
)


def _state(path, **extra) -> dict:
    return {"filePath": str(path), "file_type": "csv", **extra}


def _folder(tmp_path):
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "a_good.csv").write_text("id,name\n1,x\n2,y\n", encoding="utf-8")
    return folder


def test_bad_byte_in_body_is_skipped_and_named(tmp_path) -> None:
    folder = _folder(tmp_path)
    (folder / "b_bad.csv").write_bytes(b"id,name\n3,ok\n4,caf\xe9\n")
    result = build_source(_state(folder, on_file_error="skip"))
    frame = result.frame.collect()
    assert frame["id"].to_list() == ["1", "2"]
    assert result.report.skipped_count == 1
    skipped = [f for f in result.report.files if f.status == "skipped"]
    assert skipped[0].path.endswith("b_bad.csv")
    assert skipped[0].error["kind"] == "encoding"
    assert skipped[0].error["code"] == "TD-IN-004"


def test_over_long_row_in_body_is_skipped_and_named(tmp_path) -> None:
    folder = _folder(tmp_path)
    (folder / "c_wide.csv").write_text("id,name\n5,x\n6,y,z,extra\n", encoding="utf-8")
    result = build_source(_state(folder, on_file_error="skip"))
    assert result.frame.collect()["id"].to_list() == ["1", "2"]
    skipped = [f for f in result.report.files if f.status == "skipped"]
    assert [f.path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for f in skipped] == [
        "c_wide.csv"
    ]
    assert skipped[0].error["kind"] == "parse"
    assert skipped[0].error["code"] == "TD-IN-010"


def test_stop_policy_still_fails_at_collect(tmp_path) -> None:
    folder = _folder(tmp_path)
    (folder / "b_bad.csv").write_bytes(b"id,name\n3,ok\n4,caf\xe9\n")
    result = build_source(_state(folder))
    with pytest.raises(pl.exceptions.PolarsError):
        result.frame.collect()


def test_diagnose_names_the_file_among_several(tmp_path) -> None:
    folder = _folder(tmp_path)
    (folder / "b_bad.csv").write_bytes(b"id,name\n3,ok\n4,caf\xe9\n")
    state = _state(folder)
    result = build_source(state)
    with pytest.raises(pl.exceptions.PolarsError) as raised:
        result.frame.collect()
    error = diagnose_collect_error(raised.value, result.report, state)
    assert error.path is not None and error.path.endswith("b_bad.csv")
    assert "b_bad.csv" in str(error)
    assert error.code == "TD-IN-004"


def test_diagnose_without_state_says_how_many_files_not_just_the_input(
    tmp_path,
) -> None:
    folder = _folder(tmp_path)
    (folder / "b_bad.csv").write_bytes(b"id,name\n3,ok\n4,caf\xe9\n")
    result = build_source(_state(folder))
    with pytest.raises(pl.exceptions.PolarsError) as raised:
        result.frame.collect()
    error = diagnose_collect_error(raised.value, result.report)
    assert "one of the 2 input files" in str(error).lower()
