#!/usr/bin/env python3
"""Dock separators show the native resize cursors, not Qt's split cursors.

Qt's dock layout sets ``Qt::SplitHCursor`` / ``Qt::SplitVCursor`` while a
draggable separator is hovered. Windows draws those as Qt's own bitmap arrows,
so a dock edge and the window frame showed two different resize pointers.
``install_dock_resize_cursor`` rewrites the shape in the window's
``CursorChange`` notification, before the private separator helper sees it.

The events are addressed to the window directly: the separator is painted by
``QMainWindow`` and is not a child widget, so ``QTest.mouseMove`` - which
hit-tests through the window system - never reaches the helper offscreen.
"""

from collections.abc import Iterator

import pytest
from qtpy.QtCore import QEvent, QPoint, Qt
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.layout_state import apply_default_layout
from trigger_designer.qt.main_window import TriggerWindow

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def window() -> Iterator[TriggerWindow]:
    win = TriggerWindow()
    win.resize(1200, 800)
    win.show()
    apply_default_layout(win)
    _APP.processEvents()
    yield win
    win.hide()
    win.deleteLater()
    _APP.processEvents()


def _send(
    window: TriggerWindow,
    kind: QEvent.Type,
    point: QPoint,
    button: Qt.MouseButton,
    buttons: Qt.MouseButton,
) -> None:
    event = QMouseEvent(
        kind,
        point,
        window.mapToGlobal(point),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(window, event)


def _move(window: TriggerWindow, point: QPoint) -> Qt.CursorShape:
    """Deliver a real separator mouse move and read the resulting cursor."""
    _send(
        window,
        QEvent.Type.MouseMove,
        point,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
    )
    return window.cursor().shape()


def _separator_cursor(
    window: TriggerWindow, points: list[QPoint], where: str
) -> Qt.CursorShape:
    """The first non-arrow cursor found along the points, i.e. an edge."""
    for point in points:
        shape = _move(window, point)
        if shape != Qt.CursorShape.ArrowCursor:
            return shape
    raise AssertionError(f"no draggable dock separator found {where}")


def test_vertical_dock_edge_uses_the_width_cursor(window: TriggerWindow) -> None:
    config = window.configDock.geometry()
    canvas = window.mdiArea.geometry()
    y = config.top() + 80
    points = [QPoint(x, y) for x in range(config.right() - 2, canvas.left() + 2)]

    shape = _separator_cursor(window, points, "between the Config dock and the canvas")

    assert shape == Qt.CursorShape.SizeHorCursor, (
        f"the vertical dock edge shows {shape.name}, expected SizeHorCursor "
        "(the same arrow as the window's side border)"
    )


def test_horizontal_dock_edge_uses_the_height_cursor(window: TriggerWindow) -> None:
    config = window.configDock.geometry()
    logging_dock = window.loggingDock.geometry()
    # Well inside the Config dock's width: its right edge is the *vertical*
    # separator this test is not about.
    x = config.width() // 4
    points = [QPoint(x, y) for y in range(config.bottom() - 2, logging_dock.top() + 2)]

    shape = _separator_cursor(window, points, "between the Config and Logging docks")

    assert shape == Qt.CursorShape.SizeVerCursor, (
        f"the horizontal dock edge shows {shape.name}, expected SizeVerCursor "
        "(the same arrow as the window's bottom border)"
    )


def test_repeated_moves_keep_the_native_cursor(window: TriggerWindow) -> None:
    config = window.configDock.geometry()
    canvas = window.mdiArea.geometry()
    y = config.top() + 80
    point = QPoint((config.right() + canvas.left()) // 2, y)

    assert _move(window, point) == Qt.CursorShape.SizeHorCursor
    assert _move(window, point) == Qt.CursorShape.SizeHorCursor


def test_leaving_the_separator_restores_the_arrow(window: TriggerWindow) -> None:
    config = window.configDock.geometry()
    canvas = window.mdiArea.geometry()
    y = config.top() + 80
    edge = QPoint((config.right() + canvas.left()) // 2, y)
    inside = canvas.center()

    assert _move(window, edge) == Qt.CursorShape.SizeHorCursor
    assert _move(window, inside) == Qt.CursorShape.ArrowCursor


def test_dragging_the_edge_still_resizes_the_dock(window: TriggerWindow) -> None:
    """The filter only rewrites the cursor; the separator move must survive."""
    config = window.configDock.geometry()
    canvas = window.mdiArea.geometry()
    start = QPoint((config.right() + canvas.left()) // 2, config.top() + 80)
    assert _move(window, start) == Qt.CursorShape.SizeHorCursor

    _send(
        window,
        QEvent.Type.MouseButtonPress,
        start,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
    )
    for step in range(1, 5):
        _send(
            window,
            QEvent.Type.MouseMove,
            start + QPoint(10 * step, 0),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
        )
        _APP.processEvents()
        assert window.cursor().shape() == Qt.CursorShape.SizeHorCursor
    _send(
        window,
        QEvent.Type.MouseButtonRelease,
        start + QPoint(40, 0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
    )
    _APP.processEvents()

    assert window.configDock.width() > config.width()
