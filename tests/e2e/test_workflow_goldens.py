"""Checked-in workflows, loaded and run end to end against frozen goldens.

Every case materializes a workflow from ``savedfiles/`` into the test's tmp
directory: File Input nodes point at the checked-in sample data, File Output
nodes write into ``tmp_path/out``. The workflow is then loaded through a real
``TriggerSubWindow`` - which deserializes, validates and evaluates it - and
run through the same ``WorkflowWorker`` the Run button uses. That covers the
whole path: file parsing, node construction, graph evaluation, code
generation, execution and file writing.

What each case expects is frozen under ``tests/e2e/fixtures/expected`` and
regenerated only with ``TRIGGER_UPDATE_E2E_GOLDENS=1``; the module docstring
in ``tests/support/corpus.py`` says why the CSVs under ``savedfiles/`` are
not used as expectations.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest
from polars.testing import assert_series_equal

from tests.support.corpus import (
    ALL_NODES_CASE,
    FILE_OUTPUT_CASES,
)
from tests.support.frames import assert_frame_golden, read_frame
from tests.support.workflows import (
    REPO_ROOT,
    WorkflowCase,
    executed_frame,
    materialize,
    nodes_titled,
    run_workflow_and_wait,
)
from trigger_designer.core.shaping.common import LIVE_SAMPLE_ROWS

pytestmark = pytest.mark.e2e


def _open_case(qtbot, tmp_path, dialogs, case: WorkflowCase, input_paths=None):
    """Materialize, load and validate one workflow; return (window, files)."""
    from trigger_designer.qt.design_window import TriggerSubWindow

    materialized = materialize(case, tmp_path, input_paths)
    # No parent QMainWindow: qtbot only keeps a weakref, and a collected
    # parent would delete this widget with it mid-test.
    window = TriggerSubWindow()
    qtbot.addWidget(window)

    assert window.fileLoad(str(materialized.path)) is True
    messages = window.validateLoadedWorkflow()
    assert messages == [], f"workflow validation warnings: {messages}"
    assert window.getAllNodes(), "workflow loaded no nodes"
    assert dialogs["warnings"] == [], dialogs["warnings"]
    return window, materialized


def _assert_run_clean(window) -> None:
    total = len(window.getAllNodes())
    finished = len(window.execution_results)
    assert finished == total, (
        f"{total - finished} of {total} nodes did not finish successfully; "
        f"invalid: {[node.title for node in window.getAllNodes() if node.isInvalid()]}"
    )
    assert [node.title for node in window.getAllNodes() if node.isInvalid()] == []


@pytest.mark.parametrize("case", FILE_OUTPUT_CASES, ids=lambda case: case.name)
def test_file_outputs_match_golden(qtbot, tmp_path, no_modal_dialogs, case) -> None:
    window, materialized = _open_case(qtbot, tmp_path, no_modal_dialogs, case)
    run_workflow_and_wait(qtbot, window)
    _assert_run_clean(window)

    written = sorted(path.name for path in materialized.out_dir.iterdir())
    for basename, golden_name in case.goldens.items():
        assert basename in written, f"{basename!r} not written; wrote {written}"
        frame = read_frame(materialized.out_dir / basename)
        sort_by = frame.columns if golden_name in case.unordered_goldens else None
        assert_frame_golden(frame, golden_name, sort_by=sort_by)

    assert no_modal_dialogs["run_code"], "the run never reached its code export"


def test_running_total_frame_is_cumulative_per_keyword(
    qtbot, tmp_path, no_modal_dialogs
) -> None:
    """Property check on the frame the run computed.

    The golden pins the values; this pins the rule, so a careless golden
    regeneration cannot freeze a broken cumulative sum.
    """
    case = next(case for case in FILE_OUTPUT_CASES if case.name == "running_total")
    window, _ = _open_case(qtbot, tmp_path, no_modal_dialogs, case)
    run_workflow_and_wait(qtbot, window)
    _assert_run_clean(window)

    node = nodes_titled(window, "Running Total")[0]
    frame = executed_frame(window, node)
    assert "RunTot_RelevancyNum" in frame.columns
    expected = frame.select(
        pl.col("RelevancyNum").cum_sum().over("Difficulty").alias("RunTot_RelevancyNum")
    ).to_series()
    assert_series_equal(frame["RunTot_RelevancyNum"], expected)


@pytest.mark.slow
def test_all_node_workflow_runs_every_node(qtbot, tmp_path, no_modal_dialogs) -> None:
    """The 26-node sample: every node type runs and none is left invalid."""
    case = ALL_NODES_CASE
    window, _ = _open_case(qtbot, tmp_path, no_modal_dialogs, case)
    run_workflow_and_wait(qtbot, window, timeout_ms=180_000)
    _assert_run_clean(window)
    assert len(window.getAllNodes()) >= 20, "sample workflow shrank unexpectedly"

    # Names come from the node classes, not from the file. This sample was
    # saved before "Count Records" became "Count", so a load must not bring
    # the old name back.
    assert nodes_titled(window, "Count"), "the Count node lost its name"
    stale = [
        node.title
        for node in window.getAllNodes()
        if node.title != node.__class__.node_title
    ]
    assert stale == [], f"nodes kept a name their type no longer uses: {stale}"


def _large_check_csv(path: Path) -> int:
    """Write ``data/check.csv``'s rows repeated past 1,000; return the row count."""
    lines = (REPO_ROOT / "data" / "check.csv").read_text(encoding="utf-8").splitlines()
    header, rows = lines[0], [line for line in lines[1:] if line]
    body = rows * (1_000 // len(rows) + 1)
    path.write_text("\n".join([header, *body]) + "\n", encoding="utf-8")
    return len(body)


def _rows(frame) -> int:
    if isinstance(frame, pl.LazyFrame):
        return frame.select(pl.len()).collect().item()
    return frame.height


def test_load_samples_the_input_and_run_reads_every_row(
    qtbot, tmp_path, no_modal_dialogs
) -> None:
    """Loading evaluates only the live sample; Run still reads every row."""
    case = next(case for case in FILE_OUTPUT_CASES if case.name == "select")
    csv_path = tmp_path / "check.csv"
    total = _large_check_csv(csv_path)
    assert total > LIVE_SAMPLE_ROWS

    collected: list[int] = []
    collect = pl.LazyFrame.collect

    def counting_collect(self, *args, **kwargs):
        frame = collect(self, *args, **kwargs)
        collected.append(frame.height)
        return frame

    with patch.object(pl.LazyFrame, "collect", counting_collect):
        window, _ = _open_case(
            qtbot, tmp_path, no_modal_dialogs, case, input_paths={"check.csv": csv_path}
        )

    assert all(height <= LIVE_SAMPLE_ROWS for height in collected), collected
    for node in window.getAllNodes():
        outputs = node.value if isinstance(node.value, list) else [node.value]
        for entry in outputs:
            if isinstance(entry, dict) and entry.get("data") is not None:
                assert _rows(entry["data"]) <= LIVE_SAMPLE_ROWS, node.title

    run_workflow_and_wait(qtbot, window)
    _assert_run_clean(window)
    for title in ("File Input", "Select"):
        frame = executed_frame(window, nodes_titled(window, title)[0])
        assert frame.height == total, title
