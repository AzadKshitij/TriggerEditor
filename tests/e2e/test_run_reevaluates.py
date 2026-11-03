"""Run recomputes every node's live state first (BUG-005)."""

from __future__ import annotations

import pytest

from tests.support.workflows import (
    WorkflowCase,
    executed_frame,
    materialize,
    nodes_titled,
    run_workflow_and_wait,
)

pytestmark = pytest.mark.e2e

SELECT_CASE = WorkflowCase(
    name="in_select",
    source="savedfiles/1. in-select.tds",
    inputs={"check.csv": "data/check.csv"},
)


def test_run_after_unevaluated_load_uses_real_data(
    qtbot, tmp_path, no_modal_dialogs
) -> None:
    from trigger_designer.qt.design_window import TriggerSubWindow

    materialized = materialize(SELECT_CASE, tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(materialized.path)) is True

    select = nodes_titled(window, "Select")[0]
    # The state a never-evaluated node has: it does not know its input, so
    # the generated code falls back to an empty frame unless Run recomputes it.
    select.content.input_vars = [""]
    assert "pl.DataFrame()" in select.get_code()

    run_workflow_and_wait(qtbot, window)

    frame = executed_frame(window, select)
    assert frame.height > 0
    assert frame.columns == ["Keyword", "Seed"]
