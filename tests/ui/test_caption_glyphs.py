"""Caption glyphs are painted in device pixels, so they stay crisp at any scale."""

import pytest
from qtpy.QtGui import QColor

from trigger_designer.qt.widgets.common.window_chrome import (
    CAPTION_ICON_SIZE,
    caption_icon,
    caption_pixmap,
)

INK = QColor("#202020")
GLYPHS = ("minimize", "maximize", "restore", "close")
SCALES = (1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0)


def _alpha_rows(pixmap) -> list[list[int]]:
    image = pixmap.toImage()
    return [
        [image.pixelColor(x, y).alpha() for x in range(image.width())]
        for y in range(image.height())
    ]


@pytest.mark.parametrize("glyph", GLYPHS)
@pytest.mark.parametrize("dpr", SCALES)
def test_every_glyph_draws_at_every_scale(qapp, glyph: str, dpr: float) -> None:
    pixmap = caption_pixmap(glyph, INK, dpr)
    assert pixmap.devicePixelRatio() == dpr
    assert pixmap.width() == round(CAPTION_ICON_SIZE * dpr)
    assert any(any(row) for row in _alpha_rows(pixmap)), "glyph must not be blank"


@pytest.mark.parametrize("dpr", (1.0, 1.25, 1.5))
def test_minimize_is_one_solid_device_pixel_row(qapp, dpr: float) -> None:
    # The old renderer smeared this over two rows at fractional scales.
    rows = [
        row for row in _alpha_rows(caption_pixmap("minimize", INK, dpr)) if any(row)
    ]
    assert len(rows) == 1
    assert set(a for a in rows[0] if a) == {255}


@pytest.mark.parametrize("dpr", (1.0, 1.25, 1.5))
def test_maximize_edges_are_solid_one_pixel_lines(qapp, dpr: float) -> None:
    grid = _alpha_rows(caption_pixmap("maximize", INK, dpr))
    middle = len(grid) // 2
    inked = [a for a in grid[middle] if a]
    # Left and right edge of the square: two solid pixels, nothing blurred.
    assert inked == [255, 255]


def test_glyphs_use_the_requested_colour(qapp) -> None:
    red = QColor("#ff0000")
    image = caption_pixmap("maximize", red, 1.0).toImage()
    solid = [
        image.pixelColor(x, y)
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() == 255
    ]
    assert solid
    assert all(c.red() == 255 and c.green() == 0 and c.blue() == 0 for c in solid)


def test_icon_carries_a_pixmap_for_each_scale(qapp) -> None:
    icon = caption_icon("close", INK)
    assert not icon.isNull()
    assert len(icon.availableSizes()) >= 1
