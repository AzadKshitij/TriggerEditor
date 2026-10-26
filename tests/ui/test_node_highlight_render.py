#!/usr/bin/env python3
"""The selection and hover rings survive the canvas simplifying.

At low zoom the canvas stops drawing the card and paints the node icon
instead. That branch bypassed ``QDMIconGraphicsNode.paint``, which is the only
place the rings are drawn, so a selected node lost its highlight exactly when
the user zoomed out to look at the whole graph.
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
from qtpy.QtGui import QColor, QImage, QPainter
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.nodes.Preparation.select import (
    TriggerNode_Select as SelectNode,
)

_APP = QApplication.instance() or QApplication([])

_BACKGROUND = QColor("#14171a")


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


def _render_node(gr_node, scale: float) -> QImage:
    """Paint ``gr_node`` into an image at ``scale``, with room for its ring."""
    margin = 20.0
    side = max(1, int((gr_node.width + 2.0 * margin) * scale))
    image = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(_BACKGROUND)
    painter = QPainter(image)
    try:
        painter.scale(scale, scale)
        painter.translate(margin, margin)
        gr_node.paint(painter, None, None)
    finally:
        painter.end()
    return image


def _added_pixels(before: QImage, after: QImage, channel: str) -> int:
    """Pixels ``after`` paints in ``channel`` that ``before`` did not.

    Comparing two renders keeps the node's own icon out of the count; only the
    ring changed between them.
    """
    added = 0
    for y in range(after.height()):
        for x in range(after.width()):
            old = before.pixelColor(x, y)
            new = after.pixelColor(x, y)
            if channel == "green":
                if (
                    new.green() > old.green() + 60
                    and new.green() > new.red() + 40
                    and new.green() > new.blue() + 40
                ):
                    added += 1
            elif (
                new.blue() > old.blue() + 60
                and new.blue() > new.red() + 80
                and new.blue() > new.green() + 40
            ):
                added += 1
    return added


@pytest.mark.parametrize("scale", [0.44, 0.25, 0.1])
def test_the_selection_ring_stays_visible_at_every_low_zoom(window, node, scale):
    gr_scene = window.scene.grScene
    gr_node = node.grNode

    gr_scene.setDetailLod(True)
    assert gr_scene.updateDetailLod(scale) is True
    assert not gr_node._content_visible

    gr_node.setSelected(False)
    plain = _render_node(gr_node, scale)
    gr_node.setSelected(True)
    selected = _render_node(gr_node, scale)

    assert _added_pixels(plain, selected, "green") > 10


def test_the_highlight_pens_do_not_scale_with_the_view(window, node) -> None:
    """A scene-space pen is what made the ring fade out in the first place."""
    gr_node = node.grNode
    assert gr_node._pen_selected.isCosmetic()
    assert gr_node._pen_hovered.isCosmetic()


def test_the_hover_ring_stays_visible_at_low_zoom(window, node):
    scale = 0.25
    gr_scene = window.scene.grScene
    gr_node = node.grNode

    gr_scene.setDetailLod(True)
    assert gr_scene.updateDetailLod(scale) is True
    assert not gr_node._content_visible

    gr_node.setSelected(False)
    plain = _render_node(gr_node, scale)
    gr_node.hovered = True
    try:
        hovered = _render_node(gr_node, scale)
    finally:
        gr_node.hovered = False

    assert _added_pixels(plain, hovered, "blue") > 10
