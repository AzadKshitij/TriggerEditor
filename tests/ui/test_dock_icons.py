"""Dock title-bar and tab glyphs follow the theme and survive both engines."""

from __future__ import annotations

import pytest
from qtpy.QtGui import QColor, QIcon
from qtpy.QtWidgets import QApplication, QLabel, QMainWindow, QMdiArea, QTextEdit

from trigger_designer.qt.docking import dock_icons
from trigger_designer.qt.docking.ads_host import AdsDockHost
from trigger_designer.qt.docking.layouts import Area, LayoutSpec, Placement
from trigger_designer.qt.docking.panel import CENTRAL, PANEL_CONFIG, PANEL_LOGS, Panel

_APP = QApplication.instance() or QApplication([])


def _flush() -> None:
    for _ in range(5):
        _APP.processEvents()


def _has_colour(icon: QIcon, colour: QColor) -> bool:
    image = icon.pixmap(16, 16).toImage()
    wanted = colour.rgb()
    return any(
        image.pixelColor(x, y).alpha() > 200 and image.pixelColor(x, y).rgb() == wanted
        for x in range(image.width())
        for y in range(image.height())
    )


@pytest.mark.parametrize("glyph", dock_icons.GLYPHS)
def test_each_glyph_is_drawn_in_the_colour_and_fades_when_disabled(glyph) -> None:
    colour = QColor("#e0a040")

    icon = dock_icons.glyph_icon(glyph, colour)

    assert _has_colour(icon, colour)
    disabled = icon.pixmap(16, 16, QIcon.Mode.Disabled).toImage()
    assert (
        max(
            disabled.pixelColor(x, y).alpha()
            for x in range(disabled.width())
            for y in range(disabled.height())
        )
        < 200
    )


def test_an_unknown_glyph_is_refused() -> None:
    with pytest.raises(ValueError):
        dock_icons.glyph_icon("nope", QColor("#fff"))


@pytest.mark.parametrize("theme_id", ["dark", "qlementine-dark"])
def test_the_title_bar_buttons_carry_the_themed_glyphs(
    qtbot, theme_manager, theme_id
) -> None:
    import PySide6QtAds as QtAds

    theme_manager.apply(theme_id, persist=False)
    window = QMainWindow()
    qtbot.addWidget(window)
    window.setCentralWidget(QMdiArea())
    host = AdsDockHost(window)
    host.set_central(QMdiArea())
    host.register(Panel(PANEL_CONFIG, "Node Configuration", QLabel("config")))
    host.register(Panel(PANEL_LOGS, "Logs", QTextEdit("logs")))
    host.apply_layout(
        LayoutSpec(
            name="t",
            placements=(
                Placement(PANEL_CONFIG, Area.LEFT),
                Placement(PANEL_LOGS, Area.BOTTOM, CENTRAL),
            ),
            active=(PANEL_LOGS,),
        )
    )
    window.show()
    _flush()

    colour = theme_manager.color("text_secondary")
    bar = host.area_widget(PANEL_LOGS).titleBar()
    assert _has_colour(bar.button(QtAds.TitleBarButtonTabsMenu).icon(), colour)
    assert _has_colour(bar.button(QtAds.TitleBarButtonUndock).icon(), colour)

    theme_manager.apply("qlementine-solarized-light", persist=False)
    _flush()
    after = theme_manager.color("text_secondary")
    assert after != colour
    assert _has_colour(bar.button(QtAds.TitleBarButtonTabsMenu).icon(), after)
