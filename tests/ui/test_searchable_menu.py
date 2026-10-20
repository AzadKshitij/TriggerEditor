#!/usr/bin/env python3

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import QAction, QApplication, QWidget

from trigger_designer.qt.widgets.node_searchable_menu import SearchableMenu

APP = QApplication.instance() or QApplication([])


def _make_menu(calls):
    parent = QWidget()
    parent.set_selected_action_data = lambda data: setattr(parent, "_data", data)
    parent.add_node_to_scene = lambda: calls.append(getattr(parent, "_data", None))
    menu = SearchableMenu(parent)
    action = QAction("Filter", menu)
    action.setData(["filter-code", "filter-type"])
    menu.all_actions = {"Preparation": [action]}
    menu.showFlatList()
    return menu


def _press_enter(menu):
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier
    )
    menu.keyPressEvent(event)


def test_single_enter_adds_one_node() -> None:
    calls: list = []
    menu = _make_menu(calls)
    # Both Enter paths firing for one keypress (returnPressed, then the menu's
    # own keyPressEvent) must still add exactly one node.
    menu._confirm_first_match()
    _press_enter(menu)
    assert len(calls) == 1, calls
    menu.hide()
    APP.processEvents()


def test_second_showing_can_add_again() -> None:
    calls: list = []
    menu = _make_menu(calls)
    menu._confirm()
    menu.hide()
    APP.processEvents()
    from qtpy.QtGui import QShowEvent

    menu.showEvent(QShowEvent())
    menu.showFlatList()
    menu._confirm()
    assert len(calls) == 2, calls
    menu.hide()
    APP.processEvents()
