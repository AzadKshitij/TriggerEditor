"""screen_guard: reachability checks and off-screen rescue, with injected screens."""

from collections.abc import Iterator

import pytest
from qtpy.QtCore import QRect
from qtpy.QtWidgets import QApplication, QWidget

from trigger_designer.qt.docking.screen_guard import (
    MIN_VISIBLE_HEIGHT,
    MIN_VISIBLE_WIDTH,
    STRIP_HEIGHT,
    is_reachable,
    rescue_offscreen,
)

_APP = QApplication.instance() or QApplication([])

PRIMARY = QRect(0, 0, 1000, 800)
SECONDARY = QRect(1000, 0, 1000, 800)
SCREENS = [PRIMARY, SECONDARY]


def _flush() -> None:
    for _ in range(3):
        _APP.processEvents()


@pytest.fixture
def windows() -> Iterator[list[QWidget]]:
    created: list[QWidget] = []
    yield created
    for widget in created:
        widget.close()
        widget.deleteLater()
    _flush()


def _window(
    windows: list[QWidget],
    x: int,
    y: int,
    w: int = 300,
    h: int = 200,
    *,
    show: bool = True,
) -> QWidget:
    widget = QWidget()
    windows.append(widget)
    widget.resize(w, h)
    widget.move(x, y)
    if show:
        widget.show()
        _flush()
    return widget


def _inside(frame: QRect, rect: QRect) -> bool:
    return (
        frame.left() >= rect.left()
        and frame.top() >= rect.top()
        and frame.right() <= rect.right()
        and frame.bottom() <= rect.bottom()
    )


def test_reachable_window_stays_put_and_is_not_counted(windows: list[QWidget]) -> None:
    window = _window(windows, 100, 100)
    before = window.frameGeometry()

    moved = rescue_offscreen([window], SCREENS)

    assert moved == 0
    assert window.frameGeometry() == before


def test_window_far_off_screen_moves_inside_first_rect(windows: list[QWidget]) -> None:
    window = _window(windows, -5000, -5000)

    moved = rescue_offscreen([window], SCREENS)
    _flush()

    assert moved == 1
    frame = window.frameGeometry()
    assert _inside(frame, PRIMARY)
    # Centred horizontally, 20% of the free vertical space from the top.
    assert frame.x() == (PRIMARY.width() - frame.width()) // 2
    assert frame.y() == int((PRIMARY.height() - frame.height()) * 0.2)


def test_window_larger_than_screen_is_resized_to_fit(windows: list[QWidget]) -> None:
    window = _window(windows, -5000, -5000, w=1500, h=1000)

    moved = rescue_offscreen([window], SCREENS)
    _flush()

    assert moved == 1
    frame = window.frameGeometry()
    assert frame.width() <= PRIMARY.width()
    assert frame.height() <= PRIMARY.height()
    assert _inside(frame, PRIMARY)


def test_title_strip_only_10px_visible_is_unreachable(windows: list[QWidget]) -> None:
    window = _window(windows, -390, 100, w=400, h=300)
    assert not is_reachable(window.frameGeometry(), [PRIMARY])

    moved = rescue_offscreen([window], SCREENS)

    assert moved == 1
    assert _inside(window.frameGeometry(), PRIMARY)


def test_hanging_off_right_edge_with_visible_strip_is_left_alone(
    windows: list[QWidget],
) -> None:
    # Only the rightmost MIN_VISIBLE_WIDTH columns of the strip are on screen.
    x = PRIMARY.right() + 1 - MIN_VISIBLE_WIDTH
    window = _window(windows, x, 100, w=400, h=300)
    before = window.frameGeometry()

    moved = rescue_offscreen([window], [PRIMARY])

    assert moved == 0
    assert window.frameGeometry() == before


def test_empty_available_returns_zero_and_leaves_windows(
    windows: list[QWidget],
) -> None:
    window = _window(windows, -5000, -5000)
    before = window.frameGeometry()

    assert rescue_offscreen([window], []) == 0
    assert window.frameGeometry() == before


def test_hidden_window_is_skipped(windows: list[QWidget]) -> None:
    window = _window(windows, -5000, -5000, show=False)
    before = window.geometry()

    moved = rescue_offscreen([window], SCREENS)

    assert moved == 0
    assert window.geometry() == before


def test_return_value_counts_only_moved_windows(windows: list[QWidget]) -> None:
    reachable = _window(windows, 100, 100)
    far = _window(windows, -5000, -5000)
    hidden = _window(windows, -5000, -5000, show=False)

    moved = rescue_offscreen([reachable, far, hidden], SCREENS)

    assert moved == 1
    assert _inside(far.frameGeometry(), PRIMARY)


def test_is_reachable_width_boundary() -> None:
    width = 400
    x_ok = PRIMARY.left() - (width - MIN_VISIBLE_WIDTH)
    exact = QRect(x_ok, 0, width, 200)
    one_less = QRect(x_ok - 1, 0, width, 200)

    assert is_reachable(exact, [PRIMARY])
    assert not is_reachable(one_less, [PRIMARY])


def test_is_reachable_height_boundary() -> None:
    height = 200
    y_ok = PRIMARY.top() - (STRIP_HEIGHT - MIN_VISIBLE_HEIGHT)
    exact = QRect(0, y_ok, 400, height)
    one_less = QRect(0, y_ok - 1, 400, height)

    assert is_reachable(exact, [PRIMARY])
    assert not is_reachable(one_less, [PRIMARY])
