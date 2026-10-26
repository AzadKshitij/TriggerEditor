#!/usr/bin/env python3
"""Canvas painting at every zoom, including the levels that drop detail.

Three reported regressions live here.

1. ``QDMGraphicsScene.drawBackground`` painted its two grid-line batches with
   ``painter.drawLines(*lines_dark)``. PyQt6 has no zero-argument overload of
   ``drawLines``, so an empty batch raised ``TypeError`` - and the batch empties
   the moment the minor grid lines are dropped, i.e. as soon as the user zooms
   out far enough to take in a graph.
2. Zooming out blanked every node: the level-of-detail state hid each node's
   content widget, and that widget *is* the node's whole look (a pixmap).
3. The level-of-detail flip ran inside the scene's paint pass, where hiding an
   item leaves the pixels it already claimed on screen; those ghosts then drifted
   with every scroll. The view now decides before it paints.
"""

import os
import sys
from collections.abc import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest
from qtpy.QtGui import QImage, QPainter
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.nodes.Preparation.select import (
    TriggerNode_Select as SelectNode,
)

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def window() -> Iterator[TriggerSubWindow]:
    win = TriggerSubWindow()
    try:
        yield win
    finally:
        win.deleteLater()


@pytest.fixture
def node(window: TriggerSubWindow) -> SelectNode:
    created = SelectNode(window.scene)
    window.scene.nodes.append(created)
    return created


def _paint_background(gr_scene, scale: float) -> None:
    """Run one scene background pass at `scale`, the way a viewport paint does."""
    image = QImage(64, 64, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    painter.scale(scale, scale)
    try:
        gr_scene.drawBackground(painter, gr_scene.sceneRect())
    finally:
        painter.end()


def _painted_pixels(item) -> int:
    """How many pixels of `item`'s own rect its paint would colour."""
    image = QImage(
        int(item.width), int(item.height), QImage.Format.Format_ARGB32_Premultiplied
    )
    image.fill(0)
    painter = QPainter(image)
    try:
        item.paint(painter, None, None)
    finally:
        painter.end()
    return sum(
        1
        for y in range(0, image.height(), 3)
        for x in range(0, image.width(), 3)
        if image.pixelColor(x, y).alpha() > 0
    )


def test_zoomed_out_background_paints_an_empty_minor_batch(window) -> None:
    """The batch that used to raise: only major lines are left at this scale."""
    gr_scene = window.scene.grScene
    scale = gr_scene.MIN_GRID_SPACING_PX / gr_scene.gridSize / 2.0

    # Premise of the test: the scene takes its no-minor-lines branch here, so
    # the light batch is empty and the old ``drawLines(*[])`` form would raise.
    assert gr_scene.gridSize * scale < gr_scene.MIN_GRID_SPACING_PX

    _paint_background(gr_scene, scale)


@pytest.mark.parametrize("scale", [0.22, 0.1, 0.199, 0.2, 0.35, 0.5, 1.0, 2.0, 4.0])
def test_background_paints_at_every_zoom_level(window, scale: float) -> None:
    _paint_background(window.scene.grScene, scale)


def test_background_paints_with_the_grid_switched_off(window) -> None:
    gr_scene = window.scene.grScene
    gr_scene.showGrid = False
    try:
        _paint_background(gr_scene, 0.1)
    finally:
        gr_scene.showGrid = True


def test_painting_the_background_never_flips_the_detail_state(window, node) -> None:
    """The flip must happen before the paint, not inside it (it left ghosts)."""
    gr_scene = window.scene.grScene
    socket = node.outputs[0].grSocket

    _paint_background(gr_scene, gr_scene.DETAIL_LOD_THRESHOLD / 2.0)

    assert gr_scene._detail_visible is True
    assert socket.isVisible()


def test_detail_lod_hides_sockets_below_half_scale_and_restores_them(
    window, node
) -> None:
    gr_scene = window.scene.grScene
    socket = (node.inputs or node.outputs)[0].grSocket

    assert gr_scene.updateDetailLod(gr_scene.DETAIL_LOD_THRESHOLD / 2.0) is True
    assert not socket.isVisible()

    assert gr_scene.updateDetailLod(1.0) is True
    assert socket.isVisible()

    # Same state again: no broadcast, nothing to repaint.
    assert gr_scene.updateDetailLod(1.2) is False


def test_a_zoomed_out_node_still_draws_itself(window, node) -> None:
    """The node must stay visible when the content widget is hidden."""
    gr_scene = window.scene.grScene
    gr_scene.setDetailLod(False)
    assert node.grNode._detail_visible is False
    assert not node.outputs[0].grSocket.isVisible()

    drawn = _painted_pixels(node.grNode)

    assert drawn > 0, "a zoomed-out node painted nothing at all"
    # The stand-in is a blit of the icon pixmap, not a token rectangle.
    assert node.grNode._detailPixmap() is not None


def test_a_detailed_node_draws_its_content_pass(window, node) -> None:
    """Sanity check on the measurement above: detail on paints more than nothing."""
    assert node.grNode._detail_visible is True

    assert _painted_pixels(node.grNode) > 0


def test_nodes_added_while_zoomed_out_pick_up_the_current_detail_state(window) -> None:
    """A node created after the LOD flip must not appear fully detailed."""
    gr_scene = window.scene.grScene
    gr_scene.setDetailLod(False)

    created = SelectNode(window.scene)
    window.scene.nodes.append(created)
    socket = (created.inputs or created.outputs)[0].grSocket

    assert not socket.isVisible()
    assert created.grNode._detail_visible is False
