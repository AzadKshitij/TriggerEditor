"""Multi-sheet Excel reader tests."""

from __future__ import annotations

import shutil

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from tests.support.input_fixtures import multi_sheet_xlsx, write_text
from trigger_designer.core.input_source import build_source
from trigger_designer.core.inputs import InputReadError


def _state(path, **extra) -> dict:
    state = {"filePath": str(path), "file_type": "excel"}
    state.update(extra)
    return state


def test_one_sheet_legacy_equivalence(tmp_path) -> None:
    book = multi_sheet_xlsx(tmp_path)
    frame = build_source(_state(book, selected_sheet="Jan")).frame.collect()
    expected = pl.DataFrame({"id": [1.0], "amt": [2.5]})
    assert_frame_equal(frame, expected)


def test_all_sheets_union_with_sheet_column(tmp_path) -> None:
    book = multi_sheet_xlsx(tmp_path)
    result = build_source(_state(book, sheet_mode="all", add_sheet_name_column=True))
    frame = result.frame.collect()
    assert frame.columns == ["id", "amt", "note", "SheetName"]
    assert frame["amt"].to_list() == ["2.5", "n/a"]
    assert frame["SheetName"].to_list() == ["Jan", "Feb"]
    assert frame.height == 2
    assert len(result.report.files) == 2
    assert {item.sheet for item in result.report.files} == {"Jan", "Feb"}


def test_chosen_sheets(tmp_path) -> None:
    book = multi_sheet_xlsx(tmp_path)
    frame = build_source(
        _state(book, sheet_mode="chosen", selected_sheets=["Feb"])
    ).frame.collect()
    assert frame.columns == ["id", "amt", "note"]
    assert frame.rows() == [(2.0, "n/a", "x")]


def test_chosen_sheet_missing(tmp_path) -> None:
    book = multi_sheet_xlsx(tmp_path)
    with pytest.raises(InputReadError) as error:
        build_source(_state(book, sheet_mode="chosen", selected_sheets=["Jan", "Nope"]))
    assert error.value.kind == "sheet_missing"
    assert error.value.sheet == "Nope"
    assert error.value.path == str(book)

    result = build_source(
        _state(
            book,
            sheet_mode="chosen",
            selected_sheets=["Jan", "Nope"],
            on_file_error="skip",
        )
    )
    assert result.frame.collect().height == 1
    assert result.report.skipped_count == 1


def test_excel_lock_file_default_excluded_in_folder(tmp_path) -> None:
    book = multi_sheet_xlsx(tmp_path)
    shutil.copy(book, book.parent / "~$book.xlsx")
    frame = build_source(
        _state(book.parent, output_filename_as_field=True)
    ).frame.collect()
    assert set(frame["FileName"].to_list()) == {"book.xlsx"}


def test_not_a_workbook(tmp_path) -> None:
    broken = write_text(tmp_path / "broken.xlsx", "not an excel file")
    with pytest.raises(InputReadError) as error:
        build_source(_state(broken))
    assert error.value.kind == "parse"
    assert error.value.code == "TD-IN-006"
    assert "valid Excel workbook" in str(error.value)


def test_excel_folder_two_workbooks(tmp_path) -> None:
    first = multi_sheet_xlsx(tmp_path, name="a.xlsx")
    multi_sheet_xlsx(tmp_path, name="b.xlsx")
    frame = build_source(
        _state(first.parent, output_filename_as_field=True)
    ).frame.collect()
    assert frame.height == 2
    assert set(frame["FileName"].to_list()) == {"a.xlsx", "b.xlsx"}
    assert frame.filter(pl.col("FileName") == "a.xlsx").height == 1
