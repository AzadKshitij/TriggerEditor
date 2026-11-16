"""Native resize cursors on the draggable dock edges.

The main window's dock layout paints the separator between two docks (or a
dock and the central widget) and sets the cursor itself: ``Qt::SplitHCursor``
for a vertical edge, ``Qt::SplitVCursor`` for a horizontal one. On Windows
those shapes use Qt's own bitmap arrows, while the window frame uses
``Qt::SizeHorCursor`` / ``Qt::SizeVerCursor``, which Qt maps to the native
system cursors. The same resize gesture therefore showed two different
pointers.

There is no style hook or attribute for the separator cursor, and the private
separator helper re-applies its choice from the window's ``CursorChange``
notification. This filter rewrites the shape in that notification.

Two details make it work:

* The notification from the ``setCursor()`` below is swallowed, or the helper
  immediately restores its split cursor;
* The platform announces that same cursor change a second time, outside the
  filter call. That echo looks like an ordinary ``CursorChange`` and must be
  swallowed too, or helper and filter trade the two shapes forever.
"""

from __future__ import annotations

from qtpy.QtCore import QEvent, QObject, Qt
from qtpy.QtWidgets import QMainWindow

#: Qt's split cursor -> the native shape the window frame already uses.
_NATIVE_RESIZE = {
    Qt.CursorShape.SplitHCursor: Qt.CursorShape.SizeHorCursor,
    Qt.CursorShape.SplitVCursor: Qt.CursorShape.SizeVerCursor,
}

__all__ = ["install_dock_resize_cursor"]


class _DockResizeCursor(QObject):
    """Swap Qt's split cursors for the system resize arrows on dock edges."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self._window = window
        self._rewriting = False
        #: The native shape applied to the current separator, if any.
        self._applied: Qt.CursorShape | None = None

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is not self._window or event.type() != QEvent.Type.CursorChange:
            return False
        if self._rewriting:
            # Feedback from the setCursor() below; the separator helper must
            # not see it, or it would restore its split cursor at once.
            return True
        shape = self._window.cursor().shape()
        if shape == self._applied:
            # The platform repeats the notification for our own change. The
            # helper would treat it as a foreign cursor and revert.
            return True
        target = _NATIVE_RESIZE.get(shape)
        if target is None:
            self._applied = None
            return False
        self._applied = target
        self._rewriting = True
        try:
            self._window.setCursor(target)
        finally:
            self._rewriting = False
        # The helper handles the same notification and would undo the swap.
        return True


def install_dock_resize_cursor(window: QMainWindow) -> None:
    """Show the system resize arrows while a dock edge is hovered."""
    window.installEventFilter(_DockResizeCursor(window))
