"""Tab-only chrome for docks that share a tab group.

Qt draws a dock's own title bar - the panel name plus the float and close
buttons - *and* the dock area's tab bar, so a tabbed dock shows its name twice
and spends a ~24px row on nothing. The tab bar is all the chrome such a panel
needs, and Qt already pops a panel out when its tab is dragged out of the bar,
as long as the window sets ``QMainWindow.DockOption.GroupedDragging``
(``enable_tab_drag_out``).

The title bar is only *hidden* while the dock is a tab: it comes back while the
dock floats, because a custom title bar widget also suppresses the native
window frame Qt gives a floating dock - a popped-out panel without it could not
be moved, resized or closed. A dock that is docked but alone (no tab bar beside
it) also keeps its bar, as that is the only handle that moves it.

Traps:

- Only a custom title bar widget hides the default one. Qt hides the widget it
  replaced instead of deleting it, so one placeholder per dock is reused;
  building a fresh widget per transition would pile up hidden children.
- ``topLevelChanged`` fires before the drop that moved the dock has finished,
  so the tab state is read on the next event loop turn, and the dock may be
  gone by then.
"""

from __future__ import annotations

from functools import partial

from loguru import logger
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QDockWidget, QMainWindow, QWidget

#: objectName of the placeholder that stands in for the default title bar.
TITLE_BAR_NAME = "DockTabOnlyTitleBar"

#: Qt's private container for a floating group of docks. Its children count as
#: docked, and it owns the tab bar and the window frame for them.
_GROUP_WINDOW = "QDockWidgetGroupWindow"

__all__ = ["TITLE_BAR_NAME", "enable_tab_drag_out", "install_tab_only_chrome"]


def enable_tab_drag_out(window: QMainWindow) -> None:
    """Let a dock tab dragged out of the tab bar pop that panel out.

    ``GroupedDragging`` is the option Qt gates the tab bar's unplug path with;
    it also makes dragging the title bar of a tabbed dock move the whole group.
    """
    window.setDockOptions(window.dockOptions() | QMainWindow.DockOption.GroupedDragging)


def install_tab_only_chrome(dock: QDockWidget) -> None:
    """Keep ``dock``'s title bar out of the way while it is a tab."""
    dock.topLevelChanged.connect(partial(_reflect_state, dock))
    _apply(dock)


def _reflect_state(dock: QDockWidget, _floating: bool) -> None:
    QTimer.singleShot(0, partial(_apply, dock))


def _apply(dock: QDockWidget) -> None:
    try:
        dock.setTitleBarWidget(None if _wants_title_bar(dock) else _placeholder(dock))
    except RuntimeError:
        # Tearing the window down can leave a scheduled call behind.
        logger.debug("dock chrome: dock is gone before its title bar was set")


def _wants_title_bar(dock: QDockWidget) -> bool:
    """A floating dock needs its own bar; a tab, or a group member, does not."""
    if dock.isFloating():
        return True
    parent = dock.parentWidget()
    if parent is None:
        return True
    if parent.metaObject().className() == _GROUP_WINDOW:
        return False
    if isinstance(parent, QMainWindow):
        return not parent.tabifiedDockWidgets(dock)
    return True


def _placeholder(dock: QDockWidget) -> QWidget:
    """The empty title bar of ``dock``, created once and reused."""
    bar = dock.findChild(QWidget, TITLE_BAR_NAME)
    if bar is None:
        bar = QWidget(dock)
        bar.setObjectName(TITLE_BAR_NAME)
    return bar
