#!/usr/bin/env python3
"""The monochrome ``ui/`` glyphs follow the theme; the node icons do not.

The ``ui/`` icons ship with a hardcoded ``#D0D0D0`` stroke. On a light theme
that grey lands on a near-white button at a contrast ratio of ~1.4:1, so the
icon is invisible. The node icons are the opposite case: they carry their
node type in their colour, so recolouring them would destroy their meaning.
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

from trigger_designer.qt import theme_icons
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
        theme_icons.clear_cache()

    return _apply


def test_dark_theme_keeps_the_shipped_glyph_colour(theme, rsm) -> None:
    """The dark themes already read well, so they must not change."""
    theme("dark")
    pixmap = rsm.get("icon_options")

    assert _dominant_colour(pixmap).name() == "#d0d0d0"


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


def test_tinting_is_a_no_op_on_dark_themes(theme, rsm) -> None:
    """``themed_pixmap`` returns the raw pixmap on a dark theme."""
    theme("dark")
    raw = rsm.get("icon_options")
    assert theme_icons.themed_pixmap("icon_options", None, raw) is raw


def test_the_two_tone_glyph_keeps_its_cut_out(theme, rsm) -> None:
    """``document_save.svg`` is a shape with a hole; both parts must survive."""
    theme("light")
    manager = get_theme_manager()
    pixmap = rsm.get("icon_save")

    image = pixmap.toImage()
    colours = {
        image.pixelColor(x, y).name()
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() > 200
    }
    assert len(colours) >= 2, "the cut-out was flattened into the shape"
    # The cut-out becomes the button fill, so it reads as a hole.
    assert manager.color("button_bg").name().lower() in {c.lower() for c in colours}


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
    assert _icon_colour(button) == "#d0d0d0"

    theme("light")
    button.apply_theme()

    expected = get_theme_manager().color("text_secondary").name()
    assert _icon_colour(button).lower() == expected.lower()
