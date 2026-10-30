"""`errors/continue_past_failure`: a failed node does not stop independent branches.

Real window, real worker thread, real files. Branch A reads a file that does
not exist (fails), its Normalize and File Output are dependents (skipped).
Branch B is independent and must still write its output.
"""

from __future__ import annotations

import pytest
from nodeeditor.node_edge import Edge

from tests.support.audit_helpers import newest_record, store_dir_of, write_orders
from tests.support.workflows import run_workflow_and_wait
from trigger_designer.core.audit.store import verify_store
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.preferences import get_preferences

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


def _two_branch_workflow(tmp_path):
    window = TriggerSubWindow()
    scene = window.scene
    bad_in = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    bad_norm = get_class_from_opcode(
        PreparationNodes.NORMALIZE_COLUMNS, NodeTypes.PREPARATION
    )(scene)
    bad_out = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)
    good_in = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    good_out = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)
    (tmp_path / "out").mkdir(exist_ok=True)
    bad_in.content.filePath = str(tmp_path / "missing.csv")
    bad_in.content.file_type = "csv"
    bad_out.content.settings["filePath"] = str(tmp_path / "out" / "bad.csv")
    bad_out.content.settings["file_format"] = "csv"
    good_csv = write_orders(tmp_path / "orders.csv", 3)
    good_in.content.filePath = str(good_csv)
    good_in.content.file_type = "csv"
    good_out.content.settings["filePath"] = str(tmp_path / "out" / "good.csv")
    good_out.content.settings["file_format"] = "csv"
    Edge(scene, bad_in.outputs[0], bad_norm.inputs[0])
    Edge(scene, bad_norm.outputs[0], bad_out.inputs[0])
    Edge(scene, good_in.outputs[0], good_out.inputs[0])
    tds = tmp_path / "wf.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, bad_in, good_in


def _sealed_record(qtbot, tds):
    """The record is sealed once error enrichment has settled (a moment later)."""
    index = store_dir_of(tds) / "index.jsonl"
    qtbot.waitUntil(lambda: index.exists() and index.stat().st_size > 0, timeout=15_000)
    return newest_record(store_dir_of(tds))


def test_independent_branch_runs_and_dependents_are_skipped(
    qtbot, tmp_path, clean_preferences
):
    assert get_preferences().get("errors/continue_past_failure", True) is True
    tds, _bad, _good = _two_branch_workflow(tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)

    assert (tmp_path / "out" / "good.csv").exists()  # the independent branch ran
    assert not (tmp_path / "out" / "bad.csv").exists()
    rec = _sealed_record(qtbot, tds)
    assert rec["status"] == "failed"
    by_op = [(n["op"], n["status"]) for n in rec["nodes"]]
    assert by_op.count(("input.file_input", "failed")) == 1
    assert by_op.count(("input.file_input", "ok")) == 1
    assert ("preparation.normalize_columns", "skipped") in by_op
    assert by_op.count(("input.file_output", "skipped")) == 1
    assert by_op.count(("input.file_output", "ok")) == 1
    assert verify_store(store_dir_of(tds)).ok

    problems = window.problems
    codes = {error.code for _source, error in problems.entries()}
    assert "TD-RUN-008" in codes
    skipped_nodes = [
        n for n in window.getAllNodes() if n.node_title in ("Normalize", "File Output")
    ]
    knock_on = [
        n.current_error
        for n in skipped_nodes
        if n.current_error is not None and n.current_error.code == "TD-RUN-008"
    ]
    assert len(knock_on) == 2
    # a knock-on warning is not a root problem
    assert problems.count("error", roots_only=True) == 1


def test_preference_off_stops_at_the_first_failure(qtbot, tmp_path, clean_preferences):
    get_preferences().set("errors/continue_past_failure", False)
    tds, _bad, _good = _two_branch_workflow(tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    rec = _sealed_record(qtbot, tds)
    assert rec["status"] == "failed"
    statuses = [n["status"] for n in rec["nodes"]]
    assert statuses.count("failed") == 1
    assert "TD-RUN-008" not in {e.code for _s, e in window.problems.entries()}
    # the loop stopped at the failure: nothing after it ran
    first_failed = statuses.index("failed")
    assert all(s == "skipped" for s in statuses[first_failed + 1 :])
