#!/usr/bin/env python3
"""Label geometry: a node declares the label plate it paints above its body.

The label paints a rounded plate padded by 6x3 px around its text. Qt repaints a
moved item by the rectangle it declared at the old position, and dirties its
children only at the new one, so a label left out of the node's rectangle stayed
painted wherever the node had been - the stack of plates above a dragged node.
``boundingRect`` used to return the body, the badge and the ring only.
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
from trigger_designer.qt.node_base import TriggerGraphicsNode
from trigger_designer.qt.widgets.nodes.Preparation.select import (
    TriggerNode_Select as SelectNode,
)

_APP = QApplication.instance() or QApplication([])

pytestmark = pytest.mark.skipif(
    not hasattr(TriggerGraphicsNode, "labelRect"),
    reason="needs nodeeditor >= 0.8.2, which declares the floating label",
)


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
def labelled_node(window: TriggerSubWindow):
    created = SelectNode(window.scene)
    window.scene.nodes.append(created)
    # Inside the viewport, so a move dirties both the old and the new position
    # instead of being clipped by the view.
    created.grNode.setPos(200.0, 300.0)
    created.grNode.setLabelText("Formula")
    _APP.processEvents()
    return created


def plate_rect(label) -> QRectF:
    """The box the label paints, in the label's own coordinates."""
    return label.textRect().adjusted(
        -label._pad_x, -label._pad_y, label._pad_x, label._pad_y
    )


def test_the_label_declares_the_plate_it_paints(labelled_node) -> None:
    label = labelled_node.grNode.label_item

    declared = label.boundingRect()

    assert declared.contains(plate_rect(label))
    assert declared.width() > label.textRect().width()
    assert declared.height() > label.textRect().height()


def test_the_node_declares_the_label_above_it(labelled_node) -> None:
    gr_node = labelled_node.grNode

    assert gr_node.isLabelVisible()
    assert gr_node.boundingRect().contains(gr_node.labelRect())
    assert gr_node.labelRect().top() < 0.0, "the label sits above the body"
    assert gr_node.boundingRect().top() < 0.0


def test_the_body_is_still_inside_the_declared_rect(labelled_node) -> None:
    gr_node = labelled_node.grNode

    assert gr_node.boundingRect().contains(gr_node.bodyRect())
    assert gr_node.boundingRect().contains(gr_node.statusBadgeRect())


def test_a_hidden_label_leaves_the_body_alone(labelled_node) -> None:
    gr_node = labelled_node.grNode
    before = gr_node.boundingRect()

    gr_node.setLabelVisible(False)
    _APP.processEvents()

    assert gr_node.boundingRect().height() < before.height()
    assert not gr_node.boundingRect().contains(gr_node.labelRect())


def test_moving_a_node_invalidates_the_plate_it_leaves(window, labelled_node) -> None:
    """What the scene will repaint has to cover the plate's old place too."""
    gr_node = labelled_node.grNode
    gr_scene = window.scene.grScene
    label = gr_node.label_item

    old_plate = label.mapRectToScene(plate_rect(label))
    regions: list[QRectF] = []
    gr_scene.changed.connect(regions.extend)

    gr_node.setPos(gr_node.pos() + QPointF(0.0, 30.0))
    _APP.processEvents()

    new_plate = label.mapRectToScene(plate_rect(label))

    assert regions, "the scene reported no changed region for the node move"
    repainted = QRectF(regions[0])
    for rect in regions[1:]:
        repainted = repainted.united(QRectF(rect))

    assert repainted.contains(old_plate), f"old plate left behind: {old_plate}"
    assert repainted.contains(new_plate), f"new plate clipped away: {new_plate}"
