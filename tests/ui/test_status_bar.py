#!/usr/bin/env python3
"""The status bar reports the cursor position of the canvas.

``MainWindowDockMixin.createStatusBar`` overrode the base implementation
without calling it, so the permanent label was never created and the status
bar only ever said "Ready". The base cannot simply be called: it wires
``self.nodeeditor.view``, and this app makes the MDI area the central
widget, so that attribute does not exist.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest
from qtpy.QtWidgets import QApplication, QLabel, QWidget

from trigger_designer.qt.main_window import TriggerWindow

_APP = QApplication.instance() or QApplication([])


@pytest.fixture()
def window():
    win = TriggerWindow()
    win.show()
    _APP.processEvents()
    try:
        yield win
    finally:
        win.hide()
        win.deleteLater()
        _APP.processEvents()


def test_the_status_bar_has_the_scene_position_label(window) -> None:
    label = window.statusBar().findChild(QLabel)
    assert label is not None, "the status bar has no permanent label"
    assert label is window.status_mouse_pos
    assert label.text() == ""


def test_the_status_bar_still_says_ready(window) -> None:
    assert window.statusBar().currentMessage() == "Ready"


def test_the_position_follows_the_active_canvas(window) -> None:
    window.onFileNew()
    _APP.processEvents()

    view = window.getCurrentNodeEditorWidget().view
    view.scenePosChanged.emit(12, -34)
    _APP.processEvents()

    assert window.status_mouse_pos.text() == "Scene Pos: [12, -34]"


def test_switching_workflows_moves_the_readout(window) -> None:
    """Two open workflows: the readout must follow the active one."""
    window.onFileNew()
    _APP.processEvents()
    first = window.getCurrentNodeEditorWidget()

    window.onFileNew()
    _APP.processEvents()
    second = window.getCurrentNodeEditorWidget()
    assert first is not second

    second.view.scenePosChanged.emit(5, 6)
    _APP.processEvents()
    assert window.status_mouse_pos.text() == "Scene Pos: [5, 6]"

    # Re-activating the first workflow must hand the readout back to it.
    sub = window.mdiArea.subWindowList()
    for candidate in sub:
        if candidate.widget() is first:
            window.mdiArea.setActiveSubWindow(candidate)
            break
    _APP.processEvents()

    first.view.scenePosChanged.emit(7, 8)
    _APP.processEvents()
    assert window.status_mouse_pos.text() == "Scene Pos: [7, 8]"


def test_a_transient_message_does_not_clobber_the_readout(window) -> None:
    window.onFileNew()
    _APP.processEvents()
    view = window.getCurrentNodeEditorWidget().view
    view.scenePosChanged.emit(1, 2)
    _APP.processEvents()

    window.statusBar().showMessage("File loaded", 5000)
    _APP.processEvents()

    assert window.status_mouse_pos.text() == "Scene Pos: [1, 2]"


def test_the_readout_clears_when_a_window_without_a_canvas_comes_forward(
    window,
) -> None:
    """The coordinates of the last canvas do not describe the next window."""
    window.onFileNew()
    _APP.processEvents()
    view = window.getCurrentNodeEditorWidget().view
    view.scenePosChanged.emit(3, 4)
    _APP.processEvents()
    assert window.status_mouse_pos.text() == "Scene Pos: [3, 4]"

    plain = window.mdiArea.addSubWindow(QWidget())
    window.onSubWindowActivated(plain)
    _APP.processEvents()

    assert window.status_mouse_pos.text() == ""
