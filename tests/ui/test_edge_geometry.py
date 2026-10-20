#!/usr/bin/env python3
"""Edge geometry honesty: what an edge declares must cover what it draws.

The canvas showed smeared arcs and loops while a node was dragged. An edge was
painting a stroke that reached outside its own ``boundingRect``: the outer band
of the previous stroke was therefore never repainted, and each frame of a drag
left another band behind. Two things made the item dishonest.

1. ``QDMGraphicsEdge.boundingRect`` returned the bare path rect, while ``paint``
   strokes that path with pens up to 5px wide. Qt's own ``QGraphicsPathItem``
   inflates for the pen; the override dropped that.
2. The path was only adopted inside ``paint``, so a repaint invalidated the
   previous geometry and drew the new one.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest
from qtpy.QtCore import QPointF, QRectF
from qtpy.QtGui import QColor, QPainterPath, QPainterPathStroker, QPen
from qtpy.QtWidgets import QApplication, QGraphicsPathItem

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.nodes.Preparation.select import (
    TriggerNode_Select as SelectNode,
)

_APP = QApplication.instance() or QApplication([])

#: Every pen ``QDMGraphicsEdge.paint`` can stroke with.
_PEN_ATTRS = ("_pen", "_pen_selected", "_pen_dragging", "_pen_hovered")


def _curve(*points: tuple[float, float]) -> QPainterPath:
    path = QPainterPath(QPointF(*points[0]))
    for point in points[1:]:
        path.lineTo(QPointF(*point))
    return path


def _stroke_of(path: QPainterPath, width: float) -> QRectF:
    stroker = QPainterPathStroker()
    stroker.setWidth(width)
    return stroker.createStroke(path).boundingRect()


@pytest.fixture
def window() -> Iterator[TriggerSubWindow]:
    win = TriggerSubWindow()
    # Shown even offscreen: QGraphicsScene only reports its changed regions once
    # a view is attached and the event loop drains.
    win.resize(900, 600)
    win.show()
    _APP.processEvents()
    try:
        yield win
    finally:
        win.close()
        win.deleteLater()


@pytest.fixture
def edge(window: TriggerSubWindow):
    """A real project edge: TriggerEdge -> CachedGraphicsEdge."""
    scene = window.scene
    source = SelectNode(scene)
    target = SelectNode(scene)
    scene.nodes.extend([source, target])
    source.grNode.setPos(-200.0, 0.0)
    target.grNode.setPos(120.0, 60.0)
    created = scene.getEdgeClass()(scene, source.outputs[0], target.inputs[0])
    _APP.processEvents()
    return created


def test_qt_itself_inflates_a_path_item_rect_for_the_pen() -> None:
    """The invariant the override has to keep: a stroke reaches past the path."""
    path = _curve((0.0, 0.0), (40.0, 90.0), (120.0, -60.0), (160.0, 20.0))
    item = QGraphicsPathItem(path)
    pen = QPen(QColor("green"))
    pen.setWidthF(5.0)
    item.setPen(pen)

    stroke = _stroke_of(path, 5.0)

    assert item.boundingRect().contains(stroke)
    # And the bare path rect, which the override used to return, does not.
    assert not path.boundingRect().contains(stroke)


@pytest.mark.parametrize("pen_attr", _PEN_ATTRS)
def test_the_declared_rect_covers_the_stroke_each_pen_draws(edge, pen_attr) -> None:
    gr_edge = edge.grEdge
    pen = getattr(gr_edge, pen_attr)

    declared = gr_edge.boundingRect()
    stroke = _stroke_of(gr_edge.path(), pen.widthF())

    assert declared.contains(stroke), (
        f"{pen_attr} ({pen.widthF()}px) paints outside the declared rect "
        f"{declared} vs {stroke}"
    )


def test_the_widest_pen_is_the_hovered_one_edge_uses(edge) -> None:
    """Guards the margin: if a pen gets wider, the asserted margin must grow."""
    widths = {attr: getattr(edge.grEdge, attr).widthF() for attr in _PEN_ATTRS}

    assert max(widths.values()) == widths["_pen_hovered"] == 5.0


def test_a_moved_edge_declares_its_new_geometry_before_it_paints(window, edge) -> None:
    """The item must adopt the new path on the move, not during the repaint."""
    gr_edge = edge.grEdge
    before = QRectF(gr_edge.boundingRect())

    edge.start_socket.node.grNode.setPos(-320.0, -140.0)
    edge.updatePositions()

    # Comment says "before it paints": nothing painted this item since the move,
    # so the path and the declared rect have to be current already.
    adopted = gr_edge.path()
    expected = gr_edge.calcPath()

    assert adopted == expected
    assert QRectF(gr_edge.boundingRect()) != before
    assert QRectF(gr_edge.boundingRect()).contains(
        _stroke_of(expected, gr_edge._pen_hovered.widthF())
    )


def test_moving_an_edge_invalidates_the_old_stroke_as_well_as_the_new(
    window, edge
) -> None:
    """The end-to-end property: the region Qt repaints covers both strokes.

    This is what was missing while dragging. The scene reports the rectangles it
    will repaint, so this is Qt's own accounting. Only the edge moves, so the
    reported region is the edge's own contribution and the assertion is
    sensitive to the pen margin (``test_the_declared_rect_covers_the_stroke_*``
    pins it directly).
    """
    gr_scene = window.scene.grScene
    gr_edge = edge.grEdge
    width = gr_edge._pen_hovered.widthF()

    old_stroke = _stroke_of(gr_edge.path(), width)
    regions: list[QRectF] = []
    gr_scene.changed.connect(regions.extend)

    destination = gr_edge.posDestination
    gr_edge.setDestination(destination[0] + 60.0, destination[1] + 90.0)
    _APP.processEvents()

    new_stroke = _stroke_of(gr_edge.path(), width)

    assert regions, "the scene reported no changed region for the edge move"
    repainted = QRectF(regions[0])
    for rect in regions[1:]:
        repainted = repainted.united(rect)

    assert repainted.contains(old_stroke), f"old stroke left behind: {old_stroke}"
    assert repainted.contains(new_stroke), f"new stroke clipped away: {new_stroke}"
