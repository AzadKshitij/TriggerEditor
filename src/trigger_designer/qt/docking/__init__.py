"""Free-form docking: panels can go anywhere, split, tab, float and reopen.

Plan: ``docs/plans/2026-11-16-docking-system.md``. App code imports from here
only; the docking library behind it is an implementation detail.
"""

from trigger_designer.qt.docking.host import DockHost
from trigger_designer.qt.docking.layouts import Area, LayoutSpec, Placement
from trigger_designer.qt.docking.panel import (
    CENTRAL,
    PANEL_CONFIG,
    PANEL_HISTORY,
    PANEL_LOGS,
    PANEL_PREVIEW,
    Panel,
)

__all__ = [
    "CENTRAL",
    "PANEL_CONFIG",
    "PANEL_HISTORY",
    "PANEL_LOGS",
    "PANEL_PREVIEW",
    "Area",
    "DockHost",
    "LayoutSpec",
    "Panel",
    "Placement",
]
