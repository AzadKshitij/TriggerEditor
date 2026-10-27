#!/usr/bin/env python3
"""The Material button glyphs follow the theme; the node icons do not.

Button and action icons are Material Symbols drawn in the theme's
``text_secondary`` ink, so they stay legible on dark and light buttons alike.
The node icons are the opposite case: they carry their node type in their
colour, so recolouring them would destroy their meaning.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.theme_manager import get_theme_manager

_APP = QApplication.instance() or QApplication([])


def _relative_luminance(colour: QColor) -> float:
    def channel(value: int) -> float:
        v = value / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(colour.red())
        + 0.7152 * channel(colour.green())
        + 0.0722 * channel(colour.blue())
    )


def _contrast(a: QColor, b: QColor) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _dominant_colour(pixmap) -> QColor:
    """The most common opaque colour in ``pixmap``."""
    from collections import Counter

    image = pixmap.toImage()
    counts: Counter = Counter()
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            if colour.alpha() > 200:
                counts[colour.name()] += 1
    assert counts, "the icon painted nothing at all"
    return QColor(counts.most_common(1)[0][0])


def _icon_colour(button) -> str:
    """The ink colour of the glyph a button currently shows."""
    return _dominant_colour(button.icon().pixmap(64, 64)).name()


@pytest.fixture()
def rsm() -> ResourceManager:
    return ResourceManager()


@pytest.fixture()
def theme(theme_manager):
    """The active theme manager, with a clean icon cache."""

    def _apply(theme_id: str) -> None:
        theme_manager.apply(theme_id)
        ResourceManager._cache.clear()

    return _apply


def test_dark_theme_draws_the_glyph_in_the_theme_ink(theme, rsm) -> None:
    theme("dark")
    pixmap = rsm.get("icon_options")

    expected = get_theme_manager().color("text_secondary").name()
    assert _dominant_colour(pixmap).name().lower() == expected.lower()


def test_light_theme_recolours_the_glyph_to_the_theme_ink(theme, rsm) -> None:
    theme("light")
    manager = get_theme_manager()
    pixmap = rsm.get("icon_options")

    expected = manager.color("text_secondary").name()
    assert _dominant_colour(pixmap).name().lower() == expected.lower()


def test_light_theme_glyph_stays_legible_on_its_button(theme, rsm) -> None:
    """The whole point: the icon must be visible against the button fill."""
    theme("light")
    manager = get_theme_manager()
    button_bg = manager.color("button_bg")

    for icon_id in ("icon_options", "icon_add", "icon_search", "icon_zoom_in"):
        pixmap = rsm.get(icon_id)
        assert _contrast(_dominant_colour(pixmap), button_bg) >= 3.0, (
            f"{icon_id} is invisible on the light button "
            f"({_contrast(_dominant_colour(pixmap), button_bg):.2f}:1)"
        )


def test_node_icons_keep_their_type_colour(theme, rsm) -> None:
    """A node icon is red or purple by node type - never recoloured."""
    theme("light")
    pixmap = rsm.get("node_file_input")

    colour = _dominant_colour(pixmap)
    assert colour.name().lower() == "#c92c2f", "the input icon was recoloured"
    assert colour.red() > colour.blue(), "the red input icon lost its hue"


def test_a_button_re_resolves_its_glyph_after_a_theme_switch(theme, rsm) -> None:
    """A button built before the switch must not keep the old glyph.

    ``IconButton.themed`` hands the rendered pixmap to the button, and the
    button remembers the resource it came from. A theme switch drops the
    cached pixmaps, so the button has to ask for its resource again - if it
    cannot, it keeps the glyph it was painted with.
    """
    from trigger_designer.qt.widgets.common.config_widgets import IconButton

    theme("dark")
    button = IconButton.themed("Column options", rsm_icon=rsm.get("icon_options"))
    assert button._resource_id == "icon_options"
    dark_ink = _icon_colour(button)

    theme("light")
    button.apply_theme()

    expected = get_theme_manager().color("text_secondary").name()
    assert _icon_colour(button).lower() == expected.lower()
    assert _icon_colour(button) != dark_ink


def test_every_button_icon_id_renders(rsm) -> None:
    """A mistyped Material name would silently paint nothing."""
    ids = [k for k in ResourceManager._map if k.startswith("icon_")]
    assert ids
    for icon_id in ids:
        pixmap = rsm.get(icon_id)
        assert pixmap is not None and not pixmap.isNull(), icon_id
