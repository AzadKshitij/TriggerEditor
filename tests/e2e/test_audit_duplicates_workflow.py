"""Duplicates end to end: File Input (ledger CSV) -> Duplicates -> three File Outputs.

Expected numbers are the planted cases of ``tests/support/audit_ledger.py``
(docs/plan/04-audit-test-nodes.md section 7.5).
"""

from __future__ import annotations

from collections import Counter

import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.audit_ledger import make_ledger
from tests.support.frames import assert_frame_golden, read_frame
from tests.support.workflows import executed_frame, run_workflow_and_wait
from trigger_designer.core.node_configuration import (
    AuditNodes,
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e

EXACT = {"key_columns": ["vendor", "invoice_no", "amount"]}
NEAR = {
    "key_columns": ["vendor", "invoice_no"],
    "mode": "near",
    "amount_column": "amount",
    "tolerance": 0.5,
    "date_column": "posting_date",
    "window_days": 3,
}


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


@pytest.fixture(scope="module")
def ledger_csv(tmp_path_factory):
    path = tmp_path_factory.mktemp("ledger") / "ledger.csv"
    make_ledger().frame.write_csv(path)
    return path


def _build(root, source, settings: dict):
    out_dir = root / "out"
    out_dir.mkdir()
    paths = [out_dir / name for name in ("dups.csv", "unique.csv", "summary.csv")]

    window = TriggerSubWindow()
    scene = window.scene
    file_input = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    duplicates = get_class_from_opcode(AuditNodes.DUPLICATES, NodeTypes.AUDIT)(scene)
    outputs = [
        get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene) for _ in paths
    ]
    file_input.content.filePath = str(source)
    file_input.content.file_type = "csv"
    for name, value in settings.items():
        setattr(duplicates.content, name, value)
    Edge(scene, file_input.outputs[0], duplicates.inputs[0])
    for index, (output, path) in enumerate(zip(outputs, paths)):
        output.content.settings["filePath"] = str(path)
        output.content.settings["file_format"] = "csv"
        Edge(scene, duplicates.outputs[index], output.inputs[0])
    tds = root / "duplicates.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, paths


def _run(qtbot, root, source, settings):
    tds, paths = _build(root, source, settings)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    assert window.validateLoadedWorkflow() == []
    run_workflow_and_wait(qtbot, window)
    assert len(window.execution_results) == len(window.getAllNodes())
    assert not any(node.isInvalid() for node in window.getAllNodes())
    return window, paths


def _assert_group_sizes(dups: pl.DataFrame) -> None:
    sizes = Counter(dups["dup_group_id"].to_list())
    assert dups["dup_count"].to_list() == [
        sizes[g] for g in dups["dup_group_id"].to_list()
    ]


def test_exact_workflow(qtbot, tmp_path, ledger_csv, no_modal_dialogs) -> None:
    window, (dups_path, unique_path, summary_path) = _run(
        qtbot, tmp_path, ledger_csv, EXACT
    )
    dups = read_frame(dups_path)
    unique = read_frame(unique_path)
    summary = read_frame(summary_path)

    assert dups.height == 36 and unique.height == 2377
    assert dups["dup_group_id"].n_unique() == 17
    assert dups.columns[-2:] == ["dup_group_id", "dup_count"]
    assert unique.columns == make_ledger().frame.columns
    _assert_group_sizes(dups)
    assert set(dups["je_number"]).isdisjoint(unique["je_number"])
    assert dups.height + unique.height == 2413

    assert summary.height == 1
    assert_frame_golden(summary, "audit_dup_exact_summary")
    row = summary.row(0, named=True)
    assert row["test_name"] == "Duplicates" and row["status"] == "fail"
    assert (row["population_rows"], row["exception_rows"], row["groups"]) == (
        2413,
        36,
        17,
    )
    assert row["skipped_rows"] == 0 and row["unparseable_rows"] == 0
    assert row["message"] == "36 of 2413 rows are in 17 duplicate groups."
    assert row["criteria"].startswith("Rows with the same vendor, invoice_no and")
    assert no_modal_dialogs["warnings"] == []

    node = next(n for n in window.getAllNodes() if n.title == "Duplicates")
    assert executed_frame(window, node, 0).height == 36
    summary_frame = executed_frame(window, node, 2)
    assert summary_frame.row(0, named=True)["exception_rows"] == 36
    test_summary = node.content.test_summary  # filled by after_execution
    assert test_summary is not None and test_summary.exception_rows == 36
    assert test_summary.test_id == f"audit.duplicates#{node.id}"
    assert test_summary.exceptions_var == node.content.duplicates_var


def test_near_workflow(qtbot, tmp_path, ledger_csv) -> None:
    _window, (dups_path, unique_path, summary_path) = _run(
        qtbot, tmp_path, ledger_csv, NEAR
    )
    dups = read_frame(dups_path)
    unique = read_frame(unique_path)
    summary = read_frame(summary_path)
    assert_frame_golden(summary, "audit_dup_near_summary")
    row = summary.row(0, named=True)

    assert dups.height == 46 and unique.height == 2367
    assert dups["dup_group_id"].n_unique() == 22
    _assert_group_sizes(dups)
    assert row["status"] == "fail" and row["groups"] == 22
    assert row["exception_rows"] == 46 and row["unparseable_rows"] == 0
    assert "at most 0.50" in row["criteria"] and "at most 3 days" in row["criteria"]


def test_two_runs_give_the_same_outputs(qtbot, tmp_path, ledger_csv) -> None:
    window, paths = _run(qtbot, tmp_path, ledger_csv, EXACT)
    first = [path.read_bytes() for path in paths]
    for path in paths:
        path.unlink()
    run_workflow_and_wait(qtbot, window)
    assert [path.read_bytes() for path in paths] == first


def test_settings_survive_save_and_reload(qtbot, tmp_path, ledger_csv) -> None:
    window, _paths = _run(qtbot, tmp_path, ledger_csv, NEAR)
    node = next(n for n in window.getAllNodes() if n.title == "Duplicates")
    params = node.content.params()
    assert params.key_columns == NEAR["key_columns"]
    assert (params.mode, params.tolerance, params.window_days) == ("near", 0.5, 3)
    assert node.serialize()["op"] == "audit.duplicates"
