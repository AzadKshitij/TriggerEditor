#!/usr/bin/env python3
"""Node geometry honesty: what a node declares must cover what it draws.

A node paints two things outside its own body: the status badge, centred on the
bottom edge, and the state ring, stroked with a 5px pen. ``boundingRect`` used to
return the body alone, so Qt never repainted the badge's lower half and every
frame of a drag left another copy of it behind - the trail of green check badges
under a dragged node.
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
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.nodes.Preparation.select import (
    TriggerNode_Select as SelectNode,
)

_APP = QApplication.instance() or QApplication([])


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
def node(window: TriggerSubWindow):
    created = SelectNode(window.scene)
    window.scene.nodes.append(created)
    created.grNode.setPos(-60.0, 40.0)
    _APP.processEvents()
    return created


@pytest.fixture
def isolated_node(window: TriggerSubWindow):
    """A node with no edges, so only the node reports a changed region."""
    created = SelectNode(window.scene)
    window.scene.nodes.append(created)
    # Outside the viewport centre: the harness picks the node under the cursor.
    created.grNode.setPos(400.0, 500.0)
    _APP.processEvents()
    return created


def test_the_declared_rect_covers_the_body_the_badge_and_the_ring(node) -> None:
    gr_node = node.grNode

    declared = gr_node.boundingRect()

    assert declared.contains(gr_node.bodyRect())
    assert declared.contains(gr_node.statusBadgeRect())
    half_ring = gr_node.RING_PEN_WIDTH / 2.0
    ring = gr_node.bodyRect().adjusted(-half_ring, -half_ring, half_ring, half_ring)
    assert declared.contains(ring), f"the ring paints outside {declared}"


def test_the_declared_rect_is_not_just_the_body(node) -> None:
    """The regression itself: the badge hangs below the body."""
    gr_node = node.grNode

    assert not gr_node.bodyRect().contains(gr_node.statusBadgeRect())
    assert gr_node.boundingRect() != gr_node.bodyRect()
    assert gr_node.boundingRect().bottom() > gr_node.bodyRect().bottom()


def test_the_badge_sits_on_the_bottom_edge(node) -> None:
    """The margin has to match the drawing, not just grow the rect."""
    gr_node = node.grNode
    badge = gr_node.statusBadgeRect()
    body = gr_node.bodyRect()

    assert badge.width() == badge.height() == gr_node.STATUS_BADGE_SIDE
    assert badge.center().y() == body.bottom()
    assert badge.center().x() == body.center().x()


def test_moving_a_node_invalidates_the_area_its_badge_covered(
    window, isolated_node
) -> None:
    """What the scene will repaint has to cover the badge's old place too.

    The node moves by one drag step; under the old body-only rectangle the badge
    at the new position fell outside the region, which is what left the trails.
    """
    gr_node = isolated_node.grNode
    gr_scene = window.scene.grScene

    old_badge = gr_node.statusBadgeRect().translated(gr_node.pos())
    regions: list[QRectF] = []
    gr_scene.changed.connect(regions.extend)

    gr_node.setPos(gr_node.pos() + QPointF(8.0, 4.0))
    _APP.processEvents()

    new_badge = gr_node.statusBadgeRect().translated(gr_node.pos())

    assert regions, "the scene reported no changed region for the node move"
    repainted = QRectF(regions[0])
    for rect in regions[1:]:
        repainted = repainted.united(rect)

    assert repainted.contains(old_badge), f"old badge left behind: {old_badge}"
    assert repainted.contains(new_badge), f"new badge clipped away: {new_badge}"
