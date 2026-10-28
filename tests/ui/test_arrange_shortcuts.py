"""The Arrange menus, their shortcut page, and the snapping switch.

Everything here is offscreen. The menu tests build the real widgets; the
shortcut tests drive the real ``QKeySequenceEdit``s, because the store alone
does not prove the page is wired to it.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
)

import pytest
from qtpy.QtCore import QPoint
from qtpy.QtGui import QContextMenuEvent, QKeySequence
from qtpy.QtWidgets import QApplication, QMenu

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.dialogs.preferences_dialog import PreferencesDialog
from trigger_designer.qt.helpers import context_menu_mixin, node_arrange, shortcuts

_APP = QApplication.instance() or QApplication([])

PORTABLE = QKeySequence.SequenceFormat.PortableText


def _text(editor) -> str:
    return editor.keySequence().toString(PORTABLE)


# -- Edit > Arrange -------------------------------------------------------


def test_edit_menu_holds_the_arrange_commands_and_the_snap_toggle():
    from trigger_designer.qt.main_window import TriggerWindow

    window = TriggerWindow()
    try:
        menu = window.arrangeMenu
        labels = [action.text() for action in menu.actions()]
        for command in node_arrange.COMMANDS:
            assert command.label in labels
            assert getattr(window, command.action) in menu.actions()
        assert "Snap to Grid" in labels
        assert window.actToggleSnap.isCheckable()
    finally:
        window.hide()
        window.deleteLater()
        _APP.processEvents()


def test_arrange_actions_follow_the_selection_size():
    from trigger_designer.qt.main_window import TriggerWindow

    class _Item:
        def __init__(self, node) -> None:
            self.node = node

    class _Active:
        def __init__(self, nodes) -> None:
            self.scene = type(
                "Scene",
                (),
                {"getSelectedItems": lambda self: [_Item(n) for n in nodes]},
            )()

    window = TriggerWindow()
    try:
        one = _Active([object()])
        window._updateArrangeActions(one, True)
        assert not window.actArrangeAlignH.isEnabled()
        assert not window.actArrangeRow.isEnabled()

        two = _Active([object(), object()])
        window._updateArrangeActions(two, True)
        assert window.actArrangeAlignH.isEnabled()
        assert window.actArrangeRow.isEnabled()
        assert not window.actArrangeDistributeH.isEnabled()

        three = _Active([object(), object(), object()])
        window._updateArrangeActions(three, True)
        assert window.actArrangeDistributeH.isEnabled()
    finally:
        window.hide()
        window.deleteLater()
        _APP.processEvents()


# -- node context menu ----------------------------------------------------


@pytest.fixture()
def sub_window():
    win = TriggerSubWindow()
    try:
        yield win
    finally:
        win.deleteLater()


def _node_menu(window, monkeypatch) -> QMenu:
    captured: list[QMenu] = []

    class _CapturingMenu(QMenu):
        def exec(self, *args, **kwargs):
            captured.append(self)

    monkeypatch.setattr(context_menu_mixin, "QMenu", _CapturingMenu)
    from trigger_designer.qt.widgets.nodes.Preparation.select import (
        TriggerNode_Select as SelectNode,
    )

    node = SelectNode(window.scene)
    window.scene.nodes.append(node)
    monkeypatch.setattr(
        type(window), "resolve_node_candidates", lambda self, item: (node, [node])
    )
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse, QPoint(0, 0), QPoint(0, 0)
    )
    window.handleNodeContextMenu(event)
    assert captured, "the context menu was never built"
    return captured[0]


def test_context_menu_has_an_arrange_submenu(sub_window, monkeypatch):
    menu = _node_menu(sub_window, monkeypatch)
    arrange = next(
        action.menu() for action in menu.actions() if action.text() == "Arrange"
    )
    labels = [action.text() for action in arrange.actions()]

    for command in node_arrange.COMMANDS:
        assert command.label in labels
    assert "Snap to Grid" in labels
    assert arrange.actions()[-1].isCheckable()


def test_context_menu_disables_arrangements_the_selection_cannot_run(
    sub_window, monkeypatch
):
    menu = _node_menu(sub_window, monkeypatch)
    arrange = next(
        action.menu() for action in menu.actions() if action.text() == "Arrange"
    )
    by_label = {action.text(): action for action in arrange.actions()}

    assert not by_label["Align Horizontal Centers"].isEnabled()
    assert not by_label["Arrange in Row"].isEnabled()
    assert by_label["Snap to Grid"].isEnabled()


# -- real nodes -----------------------------------------------------------


def test_a_real_node_can_be_arranged_and_undone(sub_window):
    """The helpers must read the node API the app really has.

    ``TriggerNode.pos`` is a property forwarding to the graphics item, not a
    method; a test double with ``pos()`` hid a crash that made every Arrange
    command fail in the running app.
    """
    from trigger_designer.qt.widgets.nodes.Preparation.select import (
        TriggerNode_Select as SelectNode,
    )

    left = SelectNode(sub_window.scene)
    right = SelectNode(sub_window.scene)
    sub_window.scene.nodes.extend([left, right])
    left.grNode.setPos(0.0, 0.0)
    right.grNode.setPos(300.0, 100.0)

    assert node_arrange.apply_command(
        sub_window.scene, "align_centers_h", [left, right]
    )

    # The selection spans 0..(300 + width), so both bodies start at 150.
    assert left.pos.x() == 150.0
    assert right.pos.x() == 150.0
    assert (left.pos.y(), right.pos.y()) == (0.0, 100.0)

    assert sub_window.scene.history.undo()
    assert (left.pos.x(), right.pos.x()) == (0.0, 300.0)

    # The Edit menu passes no nodes and relies on the scene selection instead.
    left.grNode.setSelected(True)
    right.grNode.setSelected(True)
    assert node_arrange.apply_command(sub_window.scene, "align_centers_h")
    assert (left.pos.x(), right.pos.x()) == (150.0, 150.0)


# -- Preferences: Shortcuts page -----------------------------------------


def _dialog(qtbot, clean_preferences, theme_manager) -> PreferencesDialog:
    dialog = PreferencesDialog(None)
    qtbot.addWidget(dialog)
    return dialog


def test_shortcuts_page_lists_every_command_with_its_default(
    qtbot, clean_preferences, theme_manager
):
    dialog = _dialog(qtbot, clean_preferences, theme_manager)

    assert set(dialog.shortcut_editors) == {
        command.id for command in node_arrange.SHORTCUT_COMMANDS
    }
    assert _text(dialog.shortcut_editors["align_centers_h"]) == "Ctrl+Shift+H"
    assert _text(dialog.shortcut_editors["arrange_row"]) == ""
    assert dialog.sidebar.item(4).text() == "Shortcuts"


def test_editing_a_shortcut_saves_it(qtbot, clean_preferences, theme_manager):
    dialog = _dialog(qtbot, clean_preferences, theme_manager)
    editor = dialog.shortcut_editors["arrange_row"]
    editor.setKeySequence(QKeySequence("Ctrl+Alt+R"))

    assert dialog._commit_shortcut("arrange_row")
    assert shortcuts.load_shortcuts(clean_preferences)["arrange_row"] == "Ctrl+Alt+R"
    assert dialog.shortcut_error.isHidden()


def test_a_conflicting_shortcut_is_refused_and_put_back(
    qtbot, clean_preferences, theme_manager
):
    dialog = _dialog(qtbot, clean_preferences, theme_manager)
    editor = dialog.shortcut_editors["align_centers_v"]
    editor.setKeySequence(QKeySequence("Ctrl+Shift+H"))

    assert not dialog._commit_shortcut("align_centers_v")
    assert not dialog.shortcut_error.isHidden()
    assert "Align Horizontal Centers" in dialog.shortcut_error.text()
    assert _text(editor) == dialog._shortcuts["align_centers_v"]
    assert shortcuts.load_shortcuts(clean_preferences)["align_centers_v"] == (
        "Ctrl+Shift+V"
    )


def test_restore_defaults_forgets_every_override(
    qtbot, clean_preferences, theme_manager
):
    dialog = _dialog(qtbot, clean_preferences, theme_manager)
    dialog.shortcut_editors["arrange_row"].setKeySequence(QKeySequence("Ctrl+Alt+R"))
    dialog._commit_shortcut("arrange_row")

    dialog._restore_all_shortcuts()

    assert shortcuts.load_shortcuts(clean_preferences) == shortcuts.defaults()
    assert _text(dialog.shortcut_editors["arrange_row"]) == ""


def test_snap_checkbox_writes_the_preference_and_reaches_an_open_canvas(
    qtbot, clean_preferences, theme_manager
):
    window = TriggerSubWindow()
    window.scene.grScene.snap_to_grid = True
    try:
        dialog = _dialog(qtbot, clean_preferences, theme_manager)
        assert dialog.snap_to_grid_check.isChecked()

        dialog.snap_to_grid_check.setChecked(False)

        assert clean_preferences.get("editor/snap_to_grid", True) is False
        assert window.scene.grScene.snap_to_grid is False
    finally:
        window.deleteLater()
        _APP.processEvents()


def test_snap_checkbox_shows_the_stored_value(qtbot, clean_preferences, theme_manager):
    clean_preferences.set("editor/snap_to_grid", False)
    dialog = _dialog(qtbot, clean_preferences, theme_manager)

    assert not dialog.snap_to_grid_check.isChecked()


# -- applying -------------------------------------------------------------


def test_defaults_are_applied_to_a_windows_actions():
    from trigger_designer.qt.main_window import TriggerWindow

    window = TriggerWindow()
    try:
        window.refreshShortcuts()
        assert window.actArrangeAlignH.shortcut().toString(PORTABLE) == "Ctrl+Shift+H"
        assert window.actArrangeDistributeH.shortcut().isEmpty()
    finally:
        window.hide()
        window.deleteLater()
        _APP.processEvents()
