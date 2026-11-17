"""Idle means silent: with a workflow open and nothing pressed, nothing connects.

Phase 5 of the AI plan allows exactly one network use, a download the user starts
from the optional modules dialog. The main window is shown offscreen with every
connection function replaced by a recorder that refuses, the same functions the
unit layer checks (``tests/unit/test_network_isolation.py``). A workflow is opened
the way a user opens one, the window settles for a second, and no recorder may
have been called.
"""

from __future__ import annotations

import socket

import pytest

from tests.unit.test_network_isolation import CONNECTION_FUNCTIONS
from trigger_designer.core.authoring import Editor, apply_patch, new_workflow
from trigger_designer.core.headless.params import dump_workflow
from trigger_designer.qt.main_window import TriggerWindow

pytestmark = pytest.mark.ui


@pytest.fixture()
def network_calls(monkeypatch) -> list[str]:
    """Every connection function raises, and each call is recorded before it does.

    A caller that catches the exception still leaves its name in the list, so the
    test checks the list at the end and not only for a raised error.
    """
    calls: list[str] = []

    def refusing(name: str):
        def _refuse(*_args, **_kwargs):
            calls.append(name)
            raise AssertionError("network used")

        return _refuse

    for owner, attr, name in CONNECTION_FUNCTIONS:
        monkeypatch.setattr(owner, attr, refusing(name))
    return calls


def test_an_open_workflow_opens_no_connection_while_idle(
    qtbot, tmp_path, network_calls, no_modal_dialogs
):
    source = tmp_path / "in.csv"
    source.write_text("acct,amount\nA,10\nB,25\n", encoding="utf-8")
    editor = Editor(new_workflow(), base_dir=str(tmp_path))
    apply_patch(
        editor,
        [
            {
                "op": "add_node",
                "type": "input.file_input",
                "ref": "src",
                "settings": {"filePath": str(source), "file_type": "csv"},
            },
            {"op": "add_node", "type": "preparation.sort", "ref": "s", "after": "src"},
            {
                "op": "add_node",
                "type": "input.file_output",
                "ref": "out",
                "after": "s",
                "settings": {
                    "filePath": str(tmp_path / "out.csv"),
                    "file_format": "csv",
                },
            },
            {"op": "connect", "from": "src", "to": "s"},
            {"op": "connect", "from": "s", "to": "out"},
        ],
    )
    workflow = tmp_path / "idle.tds"
    workflow.write_bytes(dump_workflow(editor.data))

    # Not qtbot.addWidget: closing a TriggerWindow saves the session and quits the
    # shared application (see tests/conftest.py), so the window is hidden and
    # deleted here instead, as tests/ui/test_dock_chrome.py does.
    window = TriggerWindow()
    window.show()
    try:
        window.openFile(str(workflow))
        subwindows = window.mdiArea.subWindowList()
        assert len(subwindows) == 1, "the workflow did not open"
        assert len(subwindows[0].widget().scene.nodes) == 3
        qtbot.wait(1000)
        assert network_calls == [], f"network used while idle: {network_calls}"
    finally:
        window.hide()
        window.deleteLater()


def test_the_recorder_replaces_the_connection_functions():
    """An empty list would let the idle test pass without replacing anything."""
    replaced = {(owner, attr) for owner, attr, _name in CONNECTION_FUNCTIONS}
    assert (socket, "getaddrinfo") in replaced
    assert (socket.socket, "connect") in replaced
