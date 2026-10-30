"""Pins the xlsxwriter behaviour the writers rely on (a library upgrade that changes
one of these must fail here, not in an auditor's workbook)."""

from __future__ import annotations

import openpyxl
import pytest

from trigger_designer.core.excel import engine


@pytest.fixture
def make(tmp_path):
    def build(fn, name="w.xlsx"):
        path = tmp_path / name
        wb = engine.new_workbook(str(path), str(tmp_path))
        fn(wb)
        wb.close()
        return path

    return build


def test_formula_cached_value_is_readable_without_recalc(make):
    def fn(wb):
        ws = wb.add_worksheet("S")
        for r in range(3):
            ws.write_number(r, 0, r)
        ws.write_formula(3, 0, "=COUNT(A1:A3)", None, 5)

    path = make(fn)
    assert openpyxl.load_workbook(path)["S"]["A4"].value == "=COUNT(A1:A3)"
    assert openpyxl.load_workbook(path, data_only=True)["S"]["A4"].value == 5


def test_data_validation_list_present(make):
    def fn(wb):
        ws = wb.add_worksheet("S")
        ws.data_validation(0, 0, 0, 0, {"validate": "list", "source": ["a", "b"]})
        ws.data_validation(1, 1, 5, 1, {"validate": "list", "source": ["x", "y"]})

    ws = openpyxl.load_workbook(make(fn))["S"]
    got = {str(v.sqref): v.formula1 for v in ws.data_validations.dataValidation}
    assert got == {"A1": '"a,b"', "B2:B6": '"x,y"'}


def test_freeze_panes_and_autofilter(make):
    def fn(wb):
        ws = wb.add_worksheet("S")
        ws.write_string(0, 0, "h")
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, 3, 2)

    ws = openpyxl.load_workbook(make(fn))["S"]
    assert ws.freeze_panes == "A2" and ws.auto_filter.ref == "A1:C4"


def test_sheet_protection_with_unlocked_cell(make):
    def fn(wb):
        ws = wb.add_worksheet("S")
        free = wb.add_format({"locked": False})
        ws.write_string(0, 0, "free", free)
        ws.write_string(1, 0, "locked")
        ws.protect("", {"autofilter": True})

    ws = openpyxl.load_workbook(make(fn))["S"]
    assert ws.protection.sheet is True
    assert ws["A1"].protection.locked is False and ws["A2"].protection.locked is True


def test_quote_prefix_and_string_formula_stay_text(make):
    def fn(wb):
        ws = wb.add_worksheet("S")
        ws.write_string(
            0, 0, "=cmd|' /C calc'!A0", wb.add_format({"quote_prefix": True})
        )

    cell = openpyxl.load_workbook(make(fn))["S"]["A1"]
    assert cell.data_type == "s" and cell.quotePrefix is True


def test_long_string_returns_minus_two(make):
    rcs = []

    def fn(wb):
        rcs.append(wb.add_worksheet("S").write_string(0, 0, "x" * 40_000))

    path = make(fn)
    assert rcs == [-2]
    assert len(openpyxl.load_workbook(path)["S"]["A1"].value) == 32_767


def test_control_char_is_escaped_by_library(make):
    def fn(wb):
        wb.add_worksheet("S").write_string(0, 0, "a\x01b")

    assert openpyxl.load_workbook(make(fn))["S"]["A1"].value != "a\x01b"


def test_constant_memory_rejects_earlier_row_write(make):
    rcs = []

    def fn(wb):
        ws = wb.add_worksheet("S")
        ws.write_number(5, 0, 1)
        rcs.append(ws.write_number(1, 0, 2))

    make(fn)
    assert rcs == [-1]


def test_constant_memory_allows_any_sheet_order(make):
    def fn(wb):
        summary = wb.add_worksheet("Summary")
        exc = wb.add_worksheet("Exceptions")
        for r in range(2, 5):
            exc.write_number(r, 0, r)
        summary.write_formula(0, 0, "=COUNT('Exceptions'!$A$3:$A$5)", None, 3)

    path = make(fn)
    wb = openpyxl.load_workbook(path, data_only=True)
    assert wb.sheetnames == ["Summary", "Exceptions"] and wb["Summary"]["A1"].value == 3


def test_set_column_after_rows_in_constant_memory(make):
    def fn(wb):
        ws = wb.add_worksheet("S")
        ws.write_string(0, 0, "x")
        ws.set_column(0, 0, 44.7)

    assert openpyxl.load_workbook(make(fn))["S"].column_dimensions["A"].width > 44


def test_last_excel_row_is_writable_and_next_is_not(make):
    rcs = []

    def fn(wb):
        ws = wb.add_worksheet("S")
        rcs.append(ws.write_number(1_048_575, 0, 1))
        rcs.append(ws.write_number(1_048_576, 0, 1))

    make(fn)
    assert rcs == [0, -1]


def test_nan_requires_option(make):
    def fn(wb):
        wb.add_worksheet("S").write_number(0, 0, float("nan"))

    with pytest.raises(TypeError):
        make(fn)


def test_invalid_sheet_name_raises(tmp_path):
    wb = engine.new_workbook(str(tmp_path / "w.xlsx"), str(tmp_path))
    with pytest.raises(engine.library_errors()):
        wb.add_worksheet("a" * 32)
    with pytest.raises(engine.library_errors()):
        wb.add_worksheet("bad:name")
    wb.close()


def test_print_setup_tab_colour_and_properties(make):
    def fn(wb):
        ws = wb.add_worksheet("S")
        ws.write_string(0, 0, "x")
        ws.set_tab_color("#C00000")
        ws.hide_gridlines(2)
        ws.set_landscape()
        ws.fit_to_pages(1, 0)
        ws.repeat_rows(0)
        ws.set_footer("&L&F")
        ws.merge_range(0, 0, 0, 4, "m")
        wb.set_properties({"title": "T"})

    wb = openpyxl.load_workbook(make(fn))
    ws = wb["S"]
    assert ws.sheet_properties.tabColor.rgb.endswith("C00000")
    assert ws.sheet_view.showGridLines is False
    assert ws.page_setup.orientation == "landscape"
    assert str(ws.merged_cells) == "A1:E1" and wb.properties.title == "T"
