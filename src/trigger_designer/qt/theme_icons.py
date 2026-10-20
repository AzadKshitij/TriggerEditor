"""Theme-aware rendering for the monochrome ``ui/`` icon set.

The ``ui/`` glyphs (``resources/qt/images/node_icons/ui/*.svg``) ship with a
hardcoded ``#D0D0D0`` stroke. On the dark themes that reads fine against the
button fill, but on a light theme the same grey lands on a near-white button
at a contrast ratio of ~1.4:1 - the icon is effectively invisible (measured:
1.06:1 for the white add/remove PNGs).

This module re-renders those glyphs against the active theme's own tokens
instead of the baked-in ones:

* the *ink* colour (the glyph) becomes the theme's ``text_secondary``;
* the *cut-out* colour (the hole punched through the glyph) becomes the
  theme's ``button_bg``, so it keeps reading as a hole on any theme;
* anything in between is interpolated, which keeps the two-tone glyphs
  (``document_save.svg``, ``folder_open.svg``) intact.

Colours are ranked by luminance and mapped onto the two anchors, so the
result is correct for every theme without a per-theme table.

Two rules keep the change small and safe:

* **Only light themes are tinted.** The dark themes keep the shipped
  ``#D0D0D0`` pixels byte for byte, so nothing that already reads well
  changes.
* **Node icons are never touched.** They encode node type by colour (red
  ``Input/``, purple ``Join/``, ...), so they are returned unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from loguru import logger
from qtpy.QtCore import QRect, Qt
from qtpy.QtGui import QColor, QIcon, QPainter, QPixmap
from qtpy.QtSvg import QSvgRenderer

#: Resources under this path are monochrome glyphs and follow the theme.
UI_ICON_PATH_PREFIX = "qt/images/node_icons/ui/"

#: Raster resources that are monochrome and follow the theme too.
UI_ICON_RASTER_IDS = frozenset({"icon_add", "icon_remove"})

_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")

#: Cache of already-tinted pixmaps, keyed by (resource id, theme signature).
#: A theme switch produces a different signature, so the old entry is simply
#: unused rather than stale.
_TINT_CACHE: dict[tuple[str, str], QPixmap] = {}


def is_themable(resource_id: str, path: str | None) -> bool:
    """Whether ``resource_id`` is a monochrome glyph that should follow the theme."""
    if resource_id in UI_ICON_RASTER_IDS:
        return True
    return bool(path) and path.startswith(UI_ICON_PATH_PREFIX)


def _relative_luminance(colour: QColor) -> float:
    """WCAG relative luminance of ``colour``."""

    def channel(value: int) -> float:
        v = value / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(colour.red())
        + 0.7152 * channel(colour.green())
        + 0.0722 * channel(colour.blue())
    )


def _theme_anchors() -> tuple[QColor, QColor]:
    """The two colours a glyph is mapped onto: the cut-out and the ink."""
    from trigger_designer.qt.theme_manager import get_theme_manager

    try:
        manager = get_theme_manager()
        ink = manager.color("text_secondary", "#D0D0D0")
        cutout = manager.color("button_bg", "#191E21")
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.debug(f"Theme icon tint unavailable: {exc}")
        ink = QColor("#D0D0D0")
        cutout = QColor("#191E21")
    return cutout, ink


def theme_is_light() -> bool:
    """Whether the active theme is a light one (and so needs tinted icons)."""
    try:
        from trigger_designer.qt.theme_manager import get_theme_manager

        return get_theme_manager().active_theme().appearance == "light"
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.debug(f"Theme appearance unavailable: {exc}")
        return False


def theme_signature() -> str:
    """A string that changes whenever the theme's icon colours change."""
    cutout, ink = _theme_anchors()
    return f"{cutout.name()}|{ink.name()}"


def _colour_map(svg_text: str, cutout: QColor, ink: QColor) -> dict[str, str]:
    """Map each colour in ``svg_text`` onto the theme's cut-out/ink ramp.

    Colours are ranked by luminance: the darkest becomes the cut-out (it is
    the hole punched through the glyph), the lightest becomes the ink, and
    the rest are interpolated between them. A single-colour glyph is all ink.
    """
    colours = sorted({m.group(0) for m in _HEX_RE.finditer(svg_text)})
    if not colours:
        return {}
    if len(colours) == 1:
        return {colours[0]: ink.name(QColor.NameFormat.HexRgb)}

    ranked = sorted(colours, key=lambda c: _relative_luminance(QColor(c)))
    darkest, lightest = ranked[0], ranked[-1]
    dark_lum = _relative_luminance(QColor(darkest))
    light_lum = _relative_luminance(QColor(lightest))
    span = max(light_lum - dark_lum, 1e-6)

    mapping: dict[str, str] = {}
    for colour in colours:
        position = (_relative_luminance(QColor(colour)) - dark_lum) / span
        position = min(max(position, 0.0), 1.0)
        blended = QColor(
            round(cutout.red() + (ink.red() - cutout.red()) * position),
            round(cutout.green() + (ink.green() - cutout.green()) * position),
            round(cutout.blue() + (ink.blue() - cutout.blue()) * position),
        )
        mapping[colour] = blended.name(QColor.NameFormat.HexRgb)
    return mapping


def render_svg(path: Path, cutout: QColor, ink: QColor) -> QPixmap:
    """Render the SVG at ``path`` with its palette mapped onto the theme."""
    try:
        svg_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning(f"Unable to read icon {path}: {exc}")
        return QPixmap()

    mapping = _colour_map(svg_text, cutout, ink)
    for source, target in mapping.items():
        svg_text = re.sub(re.escape(source), target, svg_text, flags=re.IGNORECASE)

    renderer = QSvgRenderer()
    if not renderer.load(svg_text.encode("utf-8")):
        logger.warning(f"Unable to parse icon {path}")
        return QPixmap()

    size = renderer.defaultSize()
    pixmap = QPixmap(size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    return pixmap


def tint_raster(pixmap: QPixmap, ink: QColor) -> QPixmap:
    """Recolour a monochrome raster to ``ink``, keeping the alpha channel.

    The add/remove glyphs are solid white with an antialiased fringe; the
    alpha already carries the shape, so only the hue has to change.
    """
    tinted = QPixmap(pixmap.size())
    tinted.fill(Qt.GlobalColor.transparent)
    image = pixmap.toImage()
    painter = QPainter(tinted)
    try:
        for y in range(image.height()):
            for x in range(image.width()):
                pixel = image.pixelColor(x, y)
                if pixel.alpha() == 0:
                    continue
                painter.setPen(Qt.GlobalColor.transparent)
                painter.setBrush(
                    QColor(ink.red(), ink.green(), ink.blue(), pixel.alpha())
                )
                painter.drawRect(QRect(x, y, 1, 1))
    finally:
        painter.end()
    return tinted


def themed_pixmap(
    resource_id: str,
    path: Path | None,
    raw: QPixmap,
    signature: str | None = None,
) -> QPixmap:
    """Return ``raw`` recoloured for the active theme.

    ``raw`` is the untinted resource (the SVG rendered by the resource
    manager, or the raster loaded from disk). On a dark theme the raw
    pixmap is returned unchanged, so dark rendering stays byte for byte
    what it was.
    """
    if raw.isNull() or not theme_is_light():
        return raw

    key = (resource_id, signature or theme_signature())
    cached = _TINT_CACHE.get(key)
    if cached is not None:
        return cached

    cutout, ink = _theme_anchors()
    if path is not None and path.suffix.lower() == ".svg":
        tinted = render_svg(path, cutout, ink)
    else:
        tinted = tint_raster(raw, ink)

    _TINT_CACHE[key] = tinted
    return tinted


def themed_icon(
    resource_id: str,
    path: Path | None,
    raw: QPixmap,
    signature: str | None = None,
) -> QIcon:
    """Return ``resource_id`` as an icon recoloured for the active theme."""
    return QIcon(themed_pixmap(resource_id, path, raw, signature))


def clear_cache() -> None:
    """Drop the tinted-pixmap cache (used when the theme changes)."""
    _TINT_CACHE.clear()
