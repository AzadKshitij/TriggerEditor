"""Benford end to end: File Input (CSV) -> Benford -> three File Outputs.

The input is the deterministic synthetic ledger (2,413 rows, ``AP`` rows plant a
first-digit violation), so the checks are the plan's verified reference numbers,
not a snapshot of whatever the code produced.
"""

from __future__ import annotations

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


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


def _build(root, **settings):
    csv_path = make_ledger().write_csv(root / "in")["all"]
    out_dir = root / "out"
    out_dir.mkdir()
    paths = {k: out_dir / f"{k}.csv" for k in ("table", "summary", "drill")}

    window = TriggerSubWindow()
    scene = window.scene
    file_input = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    benford = get_class_from_opcode(AuditNodes.BENFORD, NodeTypes.AUDIT)(scene)
    file_input.content.filePath = str(csv_path)
    file_input.content.file_type = "csv"
    benford.content.amount_column = "amount"
    for name, value in settings.items():
        setattr(benford.content, name, value)
    Edge(scene, file_input.outputs[0], benford.inputs[0])
    for index, key in enumerate(("table", "summary", "drill")):
        sink = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)
        sink.content.settings["filePath"] = str(paths[key])
        sink.content.settings["file_format"] = "csv"
        Edge(scene, benford.outputs[index], sink.inputs[0])
    tds = root / "benford.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, paths


def _benford(window):
    return next(n for n in window.getAllNodes() if n.title == "Benford")


def test_first_digit_run_writes_table_summary_and_drill_down(qtbot, tmp_path) -> None:
    tds, paths = _build(tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    assert len(window.execution_results) == len(window.getAllNodes())

    table = read_frame(paths["table"])
    assert_frame_golden(table, "audit_benford_gl_table")
    assert table.height == 9
    assert table["digit"].to_list() == list(range(1, 10))
    ledger = make_ledger().frame
    expected = (
        ledger.with_columns(pl.col("amount").str.slice(0, 1).cast(pl.Int64).alias("d"))
        .group_by("d")
        .len()
        .sort("d")
    )
    assert table["count"].to_list() == expected["len"].to_list()
    assert table["count"].sum() == 2413

    summary = read_frame(paths["summary"])
    assert summary.height == 1
    row = summary.row(0, named=True)
    assert row["test_name"] == "Benford first digit"
    assert row["status"] == "fail" and row["conformity"] == "nonconforming"
    assert row["population_rows"] == 2413 and row["tested_rows"] == 2413
    assert row["mad"] == pytest.approx(0.028145, abs=1e-6)
    assert row["chi_square"] == pytest.approx(189.2603, abs=1e-4)
    assert row["flagged_digits"] == "5, 6, 7, 8, 9"
    assert row["exception_rows"] == 1032

    drill = read_frame(paths["drill"])
    assert drill.height == 1032
    assert drill.columns == [*ledger.columns, "benford_digits"]
    assert set(drill["benford_digits"]) == {5, 6, 7, 8, 9}

    # The Run's own frames are what was written, and the node got its summary.
    assert executed_frame(window, _benford(window), 1).height == 1
    summary_state = _benford(window).content.test_summary
    assert summary_state is not None
    assert summary_state.population_rows == 2413  # the whole file, not the live preview
    assert summary_state.exception_rows == 1032
    assert summary_state.status == "fail"
    assert summary_state.exceptions_var == _benford(window).content.drill_var


def test_two_runs_give_identical_files(qtbot, tmp_path) -> None:
    tds, paths = _build(tmp_path, digits=2)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    first = {k: p.read_bytes() for k, p in paths.items()}
    assert read_frame(paths["table"]).height == 90
    for path in paths.values():
        path.unlink()
    run_workflow_and_wait(qtbot, window)
    assert {k: p.read_bytes() for k, p in paths.items()} == first


def test_a_column_the_file_lacks_is_reported_on_the_node(qtbot, tmp_path) -> None:
    tds, _paths = _build(tmp_path, amount_column="no_such_column")
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    node = _benford(window)
    assert node.isInvalid() and node.current_error.code == "TD-AUDIT-002"
