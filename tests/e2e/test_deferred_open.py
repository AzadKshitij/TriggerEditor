"""An interactive open returns before evaluating, then lands in the same state.

``defer_load_evaluation`` is what Open, recent files, drag and drop and launch
turn on. The nodes are evaluated right afterwards in slices, so the window is
usable at once; scripts and tests keep the synchronous load.
"""

from __future__ import annotations

from tests.support.corpus import FILE_OUTPUT_CASES
from tests.support.workflows import (
    materialize,
    run_workflow_and_wait,
)
from trigger_designer.core.frames import frame_schema
from trigger_designer.qt.design_window import TriggerSubWindow

#: The Formula case: it goes through DuckDB, the slow part of a real load.
CASE = next(case for case in FILE_OUTPUT_CASES if case.name == "formula")


def _state(window) -> list[tuple]:
    """Per node: title, validity and the column names of every output."""
    rows = []
    for node in window.getAllNodes():
        entries = node.value if isinstance(node.value, list) else [node.value]
        columns = [
            list(frame_schema(entry["data"]))
            for entry in entries
            if isinstance(entry, dict) and entry.get("data") is not None
        ]
        rows.append((node.title, node.isInvalid(), columns))
    return rows


def _window(qtbot, *, deferred: bool) -> TriggerSubWindow:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.defer_load_evaluation = deferred
    return window


def test_the_default_load_is_still_synchronous(qtbot, tmp_path, no_modal_dialogs):
    window = _window(qtbot, deferred=False)
    assert window.fileLoad(str(materialize(CASE, tmp_path).path)) is True
    assert window.evaluation_settled is True
    assert not any(node.isDirty() for node in window.getAllNodes()), "not evaluated"


def test_a_deferred_open_returns_first_and_matches_the_synchronous_load(
    qtbot, tmp_path, no_modal_dialogs
):
    path = str(materialize(CASE, tmp_path).path)
    synchronous = _window(qtbot, deferred=False)
    assert synchronous.fileLoad(path) is True

    deferred = _window(qtbot, deferred=True)
    assert deferred.fileLoad(path) is True
    # fileLoad returned without evaluating: the pass is still to come.
    assert deferred.evaluation_settled is False
    assert any(node.isDirty() for node in deferred.getAllNodes())

    qtbot.waitUntil(lambda: deferred.evaluation_settled, timeout=60_000)
    assert _state(deferred) == _state(synchronous)


def test_a_run_supersedes_an_unfinished_deferred_open(
    qtbot, tmp_path, no_modal_dialogs
):
    window = _window(qtbot, deferred=True)
    assert window.fileLoad(str(materialize(CASE, tmp_path).path)) is True
    assert window.evaluation_settled is False

    run_workflow_and_wait(qtbot, window)  # Run does its own full evaluation

    assert window.evaluation_settled is True
    assert len(window.execution_results) == len(window.getAllNodes())
