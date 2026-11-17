"""The session-only "changed outside" cue on a node (qt/node_graphics.py).

The cue is drawn inside the body, in the margin round the icon tile, so it
adds pixels there and nowhere else. It never changes the node's bounding rect
or shape, it is not serialized, and an unknown kind is the same as no cue.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from qtpy.QtCore import QRectF
from qtpy.QtGui import QColor, QImage, QPainter

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.nodes.Preparation.select import (
    TriggerNode_Select as SelectNode,
)

pytestmark = pytest.mark.ui

KINDS = ("added", "changed", "connected")
_BACKGROUND = QColor("#14171a")
_BODY = 120
_MARGIN = 20


@pytest.fixture
def window() -> Iterator[TriggerSubWindow]:
    win = TriggerSubWindow()
    try:
        yield win
    finally:
        win.deleteLater()


@pytest.fixture
def gr_node(window: TriggerSubWindow):
    node = SelectNode(window.scene)
    window.scene.nodes.append(node)
    return node.grNode


def _render(gr_node) -> QImage:
    """Paint the node item alone onto the background, with a margin all round."""
    side = _BODY + 2 * _MARGIN
    image = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(_BACKGROUND)
    painter = QPainter(image)
    try:
        painter.translate(_MARGIN, _MARGIN)
        gr_node.paint(painter, None, None)
    finally:
        painter.end()
    return image


def _changed(before: QImage, after: QImage) -> list[tuple[int, int]]:
    """The pixel positions where the two renders differ."""
    changed = []
    for y in range(after.height()):
        for x in range(after.width()):
            if before.pixel(x, y) != after.pixel(x, y):
                changed.append((x, y))
    return changed


def _inside_body(x: int, y: int) -> bool:
    return _MARGIN <= x < _MARGIN + _BODY and _MARGIN <= y < _MARGIN + _BODY


@pytest.mark.parametrize("kind", KINDS)
def test_each_kind_paints_only_inside_the_body(gr_node, kind) -> None:
    plain = _render(gr_node)
    gr_node.set_external_cue(kind)
    cued = _render(gr_node)

    changed = _changed(plain, cued)
    assert len(changed) > 100, f"the {kind} cue drew almost nothing"
    assert all(_inside_body(x, y) for x, y in changed)


def test_the_cue_also_shows_at_low_detail(gr_node) -> None:
    gr_node.setDetailState(
        {"detail": False, "content": False, "sockets": False, "label": False}
    )
    plain = _render(gr_node)
    gr_node.set_external_cue("added")
    changed = _changed(plain, _render(gr_node))

    assert len(changed) > 100
    assert all(_inside_body(x, y) for x, y in changed)


def test_the_three_kinds_render_differently(gr_node) -> None:
    renders = {}
    for kind in KINDS:
        gr_node.set_external_cue(kind)
        renders[kind] = _render(gr_node)
    for first, second in (
        ("added", "changed"),
        ("changed", "connected"),
        ("added", "connected"),
    ):
        assert _changed(renders[first], renders[second]), (
            f"{first} and {second} look the same"
        )


def test_clearing_the_cue_restores_the_original_render(gr_node) -> None:
    plain = _render(gr_node)
    gr_node.set_external_cue("changed", "Changed outside Trigger Designer")
    gr_node.set_external_cue("")

    assert _changed(plain, _render(gr_node)) == []


def test_the_cue_does_not_change_the_bounding_rect_or_the_shape(gr_node) -> None:
    rect = QRectF(gr_node.boundingRect())
    shape_rect = QRectF(gr_node.shape().boundingRect())

    gr_node.set_external_cue("added", "Added by the agent")

    assert gr_node.boundingRect() == rect
    assert gr_node.shape().boundingRect() == shape_rect


def test_an_unknown_kind_is_the_same_as_no_cue(gr_node) -> None:
    plain = _render(gr_node)
    gr_node.set_external_cue("moved")

    assert gr_node.external_cue == ""
    assert _changed(plain, _render(gr_node)) == []


def test_kind_and_tip_are_kept_for_the_integrator(gr_node) -> None:
    gr_node.set_external_cue("connected", "Input changed upstream")
    assert gr_node.external_cue == "connected"
    assert gr_node.external_cue_tip == "Input changed upstream"

    gr_node.set_external_cue("")
    assert gr_node.external_cue == ""
    assert gr_node.external_cue_tip == ""
