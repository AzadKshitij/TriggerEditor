"""Risk Filters end to end: File Input -> Risk Filters -> three File Outputs.

The CSV is the hand-computed fixture of docs/plan/04-audit-test-nodes.md section 4.5,
read from disk the way an analyst's export would be (amounts as accounting text), so
the expected scores below are answers, not a snapshot of what the code produced.
"""

from __future__ import annotations

import csv

import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.frames import assert_frame_golden, read_frame
from tests.support.workflows import run_workflow_and_wait
from trigger_designer.core.node_configuration import (
    AuditNodes,
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e

ROWS = [
    ("je", "date", "amount", "desc", "source"),
    ("J1", "2024-03-02", "5,000.00", "Reversal of accrual", "Manual"),
    ("J2", "2024-03-04", "4,900", "normal", "Auto"),
    ("J3", "2024-12-25", "1000", "Plug entry", "m"),
    ("J4", "2024-04-03", "9999.99", "x", "AUTO"),
    ("J5", "2024-03-09", "1,000.50", "MANUAL adj", "y"),
    ("J6", "2024-03-05", "123.45", "lunch", "Auto"),
]


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


def _build(root, **settings):
    source = root / "journal.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(ROWS)
    out_dir = root / "out"
    out_dir.mkdir()
    paths = {k: out_dir / f"{k}.csv" for k in ("flagged", "clean", "summary")}

    window = TriggerSubWindow()
    scene = window.scene
    file_input = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    risk = get_class_from_opcode(AuditNodes.RISK_FILTERS, NodeTypes.AUDIT)(scene)
    outputs = [
        get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene) for _ in paths
    ]
    file_input.content.filePath = str(source)
    file_input.content.file_type = "csv"
    for name, value in settings.items():
        setattr(risk.content, name, value)
    for output, path in zip(outputs, paths.values(), strict=True):
        output.content.settings["filePath"] = str(path)
        output.content.settings["file_format"] = "csv"
    Edge(scene, file_input.outputs[0], risk.inputs[0])
    for index, output in enumerate(outputs):
        Edge(scene, risk.outputs[index], output.inputs[0])
    tds = root / "risk.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, paths


SETTINGS = {
    "date_column": "date",
    "amount_column": "amount",
    "description_column": "desc",
    "manual_column": "source",
    "weekend": True,
    "holiday": True,
    "round_amount": True,
    "just_below_limit": True,
    "keyword": True,
    "after_period_end": True,
    "manual_journal": True,
    "holidays": ["2024-12-25"],
    "approval_limits": [5000.0, 10000.0],
    "keywords": ["reversal", "plug", "manual"],
    "period_end": "2024-03-31",
}


def test_all_seven_tests_flag_the_hand_computed_entries(qtbot, tmp_path) -> None:
    tds, paths = _build(tmp_path, **SETTINGS)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    assert len(window.execution_results) == len(window.getAllNodes())

    flagged = read_frame(paths["flagged"])
    assert flagged.columns == [
        "je",
        "date",
        "amount",
        "desc",
        "source",
        "risk_tests",
        "risk_score",
    ]
    assert flagged["je"].to_list() == ["J1", "J2", "J3", "J4", "J5"]
    assert flagged["risk_score"].to_list() == [4, 1, 5, 2, 3]
    assert flagged["risk_tests"].to_list() == [
        "Weekend posting; Round amount; Keyword in description; Manual journal",
        "Just below approval limit",
        (
            "Public-holiday posting; Round amount; Keyword in description; "
            "Posted after period end; Manual journal"
        ),
        "Just below approval limit; Posted after period end",
        "Weekend posting; Keyword in description; Manual journal",
    ]

    clean = read_frame(paths["clean"])
    assert clean.columns == ["je", "date", "amount", "desc", "source"]
    assert clean["je"].to_list() == ["J6"]

    assert_frame_golden(read_frame(paths["summary"]), "audit_risk_summary")
    summary = read_frame(paths["summary"]).row(0, named=True)
    assert summary["test_name"] == "Risk Filters"
    assert summary["status"] == "warn"
    assert summary["population_rows"] == 6 and summary["exception_rows"] == 5
    assert (
        summary["message"] == "5 of 6 entries were flagged by at least one risk test."
    )
    assert summary["flagged_two_or_more"] == 4 and summary["total_score"] == 15
    assert summary["n_weekend"] == 2 and summary["n_round_amount"] == 2
    assert summary["n_just_below_limit"] == 2 and summary["n_keyword"] == 3
    assert summary["n_after_period_end"] == 2 and summary["n_manual_journal"] == 3
    assert summary["n_holiday"] == 1


def test_a_single_test_and_a_weight_reach_the_files(qtbot, tmp_path) -> None:
    tds, paths = _build(
        tmp_path,
        date_column="date",
        weekend=True,
        weights={"weekend": 6},
    )
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    flagged = read_frame(paths["flagged"])
    assert flagged["je"].to_list() == ["J1", "J5"]
    assert flagged["risk_score"].to_list() == [6, 6]
    assert read_frame(paths["clean"]).height == 4
    summary = read_frame(paths["summary"]).row(0, named=True)
    assert summary["total_score"] == 12 and summary["n_holiday"] is None
    assert (
        pl.read_csv(paths["summary"])
        .get_column("criteria")[0]
        .endswith("posted on a Saturday or Sunday (date).")
    )
