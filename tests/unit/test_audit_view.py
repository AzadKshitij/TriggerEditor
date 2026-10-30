"""Dock display helpers (plan 02 3.15)."""

from __future__ import annotations

import pytest

from tests.support.audit_helpers import make_node, make_record_dict
from trigger_designer.core.audit.view import (
    format_duration,
    format_local_time,
    node_table_rows,
    run_rows_out,
    run_summary_rows,
)


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (0, "0 ms"),
        (0.012, "12 ms"),
        (0.9, "900 ms"),
        (0.95, "950 ms"),
        (1.0, "1.0 s"),
        (59.94, "59.9 s"),
        (60, "1 min 00 s"),
        (125, "2 min 05 s"),
        (3720, "1 h 02 min"),
        (None, "-"),
    ],
)
def test_format_duration(seconds, text):
    assert format_duration(seconds) == text


def test_format_local_time_shape_and_fallback():
    shown = format_local_time("2026-10-21T09:14:03.120456Z")
    assert len(shown) == 19 and shown[4] == "-" and shown[10] == " "
    assert format_local_time("garbage") == "garbage"
    assert format_local_time(None) == ""


def _rows(rec):
    return dict(run_summary_rows(rec))


def test_summary_rows_basic_fields():
    rec = make_record_dict(
        workflow_path="C:/Work/Q3/orders.tds", workflow_sha256="9d" * 32, seq=3
    )
    rows = _rows(rec)
    assert rows["Run id"] == "a" * 32 and rows["Sequence"] == "3"
    assert rows["Status"] == "ok"
    assert rows["Workflow"] == "orders.tds (sha 9d9d9d9d)"
    assert rows["Inputs"] == "1 (all hashed)" and rows["Outputs"] == "1 (all hashed)"
    assert rows["Nodes"] == "2"
    assert "Note" not in rows
    assert rows["Run by"] == "tester @ box"


def test_summary_shows_unsaved_changes_row():
    rec = make_record_dict(workflow_modified_since_save=True)
    assert _rows(rec)["Note"] == "Workflow had unsaved changes"
    assert _rows(rec)["Workflow"].startswith("unsaved (graph ")


def test_summary_flags_unhashed_inputs_failures_and_baseline():
    rec = make_record_dict(
        baseline={
            "run_id": "x",
            "input_changes": [{"path": "p", "change": "modified"}],
        },
        warnings=["w"],
    )
    rec["inputs"][0]["sha256_status"] = "skipped_size_limit"
    rec["nodes"][1]["status"] = "failed"
    rec["nodes"].append(make_node(3, status="skipped"))
    rows = _rows(rec)
    assert "not all hashed (skipped_size_limit)" in rows["Inputs"]
    assert rows["Nodes"] == "3 (1 failed, 1 skipped)"
    assert rows["Inputs changed"] == "1 since the previous run"
    assert rows["Warnings"] == "1"


def test_node_rows_ok_failed_skipped():
    rec = make_record_dict()
    rec["nodes"] = [
        make_node(1, title="File Input", rows_out={"v": 3}, duration_s=0.012),
        make_node(
            2,
            title="Join",
            rows_in=[
                {"socket": 0, "rows": 3},
                {"socket": 1, "rows": None},
                {"socket": 2, "rows": 5},
            ],
            rows_out={"a": 2, "b": 1},
            status="failed",
            error={"code": "TD-X", "title": "It broke"},
            columns_out={"a": ["x", "y", "z"]},
        ),
        make_node(3, title="Out", status="skipped", rows_out={}, columns_out={}),
        make_node(4, title="Labelled", label="My label", rows_out={"v": None}),
    ]
    one, two, three, four = node_table_rows(rec)
    assert (one["node"], one["rows_in"], one["rows_out"], one["duration"]) == (
        "File Input",
        "-",
        "3",
        "12 ms",
    )
    assert (two["rows_in"], two["rows_out"], two["columns"], two["error"]) == (
        "3 + - + 5",
        "3",
        "3",
        "It broke",
    )
    assert (three["status"], three["duration"], three["rows_out"]) == (
        "skipped",
        "-",
        "-",
    )
    assert four["node"] == "My label" and four["rows_out"] == "-"


def test_run_rows_out():
    rec = make_record_dict()
    assert run_rows_out(rec) == 3
    rec["outputs"][0]["row_count"] = None
    assert run_rows_out(rec) is None


def test_test_result_text_and_rows():
    from trigger_designer.core.audit.view import format_test_result, test_table_rows

    assert format_test_result(None) == ""
    assert format_test_result({"status": "pass"}) == "pass"
    summary = {
        "status": "warn",
        "test_name": "Gaps",
        "population_rows": 2000,
        "exception_rows": 5,
        "exception_rate": 0.0025,
    }
    assert format_test_result(summary) == "warn: 5 of 2,000 (0.2%)"
    rec = make_record_dict()
    rec["nodes"] = [make_node(1), make_node(2, title="Gaps", test_summary=summary)]
    rows = test_table_rows(rec)
    assert len(rows) == 1
    assert (rows[0]["test"], rows[0]["status"], rows[0]["exceptions"]) == (
        "Gaps",
        "warn",
        "5",
    )
    assert node_table_rows(rec)[1]["test"] == "warn: 5 of 2,000 (0.2%)"
    assert node_table_rows(rec)[0]["test"] == ""
