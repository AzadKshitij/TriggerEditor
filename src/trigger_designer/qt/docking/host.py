"""The interface the app uses to dock panels. No docking library leaks past it."""

from __future__ import annotations

from typing import Protocol

from qtpy.QtGui import QAction
from qtpy.QtWidgets import QWidget

from trigger_designer.qt.docking.layouts import LayoutSpec
from trigger_designer.qt.docking.panel import Panel


class DockHost(Protocol):
    """Owns the canvas and every dockable panel.

    Implementations also expose ``visibility_changed``, a ``Signal(str, bool)``
    carrying ``(panel_id, visible)`` whenever a panel is shown or hidden.
    """

    def widget(self) -> QWidget:
        """The widget to install as the window's central widget."""

    def set_central(self, widget: QWidget) -> None:
        """Put the workflow canvas (the MDI area) in the middle."""

    def register(self, panel: Panel) -> None:
        """Make a panel known to the host. It stays hidden until placed/shown."""

    def panel_ids(self) -> list[str]:
        """Ids of every registered panel, in registration order."""

    def show_panel(self, panel_id: str) -> None:
        """Un-hide the panel and bring its tab to the front."""

    def hide_panel(self, panel_id: str) -> None:
        """Close the panel; its state is kept so showing it again is cheap."""

    def is_visible(self, panel_id: str) -> bool: ...

    def toggle_action(self, panel_id: str) -> QAction:
        """A checkable action that shows/hides the panel (for the Window menu)."""

    def apply_layout(self, spec: LayoutSpec) -> None:
        """Rebuild the arrangement from ``spec`` (used by default and Reset)."""

    def save_state(self) -> bytes:
        """Opaque bytes describing the current arrangement."""

    def restore_state(self, blob: bytes) -> bool:
        """Re-apply ``save_state`` output. False if it could not be applied."""
