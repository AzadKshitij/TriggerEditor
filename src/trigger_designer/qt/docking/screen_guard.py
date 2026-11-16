"""Pull floating windows back onto a screen when they are off every monitor.

A window is reachable when its title strip (the top ``STRIP_HEIGHT`` pixels)
overlaps an available screen area by at least ``MIN_VISIBLE_WIDTH`` x
``MIN_VISIBLE_HEIGHT``, so the user can still grab it. Floating panels restored
from a saved layout after a monitor was unplugged can otherwise be lost. Pure
geometry helpers: nothing here changes a window that is already reachable.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from loguru import logger
from qtpy.QtCore import QRect
from qtpy.QtGui import QGuiApplication
from qtpy.QtWidgets import QWidget

STRIP_HEIGHT = 32
MIN_VISIBLE_WIDTH = 80
MIN_VISIBLE_HEIGHT = 24
# Fraction of the free vertical space above a rescued window.
TOP_BIAS = 0.2


def available_screen_rects() -> list[QRect]:
    """The available geometry of every screen, primary screen first."""
    return [screen.availableGeometry() for screen in QGuiApplication.screens()]


def is_reachable(frame: QRect, available: Sequence[QRect]) -> bool:
    """True when the title strip of ``frame`` can be seen on some available rect."""
    strip = QRect(
        frame.x(), frame.y(), frame.width(), min(STRIP_HEIGHT, frame.height())
    )
    for rect in available:
        visible = strip.intersected(rect)
        if (
            visible.width() >= MIN_VISIBLE_WIDTH
            and visible.height() >= MIN_VISIBLE_HEIGHT
        ):
            return True
    return False


def rescue_offscreen(
    windows: Iterable[QWidget], available: Sequence[QRect] | None = None
) -> int:
    """Move unreachable windows into the first available rect; return how many moved.

    ``available=None`` uses the current screens. Windows that are hidden, None or
    already deleted are skipped. Never raises.
    """
    rects = available_screen_rects() if available is None else list(available)
    if not rects:
        return 0
    target = rects[0]

    moved = 0
    for window in windows:
        try:
            if window is None or window.isHidden():
                continue
            frame = window.frameGeometry()
            if is_reachable(frame, rects):
                continue
            _move_inside(window, target)
            moved += 1
        except RuntimeError as exc:
            logger.debug(f"Skipping window during screen rescue: {exc}")
    return moved


def _move_inside(window: QWidget, target: QRect) -> None:
    """Shrink ``window`` to fit ``target`` and place it centred near the top."""
    frame = window.frameGeometry()
    geometry = window.geometry()
    # Frame minus client size: window decorations, zero on the offscreen platform.
    decor_w = frame.width() - geometry.width()
    decor_h = frame.height() - geometry.height()
    frame_w = min(frame.width(), target.width())
    frame_h = min(frame.height(), target.height())
    if frame_w != frame.width() or frame_h != frame.height():
        window.resize(max(1, frame_w - decor_w), max(1, frame_h - decor_h))
        frame = window.frameGeometry()

    left = target.x() + (target.width() - frame.width()) // 2
    top = target.y() + int((target.height() - frame.height()) * TOP_BIAS)
    # move() positions the frame's top-left corner for top-level windows.
    window.move(left, top)
    logger.debug(f"Rescued off-screen window to ({left}, {top})")
