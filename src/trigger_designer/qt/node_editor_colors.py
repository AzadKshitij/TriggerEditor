"""Persistence and application for nodeeditor edge/socket color settings.

nodeeditor >=0.7 centralizes edge and socket colors in a process-wide
``NodeEditorColorScheme`` singleton (``nodeeditor.node_colors_config``).
This module is the single owner for reading/writing that scheme to
QSettings and for pushing a change out to every already-open workflow.

QSettings scope is ``Blue Octa / Trigger Designer`` to match the settings
dialog (``qt/models/settings_panel.py``) and recent files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nodeeditor.node_colors_config import get_color_scheme
from qtpy.QtCore import QSettings

if TYPE_CHECKING:
    from trigger_designer.qt.main_window import TriggerWindow

ORG_NAME = "Blue Octa"
APP_NAME = "Trigger Designer"
SETTINGS_GROUP = "node_editor_colors"

# Mirrors nodeeditor.node_colors_config.EdgeColors / SocketColors defaults.
DEFAULT_EDGE_COLORS: dict[str, str] = {
    "default": "#B08848",
    "selected": "#ff00d0",
    "hovered": "#FF37A6FF",
    "dragging": "#333334",
}

DEFAULT_SOCKET_COLORS: dict[str, str] = {
    "outline": "#FF000000",
    "highlight": "#FF37A6FF",
}


def default_node_editor_colors() -> dict[str, dict[str, str]]:
    return {
        "edges": dict(DEFAULT_EDGE_COLORS),
        "sockets": dict(DEFAULT_SOCKET_COLORS),
    }


def load_node_editor_colors(
    settings: QSettings | None = None,
) -> dict[str, dict[str, str]]:
    """Read saved edge/socket colors, falling back to library defaults."""
    owns_settings = settings is None
    settings = settings or QSettings(ORG_NAME, APP_NAME)
    settings.beginGroup(SETTINGS_GROUP)
    try:
        edges = {
            key: str(settings.value(f"edges/{key}", default))
            for key, default in DEFAULT_EDGE_COLORS.items()
        }
        sockets = {
            key: str(settings.value(f"sockets/{key}", default))
            for key, default in DEFAULT_SOCKET_COLORS.items()
        }
    finally:
        settings.endGroup()
        if owns_settings:
            settings.sync()
    return {"edges": edges, "sockets": sockets}


def save_node_editor_colors(
    colors: dict[str, dict[str, str]], settings: QSettings | None = None
) -> None:
    owns_settings = settings is None
    settings = settings or QSettings(ORG_NAME, APP_NAME)
    settings.beginGroup(SETTINGS_GROUP)
    try:
        for key, value in colors["edges"].items():
            settings.setValue(f"edges/{key}", value)
        for key, value in colors["sockets"].items():
            settings.setValue(f"sockets/{key}", value)
    finally:
        settings.endGroup()
        if owns_settings:
            settings.sync()


def apply_node_editor_colors(colors: dict[str, dict[str, str]]) -> None:
    """Update the process-wide nodeeditor color scheme singleton.

    Safe to call before any Scene/edge/socket exists (e.g. at startup):
    new graphics items read the singleton in their own ``initAssets()``.
    """
    scheme = get_color_scheme()
    scheme.edges.set_all(**colors["edges"])
    scheme.sockets.set_all(
        outline=colors["sockets"].get("outline"),
        highlight=colors["sockets"].get("highlight"),
    )


def refresh_open_scenes(main_window: TriggerWindow) -> None:
    """Re-paint already-open workflow scenes with the current color scheme.

    ``apply_node_editor_colors`` only updates the shared singleton; existing
    graphics items were built with the old colors and need their pens/brushes
    rebuilt. ``Scene.setEdgeColors``/``setSocketColors`` do exactly that for
    the scene they're called on, so re-apply the current scheme to each open
    sub-window's scene through that public API.
    """
    scheme = get_color_scheme()
    edge_colors = {
        "default": scheme.edges.default,
        "selected": scheme.edges.selected,
        "hovered": scheme.edges.hovered,
        "dragging": scheme.edges.dragging,
    }
    socket_colors = {
        "outline": scheme.sockets.outline,
        "highlight": scheme.sockets.highlight,
    }
    for subwindow in main_window.mdiArea.subWindowList():
        scene = getattr(subwindow.widget(), "scene", None)
        if scene is None:
            continue
        scene.setEdgeColors(**edge_colors)
        scene.setSocketColors(**socket_colors)
