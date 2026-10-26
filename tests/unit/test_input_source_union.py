"""Folder/glob union, report and deterministic-order tests."""

from __future__ import annotations

import os

import polars as pl
import pytest

from tests.support.input_fixtures import monthly_csvs, parquet_files, write_text
from trigger_designer.core.input_source import build_source
from trigger_designer.core.inputs import InputReadError


def _state(path, file_type: str = "csv", **extra) -> dict:
    state = {"filePath": str(path), "file_type": file_type}
    state.update(extra)
    return state


def test_union_by_name_fills_missing_with_null(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    result = build_source(_state(monthly, output_filename_as_field=True))
    frame = result.frame.collect()
    assert frame.columns == ["id", "region", "amount", "channel", "FileName"]
    assert frame.height == 5
    assert frame["channel"].to_list() == [None, None, None, "web", "store"]
    assert set(frame["FileName"].to_list()) == {
        "sales_2024-01.csv",
        "sales_2024-02.csv",
        "sales_2024-03.csv",
    }


def test_filename_column_values_name_path_relative(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    name = build_source(
        _state(monthly, output_filename_as_field=True, file_name_value="name")
    ).frame.collect()
    assert name["FileName"].to_list()[0] == "sales_2024-01.csv"

    absolute = build_source(
        _state(monthly, output_filename_as_field=True, file_name_value="path")
    ).frame.collect()
    assert absolute["FileName"].to_list()[0] == str(monthly / "sales_2024-01.csv")

    relative = build_source(
        _state(monthly, output_filename_as_field=True, file_name_value="relative")
    ).frame.collect()
    assert relative["FileName"].to_list()[0] == "sales_2024-01.csv"


def test_filename_column_custom_name_and_off(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    custom = build_source(
        _state(
            monthly,
            output_filename_as_field=True,
            file_name_column_name="Source",
        )
    ).frame.collect()
    assert "Source" in custom.columns
    assert "FileName" not in custom.columns

    off = build_source(_state(monthly)).frame.collect()
    assert "FileName" not in off.columns


def test_filename_column_conflict(tmp_path) -> None:
    directory = tmp_path / "conflict"
    source = write_text(directory / "a.csv", "id,FileName\n1,x\n")
    with pytest.raises(InputReadError) as error:
        build_source(_state(source, output_filename_as_field=True))
    assert error.value.kind == "column_conflict"
    assert error.value.column == "FileName"
    assert error.value.code == "TD-SCH-010"


def test_order_is_deterministic(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    first = build_source(_state(monthly)).frame.collect()
    os.utime(monthly / "sales_2024-01.csv", (9_000_000, 9_000_000))
    second = build_source(_state(monthly)).frame.collect()
    assert first.equals(second)


def test_report_marks_differing_files(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    result = build_source(_state(monthly))
    report = result.report
    assert report.file_count == 3
    assert "3 files" in report.summary()
    names = {item.relative_path for item in report.differing_files()}
    assert "sales_2024-03.csv" in names
    by_name = {item.relative_path: item for item in report.files}
    assert by_name["sales_2024-01.csv"].missing_columns == ["channel"]
    assert by_name["sales_2024-03.csv"].extra_columns == ["channel"]
    assert report.as_dict()["file_count"] == 3


def test_strict_schema_mismatch(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    with pytest.raises(InputReadError) as error:
        build_source(_state(monthly, schema_mismatch="error"))
    assert error.value.kind == "schema_mismatch"
    assert error.value.path.endswith("sales_2024-03.csv")
    assert error.value.column == "channel"
    assert error.value.code == "TD-SCH-011"


def test_skip_vs_stop_on_bad_file(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    write_text(monthly / "sales_2024-05.csv", "")
    with pytest.raises(InputReadError) as error:
        build_source(_state(monthly))
    assert error.value.kind == "empty_file"
    assert error.value.path.endswith("sales_2024-05.csv")

    result = build_source(_state(monthly, on_file_error="skip"))
    frame = result.frame.collect()
    assert frame.height == 5
    assert result.report.skipped_count == 1
    skipped = [item for item in result.report.files if item.status == "skipped"]
    assert skipped[0].error["kind"] == "empty_file"


def test_no_readable_files(tmp_path) -> None:
    directory = tmp_path / "bad"
    write_text(directory / "a.csv", "")
    with pytest.raises(InputReadError) as error:
        build_source(_state(directory, on_file_error="skip"))
    assert error.value.kind == "no_readable_files"


def test_numeric_supertype(tmp_path) -> None:
    directory = parquet_files(tmp_path)
    frame = build_source(_state(directory, "parquet")).frame.collect()
    assert frame.schema["amount"] == pl.Float64
    assert frame["amount"].to_list() == [10.0, 20.0, 30.5]


def test_dtype_conflict_to_string(tmp_path) -> None:
    directory = tmp_path / "mixed"
    directory.mkdir()
    pl.DataFrame({"id": [1], "amount": [10]}).write_parquet(directory / "a.parquet")
    pl.DataFrame({"id": [2], "amount": ["n/a"]}).write_parquet(directory / "b.parquet")
    result = build_source(_state(directory, "parquet"))
    frame = result.frame.collect()
    assert frame.schema["amount"] == pl.String
    assert frame["amount"].to_list() == ["10", "n/a"]
    conflicts = {
        item.relative_path: item.dtype_conflicts
        for item in result.report.files
        if item.dtype_conflicts
    }
    assert conflicts == {"a.parquet": ["amount"], "b.parquet": ["amount"]}


def test_parquet_folder_missing_column_null(tmp_path) -> None:
    directory = parquet_files(tmp_path)
    frame = build_source(_state(directory, "parquet")).frame.collect()
    assert frame["tag"].to_list() == [None, None, "x"]


def test_duplicate_column_names_renamed_and_noted(tmp_path) -> None:
    source = write_text(tmp_path / "dup.csv", "id,id\n1,2\n")
    result = build_source(_state(source))
    frame = result.frame.collect()
    assert frame.columns == ["id", "id_duplicated_0"]
    assert any("TD-SCH-002" in warning for warning in result.report.warnings)


def test_build_is_lazy(tmp_path, monkeypatch) -> None:
    monthly = monthly_csvs(tmp_path)
    directory = parquet_files(tmp_path)
    ndjson = write_text(tmp_path / "a.ndjson", '{"a":1}\n')

    def fail_collect(self, *args, **kwargs):
        raise AssertionError("build_source must not collect")

    monkeypatch.setattr(pl.LazyFrame, "collect", fail_collect)
    for path, file_type in (
        (monthly, "csv"),
        (directory, "parquet"),
        (ndjson, "ndjson"),
    ):
        result = build_source(_state(path, file_type))
        assert isinstance(result.frame, pl.LazyFrame)


def test_unicode_file_name_in_column(tmp_path) -> None:
    directory = tmp_path / "unicode"
    write_text(directory / "données_é.csv", "id\n1\n")
    frame = build_source(
        _state(directory, output_filename_as_field=True)
    ).frame.collect()
    assert frame["FileName"].to_list() == ["données_é.csv"]
