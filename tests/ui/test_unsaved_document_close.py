"""Closing an untitled document must prompt for and save that document.

Every untitled document has ``filename is None``. The close handler used to
activate ``findMdiChild(widget.filename)``, which returned the first untitled
window rather than the one being closed. ``maybeSave`` then read the active
window, so closing a modified tab could discard it silently when a different
untitled tab was unmodified, or prompt to save the wrong document.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from qtpy.QtWidgets import QApplication, QFileDialog, QMessageBox

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.main_window import TriggerWindow

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def window() -> Iterator[TriggerWindow]:
    win = TriggerWindow()
    win.resize(1200, 800)
    win.show()
    _APP.processEvents()
    yield win
    win.hide()
    win.deleteLater()
    _APP.processEvents()


@pytest.fixture
def prompts(monkeypatch):
    """Record the unsaved-changes prompts and choose the next answer."""
    calls: list[tuple[str, str]] = []
    answer = {"button": QMessageBox.StandardButton.Cancel}

    def warning(_parent, title, text, *_args, **_kwargs):
        calls.append((title, text))
        return answer["button"]

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(warning))
    return calls, answer


def _open_document(window: TriggerWindow):
    editor = TriggerSubWindow()
    sub = window.createMdiChild(editor)
    sub.show()
    _APP.processEvents()
    return sub, editor


def test_closing_a_modified_untitled_document_prompts_for_it(window, prompts):
    calls, answer = prompts
    first, _first_editor = _open_document(window)
    second, second_editor = _open_document(window)
    window.mdiArea.setActiveSubWindow(first)
    _APP.processEvents()

    second_editor.scene.has_been_modified = True
    answer["button"] = QMessageBox.StandardButton.Cancel

    assert second.close() is False

    assert calls, "closing the modified document must prompt"
    assert second in window.mdiArea.subWindowList()
    assert window.mdiArea.activeSubWindow() is first


def test_closing_an_unmodified_untitled_document_does_not_prompt(window, prompts):
    calls, _answer = prompts
    first, first_editor = _open_document(window)
    second, _second_editor = _open_document(window)
    first_editor.scene.has_been_modified = True
    window.mdiArea.setActiveSubWindow(second)
    _APP.processEvents()

    assert second.close() is True

    assert calls == []
    assert second not in window.mdiArea.subWindowList()
    assert first in window.mdiArea.subWindowList()


def test_save_from_the_close_prompt_saves_the_document_being_closed(
    window, prompts, tmp_path, monkeypatch
):
    calls, answer = prompts
    first, _first_editor = _open_document(window)
    second, second_editor = _open_document(window)
    window.mdiArea.setActiveSubWindow(first)
    _APP.processEvents()

    second_editor.scene.has_been_modified = True
    target = tmp_path / "untitled-second.tds"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    answer["button"] = QMessageBox.StandardButton.Save

    assert second.close() is True

    assert calls, "closing the modified document must prompt"
    assert target.is_file()
    assert second not in window.mdiArea.subWindowList()
