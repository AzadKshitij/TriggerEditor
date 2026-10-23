"""Reader tests for single-file CSV/TXT/Parquet/JSON/NDJSON sources."""

from __future__ import annotations

import polars as pl
import pytest

from tests.support.input_fixtures import (
    json_files,
    monthly_csvs,
    parquet_files,
    write_text,
)
from trigger_designer.core.input_source import (
    FileReport,
    SourceReport,
    build_source,
    diagnose_collect_error,
)
from trigger_designer.core.inputs import InputReadError


def _state(path, file_type: str = "csv", **extra) -> dict:
    state = {"filePath": str(path), "file_type": file_type}
    state.update(extra)
    return state


def test_csv_single_all_strings(tmp_path) -> None:
    source = monthly_csvs(tmp_path) / "sales_2024-01.csv"
    frame = build_source(_state(source)).frame.collect()
    assert frame.columns == ["id", "region", "amount"]
    assert all(dtype == pl.String for dtype in frame.schema.values())
    assert frame.rows() == [("1", "N", "10.50"), ("2", "S", "20.00")]


def test_csv_delimiter_and_no_header(tmp_path) -> None:
    source = write_text(tmp_path / "in.csv", "1;Ann\n2;Bob\n")
    frame = build_source(
        _state(source, delimiter=";", first_row_contains_field_names=False)
    ).frame.collect()
    assert frame.rows() == [("1", "Ann"), ("2", "Bob")]


def test_csv_encoding_default_strict_vs_lossy(tmp_path) -> None:
    source = tmp_path / "latin.csv"
    source.write_bytes(b"id,name\n1,caf\xe9\n")
    result = build_source(_state(source))
    with pytest.raises(Exception) as raised:
        result.frame.collect()
    error = diagnose_collect_error(raised.value, result.report)
    assert error.kind == "encoding"
    assert error.path == str(source)
    assert error.code == "TD-IN-004"

    lossy = build_source(_state(source, encoding="utf8-lossy")).frame.collect()
    assert "caf\ufffd" in lossy["name"].to_list()


def test_bom_stripped(tmp_path) -> None:
    source = tmp_path / "bom.csv"
    source.write_bytes(b"\xef\xbb\xbfid,name\n1,Ann\n")
    frame = build_source(_state(source)).frame.collect()
    assert frame.columns == ["id", "name"]
    assert frame.rows() == [("1", "Ann")]


def test_zero_byte_and_header_only(tmp_path) -> None:
    empty = write_text(tmp_path / "empty.csv", "")
    with pytest.raises(InputReadError) as error:
        build_source(_state(empty))
    assert error.value.kind == "empty_file"
    assert error.value.code == "TD-IN-005"

    header_only = write_text(tmp_path / "header.csv", "id,name\n")
    frame = build_source(_state(header_only)).frame.collect()
    assert frame.columns == ["id", "name"]
    assert frame.height == 0


def test_parquet_single_typed_and_lazy(tmp_path) -> None:
    directory = parquet_files(tmp_path)
    source = directory / "p1.parquet"
    result = build_source(_state(source, "parquet"))
    assert isinstance(result.frame, pl.LazyFrame)
    frame = result.frame.collect()
    assert frame.schema["id"] == pl.Int64
    assert frame.schema["amount"] == pl.Int64
    assert frame.rows() == [(1, 10), (2, 20)]


def test_ndjson_lazy(tmp_path) -> None:
    _array, source = json_files(tmp_path)
    result = build_source(_state(source, "ndjson"))
    assert isinstance(result.frame, pl.LazyFrame)
    frame = result.frame.collect()
    assert frame.columns == ["a", "s", "extra"]
    assert frame["extra"].to_list() == [None, True]


def test_json_array_records(tmp_path) -> None:
    source, _ndjson = json_files(tmp_path)
    frame = build_source(_state(source, "json", json_nested="text")).frame.collect()
    assert frame.columns == ["a", "b", "t"]
    assert frame["a"].to_list() == [1, 3]


def test_json_nested_text_vs_keep(tmp_path) -> None:
    source, _ndjson = json_files(tmp_path)
    text = build_source(_state(source, "json", json_nested="text")).frame.collect()
    assert text["b"].to_list() == ['{"c":2}', None]
    assert text["t"].to_list() == ["[1,2]", None]

    keep = build_source(_state(source, "json", json_nested="keep")).frame.collect()
    assert isinstance(keep.schema["b"], pl.Struct)
    assert isinstance(keep.schema["t"], pl.List)


def test_read_as_text_casts_all(tmp_path) -> None:
    directory = parquet_files(tmp_path)
    frame = build_source(
        _state(directory / "p1.parquet", "parquet", read_as_text=True)
    ).frame.collect()
    assert all(dtype == pl.String for dtype in frame.schema.values())


def test_record_limit_applies_after_union(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    frame = build_source(_state(monthly, record_limit=4)).frame.collect()
    assert frame.height == 4
    assert frame["id"].to_list() == ["1", "2", "3", "4"]


def test_diagnose_collect_error_names_column() -> None:
    report = SourceReport(
        mode="single",
        root="",
        file_count=1,
        ok_count=1,
        skipped_count=0,
        excluded_count=0,
        union_columns=[],
        reference_columns=[],
        files=[
            FileReport(
                path="C:\\data\\in.csv",
                relative_path="in.csv",
                sheet=None,
                status="ok",
            )
        ],
    )
    error = diagnose_collect_error(
        pl.exceptions.ComputeError('could not parse "x" in column "amount"'),
        report,
    )
    assert error.column == "amount"
    assert error.path == "C:\\data\\in.csv"
    assert error.kind == "parse"
