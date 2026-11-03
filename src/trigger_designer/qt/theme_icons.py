"""Theme-aware Material Symbols for buttons and actions.

The button/action glyphs are Material Symbols (``qt-material-icons``), drawn
as a single flat colour. They are tinted with the active theme's
``text_secondary`` token, so they read on dark and light themes alike without
a per-theme table.

Node icons are not Material icons and never pass through here: they encode
the node type by colour and are returned unchanged by the resource manager.
"""

from __future__ import annotations

from loguru import logger
from qtpy.QtGui import QColor, QPixmap

#: Design size of the Material resource. Buttons draw the pixmap at 12-14px.
MATERIAL_SIZE = 20

_FALLBACK_INK = "#D0D0D0"


def ink_color() -> QColor:
    """The colour glyphs are drawn in on the active theme."""
    from trigger_designer.qt.theme_manager import get_theme_manager

    try:
        return get_theme_manager().color("text_secondary", _FALLBACK_INK)
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.debug(f"Theme icon ink unavailable: {exc}")
        return QColor(_FALLBACK_INK)


def material_pixmap(name: str, fill: bool = False) -> QPixmap:
    """Render the Material Symbol ``name`` in the active theme's ink colour."""
    from qt_material_icons import MaterialIcon

    icon = MaterialIcon(name, MaterialIcon.OUTLINED, fill=fill, size=MATERIAL_SIZE)
    pixmap = icon.pixmap(MATERIAL_SIZE, color=ink_color())
    if pixmap.isNull():
        logger.warning(f"Unknown Material icon '{name}'")
    return pixmap
