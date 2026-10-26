#!/usr/bin/env python3
"""The node menu keeps its internals out of the user's way, and the
statistics shortcut does not collide with Save As.

Two defects lived here:

1. "Mark Dirty", "Mark Descendant Dirty", "Mark Invalid", "Unmark Invalid"
   and "Eval" were in the everyday right-click menu. They are for working
   on the app itself, so they are now behind TRIGGER_DEV_ACTIONS=1.
2. Ctrl+Shift+S was bound to both the workflow statistics and the vendored
   Save As action. Statistics moved to Ctrl+Shift+T; the Data Preview dock
   already owns Ctrl+Shift+D.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest
from qtpy.QtCore import QPoint, Qt
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import QApplication, QMenu

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.helpers import context_menu_mixin

_APP = QApplication.instance() or QApplication([])


@pytest.fixture()
def window():
    win = TriggerSubWindow()
    try:
        yield win
    finally:
        win.deleteLater()


def _menu_titles(menu: QMenu) -> list[str]:
    return [action.text() for action in menu.actions() if action.text()]


def _node_menu(window: TriggerSubWindow, monkeypatch) -> QMenu:
    """Build the node context menu and capture it instead of showing it.

    Patching ``QMenu.exec`` on the Qt type is silently ineffective under
    PySide6 (the call still reaches the C++ slot, so a real menu opens and
    the test hangs until its timeout). A stub subclass patched into the
    mixin's namespace intercepts it on either binding, and the menu that
    gets built is still the real one.
    """
    captured: list[QMenu] = []

    class _CapturingMenu(QMenu):
        def exec(self, *args, **kwargs):
            captured.append(self)

    monkeypatch.setattr(context_menu_mixin, "QMenu", _CapturingMenu)

    from qtpy.QtGui import QContextMenuEvent

    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        QPoint(0, 0),
        QPoint(0, 0),
    )
    window.handleNodeContextMenu(event)
    assert captured, "the context menu was never built"
    return captured[0]


def test_the_developer_actions_are_hidden_by_default(window, monkeypatch) -> None:
    monkeypatch.setattr(context_menu_mixin, "SHOW_DEV_ACTIONS", False)
    titles = _menu_titles(_node_menu(window, monkeypatch))

    assert "Mark Dirty" not in titles
    assert "Mark Descendant Dirty" not in titles
    assert "Mark Invalid" not in titles
    assert "Unmark Invalid" not in titles
    assert "Eval" not in titles


def test_the_user_actions_are_still_there(window, monkeypatch) -> None:
    monkeypatch.setattr(context_menu_mixin, "SHOW_DEV_ACTIONS", False)
    titles = _menu_titles(_node_menu(window, monkeypatch))

    assert "Set Label..." in titles


def test_dismissing_the_menu_does_not_touch_the_node(window, monkeypatch) -> None:
    """A dismissed menu must not mark the node dirty behind the user's back.

    The developer actions are None when they are hidden, and the result of
    the menu is None when it is dismissed - so the comparison has to rule
    the second case out explicitly.
    """
    from trigger_designer.qt.widgets.nodes.Preparation.select import (
        TriggerNode_Select as SelectNode,
    )

    node = SelectNode(window.scene)
    window.scene.nodes.append(node)
    # The click position does not matter here; what matters is that a
    # node is under the cursor.
    monkeypatch.setattr(
        type(window), "resolve_node_candidates", lambda self, item: (node, [node])
    )

    marked: list[bool] = []
    monkeypatch.setattr(type(node), "markDirty", lambda self: marked.append(True))

    monkeypatch.setattr(context_menu_mixin, "SHOW_DEV_ACTIONS", False)
    _node_menu(window, monkeypatch)

    assert marked == [], "dismissing the menu marked the node dirty"


def test_the_developer_actions_come_back_on_request(window, monkeypatch) -> None:
    monkeypatch.setattr(context_menu_mixin, "SHOW_DEV_ACTIONS", True)
    titles = _menu_titles(_node_menu(window, monkeypatch))

    assert "Mark Dirty" in titles
    assert "Mark Descendant Dirty" in titles
    assert "Mark Invalid" in titles
    assert "Unmark Invalid" in titles
    assert "Eval" in titles


def _press(window: TriggerSubWindow, key: Qt.Key, modifiers) -> None:
    event = QKeyEvent(QKeyEvent.Type.KeyPress, key, modifiers)
    window.keyPressEvent(event)


def test_the_statistics_shortcut_is_free(window) -> None:
    """Ctrl+Shift+T reports the statistics; Ctrl+Shift+S belongs to Save As."""
    calls: list[bool] = []
    window.show_workflow_statistics = lambda: calls.append(True)  # type: ignore[method-assign]

    _press(
        window,
        Qt.Key.Key_T,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    assert calls == [True]


def test_save_as_keeps_its_shortcut() -> None:
    """The vendored action is what the user expects Ctrl+Shift+S to do."""
    from trigger_designer.qt.main_window import TriggerWindow

    window = TriggerWindow()
    try:
        assert window.actSaveAs.shortcut().toString() == "Ctrl+Shift+S"
    finally:
        window.hide()
        window.deleteLater()
        _APP.processEvents()


def test_the_statistics_go_to_the_logging_dock(window, monkeypatch) -> None:
    """A windowed build has no console; the dock is where output lives."""
    logged: list[str] = []
    monkeypatch.setattr(
        type(window),
        "logInfo",
        lambda self, message: logged.append(message),
    )
    monkeypatch.setattr(
        type(window),
        "get_workflow_statistics",
        lambda self: {
            "total_executions": 3,
            "total_time": 1.5,
            "average_execution_time": 0.5,
        },
    )

    window.show_workflow_statistics()

    assert len(logged) == 1
    assert "3 run(s)" in logged[0]
    assert "1.500s total" in logged[0]
