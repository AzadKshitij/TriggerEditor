"""Choosing an open document in the Window menu must activate it.

``updateWindowMenu`` wired each document action to ``windowMapper.map`` and
registered the target with ``setMapping``, but never connected the mapper's
signal to ``QMdiArea.setActiveSubWindow``. ``map()`` emitted into nothing, so
the menu entry did nothing. Qt 6 also renamed the mapper's ``mapped`` signal to
``mappedInt``/``mappedString``/``mappedObject``, so the connection cannot be
restored under the old name.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from qtpy.QtWidgets import QApplication, QMdiSubWindow

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


def _open_two_documents(window: TriggerWindow) -> list[QMdiSubWindow]:
    window.onFileNew()
    _APP.processEvents()
    window.onFileNew()
    _APP.processEvents()
    return window.mdiArea.subWindowList()


def _document_actions(window: TriggerWindow) -> list:
    window.updateWindowMenu()
    return [
        action
        for action in window.windowMenu.actions()
        if action.isCheckable() and "New Graph" in action.text()
    ]


@pytest.mark.parametrize("target_index", [0, 1])
def test_choosing_a_document_in_the_window_menu_activates_it(
    window: TriggerWindow, target_index: int
) -> None:
    documents = _open_two_documents(window)
    other = documents[1 - target_index]
    target = documents[target_index]

    # Start on the other document so the action has to switch, not merely
    # re-activate the document that is already in front.
    window.mdiArea.setActiveSubWindow(other)
    _APP.processEvents()
    assert window.mdiArea.activeSubWindow() is other

    actions = _document_actions(window)
    assert len(actions) == len(documents)
    actions[target_index].trigger()
    _APP.processEvents()

    assert window.mdiArea.activeSubWindow() is target
    assert window.getCurrentNodeEditorWidget() is target.widget()
