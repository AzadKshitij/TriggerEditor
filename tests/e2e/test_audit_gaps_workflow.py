"""Gaps end to end: File Input (ledger CSV) -> Gaps -> two File Outputs (G and S).

The ledger is the deterministic synthetic one (``tests/support/audit_ledger``); the
expected rows are the anomalies it plants, so these are answers, not snapshots.
"""

from __future__ import annotations

import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.audit_ledger import make_ledger
from tests.support.frames import read_frame
from tests.support.workflows import run_workflow_and_wait
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


@pytest.fixture(scope="module")
def ledger_csv(tmp_path_factory) -> str:
    folder = tmp_path_factory.mktemp("gaps_ledger")
    return str(make_ledger().write_csv(folder)["all"])


def _build(root, ledger_csv: str, **settings):
    out_dir = root / "out"
    out_dir.mkdir()
    gaps_path, summary_path = out_dir / "gaps.csv", out_dir / "summary.csv"

    window = TriggerSubWindow()
    scene = window.scene
    file_input = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    gaps = get_class_from_opcode(AuditNodes.GAPS, NodeTypes.AUDIT)(scene)
    output_g = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)
    output_s = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)

    file_input.content.filePath = ledger_csv
    file_input.content.file_type = "csv"
    for output, path in ((output_g, gaps_path), (output_s, summary_path)):
        output.content.settings["filePath"] = str(path)
        output.content.settings["file_format"] = "csv"
    for name, value in settings.items():
        setattr(gaps.content, name, value)

    Edge(scene, file_input.outputs[0], gaps.inputs[0])
    Edge(scene, gaps.outputs[0], output_g.inputs[0])
    Edge(scene, gaps.outputs[1], output_s.inputs[0])
    tds = root / "gaps.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, gaps_path, summary_path


def _run(qtbot, tmp_path, ledger_csv, **settings):
    tds, gaps_path, summary_path = _build(tmp_path, ledger_csv, **settings)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    assert len(window.execution_results) == len(window.getAllNodes())
    assert not any(node.isInvalid() for node in window.getAllNodes())
    return window, read_frame(gaps_path), read_frame(summary_path)


def test_gaps_workflow_grouped_by_ledger(qtbot, tmp_path, ledger_csv, no_modal_dialogs):
    window, gaps, summary = _run(
        qtbot,
        tmp_path,
        ledger_csv,
        sequence_column="je_number",
        group_columns=["ledger"],
    )
    assert gaps.height == 13
    assert gaps.columns == [
        "ledger",
        "prefix",
        "finding",
        "from",
        "to",
        "count",
        "source_row",
    ]
    ranges = gaps.filter(pl.col("finding") == "gap")
    assert ranges.select("from", "to", "count").rows() == [
        ("GL-001000", "GL-001009", 10),
        ("GL-001500", "GL-001500", 1),
        ("GL-001800", "GL-001802", 3),
    ]
    dups = gaps.filter(pl.col("finding") == "duplicate")
    assert dups.select("from", "count", "source_row").rows() == [
        ("GL-000100", 2, 100),
        ("GL-000200", 2, 200),
        ("GL-000300", 2, 300),
    ]
    order = gaps.filter(pl.col("finding") == "out_of_order")
    assert sorted(order["source_row"].to_list()) == [
        1091,
        1191,
        1291,
        1391,
        2011,
        2012,
        2013,
    ]

    assert summary.height == 1
    row = summary.row(0, named=True)
    assert row["test_name"] == "Gaps" and row["status"] == "fail"
    assert (row["population_rows"], row["exception_rows"]) == (2413, 13)
    assert (row["series"], row["gap_ranges"], row["missing_items"]) == (2, 3, 14)
    assert (row["duplicate_values"], row["out_of_order_rows"]) == (3, 7)
    assert row["unparseable_rows"] == 0

    (node,) = [n for n in window.getAllNodes() if n.title == "Gaps"]
    assert node.content.test_summary.exception_rows == 13
    assert no_modal_dialogs["warnings"] == []


def test_gaps_date_workflow_calendar_and_business_days(qtbot, tmp_path, ledger_csv):
    (tmp_path / "calendar").mkdir()
    _window, gaps, summary = _run(
        qtbot,
        tmp_path / "calendar",
        ledger_csv,
        sequence_column="posting_date",
        mode="date",
    )
    assert gaps.select("from", "to", "count").rows() == [
        ("2024-03-24", "2024-03-24", 1),
        ("2024-03-30", "2024-04-01", 3),
    ]
    assert gaps["finding"].unique().to_list() == ["date_gap"]
    assert summary.row(0, named=True)["message"].startswith(
        "2 gap ranges covering 4 days."
    )

    (tmp_path / "business").mkdir()
    _window, business, _summary = _run(
        qtbot,
        tmp_path / "business",
        ledger_csv,
        sequence_column="posting_date",
        mode="date",
        business_days_only=True,
    )
    assert business.select("from", "to", "count").rows() == [
        ("2024-04-01", "2024-04-01", 1)
    ]


def test_second_run_gives_identical_frames(qtbot, tmp_path, ledger_csv) -> None:
    window, gaps, summary = _run(
        qtbot, tmp_path, ledger_csv, sequence_column="je_number"
    )
    first = (gaps, summary)
    run_workflow_and_wait(qtbot, window)
    again = (
        read_frame(tmp_path / "out" / "gaps.csv"),
        read_frame(tmp_path / "out" / "summary.csv"),
    )
    assert all(a.equals(b) for a, b in zip(first, again))
    # Reloading the saved file restores the node's settings.
    reloaded = TriggerSubWindow()
    qtbot.addWidget(reloaded)
    assert reloaded.fileLoad(str(tmp_path / "gaps.tds")) is True
    (node,) = [n for n in reloaded.getAllNodes() if n.title == "Gaps"]
    assert node.content.sequence_column == "je_number"
    assert node.content.mode == "prefixed"
