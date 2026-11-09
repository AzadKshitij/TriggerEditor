#!/usr/bin/env python3
"""Fit View must not rewrite the geometry it measures.

``TriggerGraphicsNode.boundingRect`` caches the declared rect, and the old fit
loop called ``moveTopLeft`` on the returned object. That shifted the cache to
the node's scene position, so Qt cached ``sceneBoundingRect`` at twice that
position, culled the node as off-screen and stopped calling its ``paint``. On a
real graph only the nodes near the origin survived a Fit View; the rest looked
deleted while their edges stayed behind.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from qtpy.QtCore import QPointF, QRectF
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.nodes.Preparation.select import (
    TriggerNode_Select as SelectNode,
)

_APP = QApplication.instance() or QApplication([])

_POSITIONS = ((-400.0, -300.0), (0.0, 0.0), (600.0, 450.0))


@pytest.fixture
def window() -> Iterator[TriggerSubWindow]:
    win = TriggerSubWindow()
    win.resize(900, 600)
    win.show()
    _APP.processEvents()
    try:
        yield win
    finally:
        win.close()
        win.deleteLater()


def _add_nodes(window: TriggerSubWindow) -> list[SelectNode]:
    nodes: list[SelectNode] = []
    for x, y in _POSITIONS:
        node = SelectNode(window.scene)
        window.scene.nodes.append(node)
        node.grNode.setPos(x, y)
        nodes.append(node)
    _APP.processEvents()
    return nodes


def _screen_rect(view, rect: QRectF) -> QRectF:
    top_left = view.mapFromScene(rect.topLeft())
    bottom_right = view.mapFromScene(rect.bottomRight())
    return QRectF(
        QPointF(top_left),
        QPointF(bottom_right),
    )


def test_fit_view_leaves_the_declared_rects_alone(window) -> None:
    nodes = _add_nodes(window)
    before = {
        id(node): (
            QRectF(node.grNode.boundingRect()),
            QRectF(node.grNode.sceneBoundingRect()),
        )
        for node in nodes
    }

    window.fitView()
    _APP.processEvents()

    for node in nodes:
        local, scene = before[id(node)]
        assert node.grNode.boundingRect() == local, (
            "Fit View rewrote the cached boundingRect"
        )
        assert node.grNode.sceneBoundingRect() == scene, (
            "Fit View moved the node's declared scene bounds"
        )


def test_fit_view_puts_every_node_inside_the_viewport(window) -> None:
    nodes = _add_nodes(window)

    window.fitView()
    _APP.processEvents()

    viewport = QRectF(window.view.viewport().rect())
    for node in nodes:
        screen = _screen_rect(window.view, node.grNode.sceneBoundingRect())
        assert viewport.contains(screen), f"{node.title} is outside {viewport}"


@pytest.mark.parametrize(
    ("step", "expected_factor"),
    [
        ("zoomOut", 1 / 1.25),
        ("zoomIn", 1.25),
    ],
)
def test_fit_view_leaves_the_zoom_counter_room_each_way(
    window, step: str, expected_factor: float
) -> None:
    """The first wheel step after Fit View must scale exactly one step.

    A single node fits at a scale above 1.0. ``fitView`` used to write that
    scale into ``view.zoom`` (the step counter), pushing the counter out of
    range. Both wheel directions then sat at a clamp until enough steps walked
    it back, and the first step that did apply jumped by the whole fit scale.
    """
    node = SelectNode(window.scene)
    window.scene.nodes.append(node)
    node.grNode.setPos(0, 0)
    _APP.processEvents()

    window.fitView()
    _APP.processEvents()
    fitted = window.view.transform().m11()
    assert fitted > 1.0, "the fit has to exceed 1:1 to exercise the old bug"

    zoom_factor = getattr(window.view, step)()
    window.view.applyZoom(zoom_factor)
    _APP.processEvents()

    assert window.view.transform().m11() == pytest.approx(fitted * expected_factor)
    low, high = window.view.zoomRange
    assert low <= window.view.zoom <= high
