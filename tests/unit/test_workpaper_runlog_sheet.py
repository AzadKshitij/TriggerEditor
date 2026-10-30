"""Run log + Workflow sheets, and the whole-run workpaper (Qt-free)."""

from __future__ import annotations

import pytest

from tests.support.workpaper import EXCEPTIONS, FIXED_NOW, find_label, load, make_spec
from trigger_designer.core.workpaper import write_run_workpaper, write_workpaper

RECORD = {
    "run_id": "abc123",
    "status": "ok",
    "started_at": "2026-03-31T09:00:00.000000Z",
    "finished_at": "2026-03-31T09:00:02.000000Z",
    "user": "auditor",
    "machine": "LAPTOP",
    "app_version": "0.1.0",
    "python_version": "3.14.0",
    "polars_version": "2.0.0",
    "workflow_path": "C:/w/wf.tds",
    "workflow_sha256": "f" * 64,
    "inputs": [
        {
            "role": "input",
            "path": "C:/data/in.csv",
            "size_bytes": 1000,
            "modified_time": "2026-03-30T10:00:00Z",
            "sha256": "a" * 64,
            "row_count": 10,
            "sheet": None,
        }
    ],
    "outputs": [
        {
            "role": "output",
            "path": "C:/data/out.csv",
            "sha256": "b" * 64,
            "size_bytes": 5,
        }
    ],
    "nodes": [
        {
            "node_id": 1,
            "op": "input.file_input",
            "title": "File Input",
            "status": "ok",
            "started_at": "2026-03-31T09:00:00Z",
            "duration_s": 0.1234,
            "rows_out": {"var_a": 10},
        },
        {
            "node_id": 2,
            "op": "audit.duplicates",
            "title": "Duplicates",
            "label": "invoices",
            "status": "ok",
            "duration_s": 0.5,
            "rows_out": {"var_d": 3, "var_u": 7},
            "warnings": ["w1", "w2"],
            "test_summary": {
                "test_name": "Duplicates",
                "criteria": "Same vendor and invoice",
                "status": "fail",
                "population_rows": 10,
                "exception_rows": 3,
                "exception_rate": 0.3,
                "message": "3 rows repeat",
            },
        },
        {
            "node_id": 3,
            "op": "preparation.select_records",
            "title": "Select Records",
            "status": "failed",
            "rows_out": {},
            "error": {"title": "Column not found", "hint": "Check the column name"},
        },
    ],
}
WORKFLOW = [
    {
        "step": 1,
        "node_id": 1,
        "title": "File Input",
        "op": "input.file_input",
        "settings": [["File", "in.csv"], ["Format", "csv"]],
        "inputs": [],
    },
    {
        "step": 2,
        "node_id": 2,
        "title": "Duplicates",
        "op": "audit.duplicates",
        "settings": [["Match on", "vendor, invoice"]],
        "inputs": ["File Input"],
    },
    {
        "kind": "comment",
        "comment": "Checked with the client on 2026-03-30.\nSecond line.",
    },
]


def _write(tmp_path, record=RECORD, workflow=WORKFLOW, **kw):
    spec = make_spec(tmp_path, **kw)
    result = write_workpaper(
        spec, EXCEPTIONS, run_record=record, workflow=workflow, now=FIXED_NOW
    )
    return result, load(result.path)


def test_run_log_header_pairs(tmp_path):
    result, wb = _write(tmp_path)
    assert result.sheets == ["Summary", "Exceptions", "Run log", "Workflow"]
    ws = wb["Run log"]
    pairs = {ws.cell(r, 1).value: ws.cell(r, 2).value for r in range(4, 14)}
    assert pairs["Run ID"] == "abc123" and pairs["Run by"] == "auditor@LAPTOP"
    assert pairs["Workflow SHA-256"] == "f" * 64 and pairs["Polars"] == "2.0.0"
    assert ws["A2"].value == "Completed run." and ws.protection.sheet is True


def test_run_log_files_and_steps_table(tmp_path):
    _, wb = _write(tmp_path)
    ws = wb["Run log"]
    head = find_label(ws, "Role")
    assert (
        ws.cell(head + 1, 2).value == "C:/data/in.csv"
        and ws.cell(head + 1, 4).value == 1000
    )
    assert ws.cell(head + 1, 6).value == "a" * 64
    first = find_label(ws, "Step") + 1
    assert [ws.cell(first + i, 1).value for i in range(3)] == [1, 2, 3]
    assert (
        ws.cell(first, 2).value == "File Input"
        and ws.cell(first, 3).value == "File Input"
    )
    assert (
        ws.cell(first, 6).value == pytest.approx(0.1234)
        and ws.cell(first, 7).value == 10
    )
    assert ws.cell(first + 1, 2).value == "Duplicates (invoices)"
    assert (
        ws.cell(first + 1, 3).value == "Duplicates"
        and ws.cell(first + 1, 7).value == 10
    )
    assert ws.cell(first + 1, 8).value == "w1; w2"
    assert ws.cell(first + 2, 8).value == "Column not found - Check the column name"
    assert ws.cell(first + 2, 7).value == "not counted"
    assert ws.cell(first + 2, 1).fill.fgColor.rgb.endswith("F8CBAD")
    assert ws.cell(first, 1).fill.fgColor.rgb != ws.cell(first + 2, 1).fill.fgColor.rgb


def test_in_progress_banner_when_status_running(tmp_path):
    record = {**RECORD, "status": "running", "nodes": RECORD["nodes"][:2]}
    _, wb = _write(tmp_path, record=record)
    banner = wb["Run log"]["A2"].value
    assert banner.startswith("Snapshot taken while the workflow was running")
    assert "Duplicates" in banner


def test_missing_keys_render_not_recorded(tmp_path):
    _, wb = _write(tmp_path, record={"run_id": "x", "nodes": [{"op": "a.b_c"}]})
    ws = wb["Run log"]
    assert ws.cell(find_label(ws, "Started (UTC)"), 2).value == "not recorded"
    first = find_label(ws, "Step") + 1
    assert (
        ws.cell(first, 2).value == "B C" and ws.cell(first, 6).value == "not recorded"
    )


def test_none_record_omits_sheet_with_reason(tmp_path):
    result, wb = _write(tmp_path, record=None)
    assert "Run log" not in wb.sheetnames
    assert "no run record" in result.omitted["Run log"]


def test_include_run_record_off(tmp_path):
    result, wb = _write(tmp_path, include_run_record=False)
    assert (
        "Run log" not in wb.sheetnames
        and result.omitted["Run log"] == "turned off in the node settings"
    )


def test_workflow_sheet_lists_nodes_settings_and_comments(tmp_path):
    _, wb = _write(tmp_path)
    ws = wb["Workflow"]
    assert ws["A4"].value == "Step" and ws["B5"].value == "File Input"
    assert ws["D5"].value == "File: in.csv\nFormat: csv"
    assert ws["E6"].value == "File Input" and ws["C6"].value == "Duplicates"
    note = find_label(ws, "Note")
    assert ws.cell(note, 2).value.startswith("Checked with the client")
    assert ws.protection.sheet is True


def test_long_setting_values_are_shortened(tmp_path):
    wf = [{"step": 1, "title": "T", "op": "a.b", "settings": [["Code", "x" * 500]]}]
    _, wb = _write(tmp_path, workflow=wf)
    assert (
        wb["Workflow"]["D5"].value.endswith("...")
        and len(wb["Workflow"]["D5"].value) < 320
    )


def test_injection_in_workflow_text(tmp_path):
    wf = [{"step": 1, "title": "=evil()", "op": "a.b", "settings": []}]
    _, wb = _write(tmp_path, workflow=wf)
    cell = wb["Workflow"]["B5"]
    assert cell.data_type == "s" and cell.quotePrefix is True


# ---------------------------------------------------------------- run workpaper
def test_run_workpaper_has_one_row_per_test(tmp_path):
    spec = make_spec(tmp_path, output_path=str(tmp_path / "run.xlsx"))
    result = write_run_workpaper(
        spec, run_record=RECORD, workflow=WORKFLOW, now=FIXED_NOW
    )
    assert (
        result.sheets == ["Summary", "Run log", "Workflow"]
        and result.exceptions_total == 3
    )
    ws = load(result.path)["Summary"]
    head = find_label(ws, "Test")
    assert [ws.cell(head, c).value for c in range(1, 7)][:3] == [
        "Test",
        "Status",
        "Population rows",
    ]
    row = head + 1
    assert ws.cell(row, 1).value == "Duplicates" and ws.cell(row, 2).value == "fail"
    assert ws.cell(row, 3).value == 10 and ws.cell(row, 4).value == 3
    assert ws.cell(row, 5).value == pytest.approx(0.3)
    assert "Same vendor and invoice" in ws.cell(row, 6).value
    assert find_label(ws, "Conclusion") and find_label(ws, "Source files")
    assert ws.protection.sheet is True


def test_run_workpaper_without_tests_says_so(tmp_path):
    spec = make_spec(tmp_path)
    record = {**RECORD, "nodes": RECORD["nodes"][:1]}
    result = write_run_workpaper(spec, run_record=record, now=FIXED_NOW)
    ws = load(result.path)["Summary"]
    assert ws["A22"].value == "No audit tests were recorded in this run."
