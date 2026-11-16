"""A dockable panel: what the app hands to a :class:`DockHost`."""

from __future__ import annotations

from dataclasses import dataclass

from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QWidget

#: Stable panel ids. They are persisted in saved layouts - never rename one.
PANEL_CONFIG = "config"
PANEL_LOGS = "logs"
PANEL_PREVIEW = "preview"
PANEL_HISTORY = "history"

#: Pseudo-id for the workflow canvas (the MDI area) in layout placements.
CENTRAL = "central"


@dataclass
class Panel:
    """One panel the user can move, tab, float, close and reopen."""

    panel_id: str
    title: str
    widget: QWidget
    closable: bool = True
    icon: QIcon | None = None
    #: Smallest size the panel may be squeezed to. 0 means "no extra limit".
    min_width: int = 0
    min_height: int = 0
