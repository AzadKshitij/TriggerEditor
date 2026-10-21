#!/usr/bin/env python3
"""The Graph node, end to end through a real workflow run.

``savedfiles/8. In-Graph.tds`` predates the redesign: a line chart of
``Difficulty`` against ``Relevancy Score``, titled "Lol". The saved settings
used to be clobbered the moment the node was selected, and the run executed
``plt.show()`` on the workflow worker thread - popping a window and blocking
headless runs. This case pins the new contract: a clean run, the saved
settings intact, and an output socket that carries the frame the node charted.
"""

from __future__ import annotations

from tests.support.workflows import (
    WorkflowCase,
    executed_frame,
    materialize,
    nodes_titled,
    run_workflow_and_wait,
)

GRAPH_CASE = WorkflowCase(name="graph_sink", source="savedfiles/8. In-Graph.tds")


def _assert_run_clean(window) -> None:
    total = len(window.getAllNodes())
    finished = len(window.execution_results)
    assert finished == total, (
        f"{total - finished} of {total} nodes did not finish successfully; "
        f"invalid: {[node.title for node in window.getAllNodes() if node.isInvalid()]}"
    )


def test_graph_node_runs_clean_and_forwards_its_frame(
    qtbot, tmp_path, no_modal_dialogs
) -> None:
    from trigger_designer.qt.design_window import TriggerSubWindow

    materialized = materialize(GRAPH_CASE, tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(materialized.path)) is True
    assert no_modal_dialogs["warnings"] == [], no_modal_dialogs["warnings"]

    graph = nodes_titled(window, "Graph")[0]
    content = graph.content
    # The saved configuration survived the load untouched.
    assert content.graph_type == "line"
    assert content.x_column == "Difficulty"
    assert content.y_column == "Relevancy Score"
    assert content.title == "Lol"

    run_workflow_and_wait(qtbot, window)
    _assert_run_clean(window)

    forwarded = executed_frame(window, graph)
    assert "Difficulty" in forwarded.columns
    assert "Relevancy Score" in forwarded.columns
    source = nodes_titled(window, "File Input")[0]
    assert forwarded.equals(executed_frame(window, source))

    # The queued run-data signal reached the GUI-thread slot: the frame the
    # run computed is in, and Show graph is unlocked.
    qtbot.waitUntil(lambda: content.incom_data is not None, timeout=5000)
    assert content.workflow_ran_successfully is True

    # Data-only code generation: no matplotlib, no window from a run.
    code = graph.get_code()
    assert "plt" not in code
    assert "matplotlib" not in code
