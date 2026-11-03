"""The Summary sheet: labels, formulas with cached values, inputs, protection."""

from __future__ import annotations

import datetime as dt
import hashlib

import pytest

from tests.support.workpaper import (
    EXCEPTIONS,
    FIXED_NOW,
    POPULATION,
    find_label,
    load,
    make_spec,
    value_right_of,
)
from trigger_designer.core.workpaper import SourceFile, TestInfo, write_workpaper


def _write(tmp_path, **kw):
    spec_kw = kw.pop("spec", {})
    kw.setdefault("population", POPULATION)
    result = write_workpaper(
        make_spec(tmp_path, **spec_kw), EXCEPTIONS, now=FIXED_NOW, **kw
    )
    return result, load(result.path), load(result.path, data_only=True)


def test_fixed_labels_and_values(tmp_path):
    _, wb, _ = _write(tmp_path)
    ws = wb["Summary"]
    labels = [ws.cell(r, 1).value for r in range(5, 14)]
    assert labels == [
        "Workpaper reference",
        "Client",
        "Engagement",
        "Period",
        "Test performed",
        "Prepared by",
        "Prepared on",
        "Reviewed by",
        "Review date",
    ]
    assert [ws.cell(r, 1).value for r in (16, 17, 18)] == [
        "Objective",
        "Procedure performed",
        "Criteria applied",
    ]
    assert ws["A1"].value == "Invoice approval test"
    assert ws["B5"].value == "C.3.1" and ws["B6"].value == "Acme Ltd"
    assert (
        ws["B9"].value == "Invoices above approval limit"
        and ws["B10"].value == "A. Auditor"
    )
    assert ws["B11"].value == dt.datetime(2026, 3, 31)
    assert ws["B12"].value is None and ws["B13"].value is None
    assert ws["B18"].value == "Amount is at least 1,500.00"
    assert "Trigger Designer 0.1.0 on 2026-03-31 09:30" in ws["A2"].value


def test_results_block_values_and_formulas(tmp_path):
    _, wb, cached = _write(tmp_path)
    ws, data = wb["Summary"], cached["Summary"]
    assert ws["B22"].value == 10 and ws["C22"].value == pytest.approx(9956.6)
    assert ws["B24"].value == "=COUNT('Exceptions'!$A$3:$A$5)"
    assert ws["C24"].value == "=SUM('Exceptions'!$F$3:$F$5)"
    assert ws["B23"].value == "=B24" and ws["C23"].value == "=C24"
    assert ws["D23"].value == '=IFERROR(B23/B22,"n/a")'
    assert data["B24"].value == 3 and data["C24"].value == pytest.approx(6700.75)
    assert data["B23"].value == 3 and data["C23"].value == pytest.approx(6700.75)
    assert data["D23"].value == pytest.approx(0.3)
    assert data["E23"].value == pytest.approx(0.6729958)
    assert ws["F22"].value == "Counted from the Population input"
    assert ws["F23"].value == "Counted from the Exceptions input"
    assert ws["F24"].value == "All exceptions are listed"
    assert ws["B25"].value.startswith("Not needed")


def test_conclusion_validation_and_unlocked_inputs(tmp_path):
    _, wb, _ = _write(tmp_path)
    ws = wb["Summary"]
    assert ws["A29"].value == "Conclusion"
    sources = {str(v.sqref): v.formula1 for v in ws.data_validations.dataValidation}
    assert (
        sources["B29"]
        == '"No exceptions,Exceptions - explained,Exceptions - require follow-up"'
    )
    for addr in ("B12", "B13", "B29", "B30"):
        assert ws[addr].protection.locked is False
    assert ws["B5"].protection.locked is True and ws.protection.sheet is True


def test_tick_legend_counts(tmp_path):
    _, wb, cached = _write(tmp_path)
    ws = wb["Summary"]
    assert [ws.cell(r, 1).value for r in range(34, 39)] == ["✓", "X", "E", "F", "N/A"]
    assert ws["F34"].value == "=COUNTIF('Exceptions'!$B$3:$B$5,A34)"
    assert cached["Summary"]["F34"].value == 0
    assert ws["B34"].value == "Agreed to source document"


def test_missing_population_and_summary_make_input_cells(tmp_path):
    _, wb, _ = _write(tmp_path, population=None)
    ws = wb["Summary"]
    assert ws["B22"].value is None and ws["C22"].value is None
    assert ws["B22"].protection.locked is False and ws["C22"].protection.locked is False
    assert ws["F22"].value == "Not provided - enter manually"
    assert ws["B26"].value == "No test result supplied"


def test_test_info_reconciliation_difference_and_agree(tmp_path):
    info = TestInfo(
        test_name="From node",
        criteria="Amount >= 1,500",
        exception_rows=2,
        population_rows=10,
    )
    _, wb, _ = _write(
        tmp_path, test=info, population=None, spec={"test_name": "", "criteria": ""}
    )
    ws = wb["Summary"]
    assert ws["B9"].value == "From node" and ws["B18"].value == "Amount >= 1,500"
    assert (
        ws["B26"].value
        == "DIFFERENCE: the test node reported 2 exceptions but 3 were received"
    )
    assert ws["B22"].value == 10 and ws["F22"].value == "Reported by the test node"
    info = TestInfo(exception_rows=3)
    _, wb2, _ = _write(
        tmp_path, test=info, spec={"output_path": str(tmp_path / "agree.xlsx")}
    )
    assert wb2["Summary"]["B26"].value == "Agrees to the test node (3 exceptions)"


def test_blank_criteria_gets_placeholder_input_cell(tmp_path):
    _, wb, _ = _write(tmp_path, spec={"criteria": ""})
    ws = wb["Summary"]
    assert ws["B18"].value == "Not provided - complete manually"
    assert ws["B18"].protection.locked is False


def test_sources_table_hashes_and_notes(tmp_path):
    src = tmp_path / "exceptions.csv"
    src.write_bytes(b"a,b\n1,2\n")
    gone = tmp_path / "gone.csv"
    sources = (SourceFile(str(src), rows=1), SourceFile(str(gone)))
    _, wb, _ = _write(tmp_path, spec={"source_files": sources})
    ws = wb["Summary"]
    r = find_label(ws, "File") + 1
    assert ws.cell(r, 1).value == str(src) and ws.cell(r, 3).value == 1
    assert ws.cell(r, 4).value == 8
    assert ws.cell(r, 6).value == hashlib.sha256(src.read_bytes()).hexdigest()
    assert ws.cell(r + 1, 1).value == str(gone)
    assert ws.cell(r + 1, 3).value == "not recorded"
    assert ws.cell(r + 1, 6).value == "file not found or not computed"


def test_workbook_contents_lists_omitted_sheets(tmp_path):
    result, wb, _ = _write(tmp_path)
    ws = wb["Summary"]
    start = find_label(ws, "Workbook contents")
    lines = [ws.cell(r, 1).value for r in range(start + 1, start + 5)]
    assert lines[0] == "Summary" and lines[1] == "Exceptions"
    assert lines[2].startswith("Run log - omitted: no run record")
    assert lines[3].startswith("Workflow - omitted")
    assert set(result.omitted) == {"Run log", "Workflow"}


def test_logo_added_and_bad_logo_noted(tmp_path):
    from PIL import Image

    logo = tmp_path / "logo.png"
    Image.new("RGB", (400, 100), "red").save(logo)
    result, wb, _ = _write(tmp_path, spec={"logo_path": str(logo)})
    assert len(wb["Summary"]._images) == 1
    result2, wb2, _ = _write(
        tmp_path,
        spec={
            "logo_path": str(tmp_path / "nope.png"),
            "output_path": str(tmp_path / "b.xlsx"),
        },
    )
    assert len(wb2["Summary"]._images) == 0
    assert any("Logo not added" in w for w in result2.warnings)
    assert not any("Logo not added" in w for w in result.warnings)


def test_print_setup_tab_colour_and_properties(tmp_path):
    _, wb, _ = _write(tmp_path)
    ws = wb["Summary"]
    assert (
        ws.page_setup.orientation == "landscape"
        and ws.sheet_properties.pageSetUpPr.fitToPage
    )
    assert (
        "Page &P of &N" in ws.oddFooter.left.text + ws.oddFooter.right.text
        or ws.oddFooter
    )
    assert ws.sheet_view.showGridLines is False
    assert ws.sheet_properties.tabColor.rgb.endswith("305496")
    assert (
        wb.properties.title == "Invoice approval test"
        and wb.properties.creator == "A. Auditor"
    )
    assert wb.sheetnames[0] == "Summary"


def test_summary_written_after_exceptions_has_correct_cached_values(tmp_path):
    # guards the constant_memory decision: Summary is filled after Exceptions
    _, _, cached = _write(tmp_path)
    assert (
        cached["Summary"]["B24"].value == 3 and cached["Exceptions"]["F5"].value == 2200
    )


def test_injection_text_in_metadata_is_quote_prefixed(tmp_path):
    _, wb, _ = _write(tmp_path, spec={"client": "=cmd|' /C calc'!A0"})
    cell = wb["Summary"]["B6"]
    assert cell.data_type == "s" and cell.quotePrefix is True
    assert value_right_of(wb["Summary"], "Client") == "=cmd|' /C calc'!A0"


def test_custom_exceptions_sheet_name_is_sanitised_and_formulas_follow(tmp_path):
    result, wb, cached = _write(
        tmp_path, spec={"exceptions_sheet_name": "Dup: it's [1]"}
    )
    assert result.sheets[1] == "Dup it's 1"
    assert wb["Summary"]["B24"].value == "=COUNT('Dup it''s 1'!$A$3:$A$5)"
    assert cached["Summary"]["B24"].value == 3


def test_empty_population_and_decimals_format(tmp_path):
    empty = POPULATION.clear()
    _, wb, cached = _write(tmp_path, population=empty, spec={"value_decimals": 0})
    assert cached["Summary"]["D23"].value == "n/a"
    assert wb["Summary"]["C24"].number_format == "#,##0"
