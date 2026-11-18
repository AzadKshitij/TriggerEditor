#!/usr/bin/env python3
"""The cut stroke has to leave the canvas when the stroke ends.

``QDMCutLine`` derives its bounding rectangle from ``line_points``. Replacing the
points has to declare the geometry change first, or Qt repaints only the new,
empty rectangle and the dashed stroke stays on screen until something else
repaints the viewport (issue #34). nodeeditor's ``line_points`` setter declares
the change, and ``TriggerCutLine`` inherits that setter.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from nodeeditor.node_graphics_view import MODE_EDGE_CUT, MODE_NOOP
from qtpy.QtCore import QEvent, QPointF, QRectF, Qt
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QApplication, QWidget

from trigger_designer.qt.design_window import TriggerSubWindow

_APP = QApplication.instance() or QApplication([])

_STROKE = (QPointF(40.0, 40.0), QPointF(320.0, 140.0), QPointF(600.0, 300.0))


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


def _send_mouse(widget: QWidget, kind: QEvent.Type, at: QPointF) -> None:
    """A CTRL+left event at ``at``, delivered like the window manager does."""
    event = QMouseEvent(
        kind,
        at,
        QPointF(widget.mapToGlobal(at.toPoint())),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
    )
    _APP.sendEvent(widget, event)


def test_the_stroke_area_is_repainted_when_it_ends_in_blank_space(window) -> None:
    view = window.view

    viewport = view.viewport()
    regions: list[QRectF] = []
    window.scene.grScene.changed.connect(lambda rects: regions.extend(rects))

    _send_mouse(viewport, QEvent.Type.MouseButtonPress, _STROKE[0])
    for point in _STROKE[1:]:
        _send_mouse(viewport, QEvent.Type.MouseMove, point)
    _APP.processEvents()

    assert view.mode == MODE_EDGE_CUT
    stroke = view.cutline.boundingRect()
    # A one-point stroke has a 5x5 bounding rect of its own, which the release
    # repaints either way; require the stroke that reaches across the canvas.
    assert stroke.width() > 100 and stroke.height() > 50, "the stroke never drew"

    regions.clear()
    _send_mouse(viewport, QEvent.Type.MouseButtonRelease, _STROKE[-1])
    _APP.processEvents()

    assert view.mode == MODE_NOOP
    assert view.cutline.line_points == []
    assert any(rect.contains(stroke) for rect in regions), (
        "the area the stroke covered was never repainted, so the line stays"
    )
