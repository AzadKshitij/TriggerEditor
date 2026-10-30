"""Data Profile end to end: File Input -> Data Profile -> two File Outputs.

The input is a small CSV every value of which was classified by hand (see
``tests/support/profile_fixtures.MESSY_CSV``), so the checks below are the
expected answers, not a snapshot of whatever the code produced.
"""

from __future__ import annotations

import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.frames import assert_frame_golden, read_frame
from tests.support.profile_fixtures import MESSY_CSV
from tests.support.workflows import run_workflow_and_wait
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    ReportNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


def _build(root, csv_text: str = MESSY_CSV):
    source = root / "messy.csv"
    source.write_text(csv_text, encoding="utf-8", newline="")
    out_dir = root / "out"
    out_dir.mkdir()
    passthrough, profile = out_dir / "passthrough.csv", out_dir / "profile.csv"

    window = TriggerSubWindow()
    scene = window.scene
    file_input = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    data_profile = get_class_from_opcode(ReportNodes.DATA_PROFILE, NodeTypes.REPORT)(
        scene
    )
    output_a = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)
    output_b = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)

    file_input.content.filePath = str(source)
    file_input.content.file_type = "csv"
    for output, path in ((output_a, passthrough), (output_b, profile)):
        output.content.settings["filePath"] = str(path)
        output.content.settings["file_format"] = "csv"

    Edge(scene, file_input.outputs[0], data_profile.inputs[0])
    Edge(scene, data_profile.outputs[0], output_a.inputs[0])
    Edge(scene, data_profile.outputs[1], output_b.inputs[0])
    tds = root / "profile.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, passthrough, profile


def test_messy_csv_profile_matches_golden(qtbot, tmp_path) -> None:
    tds, passthrough, profile_path = _build(tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)

    assert len(window.execution_results) == len(window.getAllNodes())

    # Socket D is the input, untouched.
    expected = pl.read_csv(tmp_path / "messy.csv", infer_schema=False)
    actual = pl.read_csv(passthrough, infer_schema=False)
    assert actual.equals(expected)

    profile = read_frame(profile_path)
    assert_frame_golden(profile, "data_profile_messy")

    def row(column: str) -> dict:
        return profile.filter(pl.col("column") == column).row(0, named=True)

    assert profile.get_column("row_count").to_list() == [6] * 6
    assert profile.get_column("sampled").to_list() == [False] * 6

    ident = row("id")
    assert ident["flags"] == "leading_zeros"
    assert ident["suggested_type"] == "String"

    amount = row("amount")
    assert amount["null_count"] == 1
    assert amount["whitespace_count"] == 1
    assert amount["numeric_like_count"] == 2
    assert amount["integer_like_count"] == 1
    assert amount["trailing_minus_count"] == 1
    assert amount["distinct_count"] == 5
    assert amount["flags"] == (
        "mixed_numeric_text,trailing_minus,leading_trailing_whitespace"
    )

    qty = row("qty")
    assert qty["null_count"] == 1
    assert qty["suggested_type"] == "Int64"
    assert qty["flags"] == "numeric_as_text"

    posted = row("posted")
    assert posted["date_like_count"] == 5
    assert posted["suggested_type"] == "String"
    assert posted["flags"] == "mixed_date_text"

    flag = row("flag")
    assert flag["suggested_type"] == "Boolean"
    assert flag["top_value"] == "Y"
    assert flag["top_count"] == 4

    note = row("note")
    assert note["empty_count"] == 1
    assert note["blank_count"] == 1
    assert note["whitespace_count"] == 1
    assert note["distinct_count"] == 3
    assert note["flags"] == "leading_trailing_whitespace"


def test_two_runs_give_the_same_profile(qtbot, tmp_path) -> None:
    tds, _passthrough, profile_path = _build(tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    first = profile_path.read_bytes()
    profile_path.unlink()
    run_workflow_and_wait(qtbot, window)
    assert profile_path.read_bytes() == first


def _profile_node(window):
    return next(n for n in window.getAllNodes() if n.title == "Data Profile")


def test_run_gives_the_node_the_whole_input(qtbot, tmp_path) -> None:
    """The canvas holds 100 rows; the Run profiles all 500 and the node gets them."""
    rows = 500
    text = "n,t\n" + "".join(f"{i},{i % 7}\n" for i in range(rows))
    tds, _passthrough, _profile = _build(tmp_path, text)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    content = _profile_node(window).content

    assert content.run_profile() is None  # nothing has run yet
    live = content.get_or_compute(
        content.key(), content.source_frame(), content.profile_settings()
    )
    assert live.row_count == 100  # the preview the canvas holds

    run_workflow_and_wait(qtbot, window)
    qtbot.waitUntil(lambda: content.run_profile() is not None, timeout=5000)
    qtbot.wait(300)  # nothing after the run may wipe it again
    run = content.run_profile()
    assert run is not None
    assert run.row_count == rows
    assert [c.name for c in run.columns] == ["n", "t"]
    assert run.columns[0].distinct_count == rows
    assert run.columns[0].histogram  # the chart data came back too


def test_open_dock_switches_to_the_run_result(qtbot, tmp_path) -> None:
    from trigger_designer.qt.docks.node_config import ConfigDock

    rows = 500
    text = "n,t\n" + "".join(f"{i},{i % 7}\n" for i in range(rows))
    tds, _passthrough, _profile = _build(tmp_path, text)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    node = _profile_node(window)
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    view = node.content._view
    qtbot.waitUntil(lambda: view.state == "ready", timeout=15000)
    assert view.source == "live"
    assert view.notice.text() == "Data: 100 rows"

    run_workflow_and_wait(qtbot, window)
    qtbot.waitUntil(lambda: view.source == "run", timeout=5000)
    assert view.notice.text() == "Data: 500 rows"
    assert "workflow run" in view.notice.toolTip()
    html = view._report_html()
    assert "Data: 500 rows" in html
    assert html.count('class="card"') == 2


def test_run_profile_in_the_dock_matches_the_exported_table(qtbot, tmp_path) -> None:
    tds, _passthrough, profile_path = _build(tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    content = _profile_node(window).content
    qtbot.waitUntil(lambda: content.run_profile() is not None, timeout=5000)
    exported = read_frame(profile_path)
    shown = content.run_profile().to_frame()
    assert (
        shown.get_column("column").to_list() == exported.get_column("column").to_list()
    )
    assert shown.get_column("flags").to_list() == [
        f or "" for f in exported.get_column("flags").to_list()
    ]
