"""A Run leaves nothing behind in the working directory (BUG-013)."""

from __future__ import annotations

import pytest

from tests.support.workflows import WorkflowCase, materialize, run_workflow_and_wait
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e

#: Captured at import, before the ``no_modal_dialogs`` fixture stubs it.
REAL_GET_PY_FILE = TriggerSubWindow.__dict__["getPyFile"]

SELECT_CASE = WorkflowCase(
    name="in_select",
    source="savedfiles/1. in-select.tds",
    inputs={"check.csv": "data/check.csv"},
)


def test_run_does_not_write_into_cwd(
    qtbot, tmp_path, monkeypatch, no_modal_dialogs
) -> None:
    import os

    monkeypatch.setattr(TriggerSubWindow, "getPyFile", REAL_GET_PY_FILE)
    materialized = materialize(SELECT_CASE, tmp_path / "wf")
    cwd = tmp_path / "cwd"
    cwd.mkdir()

    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(materialized.path)) is True

    monkeypatch.chdir(cwd)
    run_workflow_and_wait(qtbot, window)

    assert list(cwd.iterdir()) == []
    script = os.path.join(
        os.environ["TRIGGER_DESIGNER_DATA_DIR"], "last_run", "check_output.py"
    )
    assert os.path.isfile(script)
