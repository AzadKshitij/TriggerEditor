#!/usr/bin/env python3
"""Edge style changes participate in undo and mark the document modified.

Issue #21: the context menu assigned ``edge.edge_type`` directly. The vendor
setter only recalculates the graphics path - it records no history step and
never marks the document modified, so closing the document silently dropped
the style change.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from nodeeditor.node_edge import EDGE_TYPE_BEZIER, EDGE_TYPE_DIRECT, Edge
from qtpy.QtCore import QPoint
from qtpy.QtGui import QContextMenuEvent
from qtpy.QtWidgets import QApplication, QMenu

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.helpers import context_menu_mixin
from trigger_designer.qt.widgets.nodes.Preparation.select import (
    TriggerNode_Select as SelectNode,
)

_APP = QApplication.instance() or QApplication([])


@pytest.fixture()
def window(qtbot):
    win = TriggerSubWindow()
    qtbot.addWidget(win)
    return win


def _edge_menu(window: TriggerSubWindow, monkeypatch, edge, chosen: str | None):
    """Capture the edge context menu and return the chosen action from exec_.

    Same trick as ``test_context_menu_dev_actions``: a stub subclass patched
    into the mixin's namespace intercepts the menu before a real one opens,
    and ``exec_`` returns the action a click would have chosen.
    """
    captured: list[QMenu] = []

    class _CapturingMenu(QMenu):
        def exec(self, *args, **kwargs):
            captured.append(self)
            if chosen is None:
                return None
            return next(action for action in self.actions() if action.text() == chosen)

        exec_ = exec

    monkeypatch.setattr(context_menu_mixin, "QMenu", _CapturingMenu)

    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        QPoint(0, 0),
        QPoint(0, 0),
    )
    window.handleEdgeContextMenu(event)
    assert captured, "the edge context menu was never built"
    return captured[0]


def _connected_edge(window: TriggerSubWindow):
    left = SelectNode(window.scene)
    right = SelectNode(window.scene)
    return Edge(window.scene, left.outputs[0], right.inputs[0])


def test_edge_style_change_is_undoable_and_marks_modified(window, monkeypatch) -> None:
    # The vendored Edge defaults to DIRECT; Bezier is a real change.
    edge = _connected_edge(window)
    assert edge.edge_type == EDGE_TYPE_DIRECT
    history = window.scene.history
    history.storeHistory("Baseline")

    def item_at(_scene, _pos):
        return SimpleNamespace(edge=edge)

    monkeypatch.setattr(type(window.scene), "getItemAt", item_at)

    _edge_menu(window, monkeypatch, edge, "Bezier Edge")

    assert edge.edge_type == EDGE_TYPE_BEZIER
    assert window.scene.has_been_modified
    assert history.controller.count == 1

    history.undo()
    current = window.scene.edges[0] if window.scene.edges else edge
    assert current.edge_type == EDGE_TYPE_DIRECT


def test_dismissing_or_repeating_the_menu_changes_nothing(window, monkeypatch) -> None:
    edge = _connected_edge(window)
    history = window.scene.history
    history.storeHistory("Baseline")

    def item_at(_scene, _pos):
        return SimpleNamespace(edge=edge)

    monkeypatch.setattr(type(window.scene), "getItemAt", item_at)

    # A dismissed menu records nothing.
    _edge_menu(window, monkeypatch, edge, None)
    assert edge.edge_type == EDGE_TYPE_DIRECT
    assert history.controller.count == 0
    assert not window.scene.has_been_modified

    # Choosing the style the edge already has is not a change either.
    _edge_menu(window, monkeypatch, edge, "Direct Edge")
    assert edge.edge_type == EDGE_TYPE_DIRECT
    assert history.controller.count == 0
    assert not window.scene.has_been_modified
