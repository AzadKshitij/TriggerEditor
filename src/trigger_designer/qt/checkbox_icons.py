"""Checkbox indicator images drawn for the active theme.

The compiled ``:/qss_icons`` checkbox PNGs only exist for the dark palette, so
on a light theme they are pale boxes on a pale background. ``base.qss`` takes
its indicator images from the ``checkbox_*`` tokens returned here instead:
Material Symbols tinted with the theme's own colours, written once per colour
set into a temp folder (QSS ``image:`` needs a file, not a pixmap).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from qtpy.QtGui import QColor, QGuiApplication

_SIZE = 18

# state -> (Material symbol, filled?, token holding its colour)
_STATES = {
    "unchecked": ("check_box_outline_blank", False, "text_secondary"),
    "unchecked_focus": ("check_box_outline_blank", False, "accent_primary"),
    "unchecked_disabled": ("check_box_outline_blank", False, "text_disabled"),
    "checked": ("check_box", True, "accent_primary"),
    "checked_focus": ("check_box", True, "accent_secondary"),
    "checked_disabled": ("check_box", True, "text_disabled"),
    "indeterminate": ("indeterminate_check_box", True, "accent_primary"),
    "indeterminate_focus": ("indeterminate_check_box", True, "accent_secondary"),
    "indeterminate_disabled": ("indeterminate_check_box", True, "text_disabled"),
    # On a selected (accent-filled) row the accent-coloured box would vanish.
    "unchecked_selected": ("check_box_outline_blank", False, "text_on_accent"),
    "checked_selected": ("check_box", True, "text_on_accent"),
    "indeterminate_selected": ("indeterminate_check_box", True, "text_on_accent"),
}

TOKENS = frozenset(f"checkbox_{state}" for state in _STATES)


def checkbox_tokens(tokens: dict) -> dict[str, str]:
    """``checkbox_<state>`` -> image path (forward slashes) for ``tokens``."""
    if QGuiApplication.instance() is None:
        return {f"checkbox_{state}": "" for state in _STATES}
    from qt_material_icons import MaterialIcon

    folder = Path(tempfile.gettempdir()) / "trigger_designer_checkbox"
    folder.mkdir(exist_ok=True)
    out: dict[str, str] = {}
    for state, (symbol, fill, colour_token) in _STATES.items():
        colour = QColor(tokens[colour_token])
        base = folder / f"{state}_{colour.name().lstrip('#')}"
        icon = MaterialIcon(symbol, MaterialIcon.OUTLINED, fill=fill, size=20)
        for suffix, scale in ((".png", 1), ("@2x.png", 2)):
            target = Path(f"{base}{suffix}")
            if not target.exists():
                icon.pixmap(_SIZE * scale, color=colour).save(str(target), "PNG")
        out[f"checkbox_{state}"] = f"{base}.png".replace("\\", "/")
    return out
