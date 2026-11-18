"""The launch path: show the window first, open the file or the last session after.

``TriggerWindow(defer_startup_open=True)`` is what ``main()`` uses. Opening a
workflow blocks for as long as it takes to load, and nothing can paint until it
returns, so the launcher shows the window and then calls ``open_startup_work``.
"""

from __future__ import annotations

import pytest
from qtpy.QtWidgets import QApplication

from trigger_designer.core.authoring import Editor, new_workflow
from trigger_designer.core.headless.params import dump_workflow
from trigger_designer.qt.main_window import TriggerWindow

pytestmark = pytest.mark.ui


def _workflow(folder, name: str = "flow.tds"):
    editor = Editor(new_workflow(), base_dir=str(folder))
    editor.add_node("preparation.sort")
    path = folder / name
    path.write_bytes(dump_workflow(editor.data))
    return path


def _discard(window) -> None:
    # Closing a TriggerWindow quits the shared application (tests/conftest.py).
    window.hide()
    window.deleteLater()
    QApplication.processEvents()


def _open_count(window) -> int:
    return len(window.mdiArea.subWindowList())


def test_a_deferred_launch_opens_the_file_only_when_asked(tmp_path):
    flow = _workflow(tmp_path)
    window = TriggerWindow(file_path=str(flow), defer_startup_open=True)
    try:
        assert _open_count(window) == 0  # constructed and shown first

        window.open_startup_work()
        assert _open_count(window) == 1
        assert window.mdiArea.subWindowList()[0].widget().defer_load_evaluation is True

        window.open_startup_work()  # once only
        assert _open_count(window) == 1
    finally:
        _discard(window)


def test_the_default_launch_still_opens_the_file_in_the_constructor(tmp_path):
    flow = _workflow(tmp_path)
    window = TriggerWindow(file_path=str(flow))
    try:
        assert _open_count(window) == 1
    finally:
        _discard(window)


def test_a_deferred_launch_without_a_file_restores_the_session_later(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(
        TriggerWindow, "_restore_last_session", lambda self: calls.append(1)
    )

    window = TriggerWindow(defer_startup_open=True)
    try:
        assert calls == []  # not during construction

        window.open_startup_work()
        window.open_startup_work()
        assert calls == [1]
    finally:
        _discard(window)
