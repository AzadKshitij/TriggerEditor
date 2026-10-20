#!/usr/bin/env python3
"""The grid settings reach the canvas, even without a console.

The canvas theming used to call ``QDMGraphicsScene.setGridColorLight``,
which writes a debug emoji to stdout. A windowed build has no stdout, so
the write raises - and because the whole block sat in one try/except, the
failure took the grid size and the visibility down with it. The grid
settings in the preferences dialog therefore did nothing at all in the
shipped app.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.theme_manager import apply_theme_to_scene

_APP = QApplication.instance() or QApplication([])


class _NoStdout:
    """A stdout that refuses to encode - what a windowed build looks like."""

    def write(self, _text: str) -> int:
        raise UnicodeEncodeError("charmap", "\U0001f40d", 0, 1, "unencodable")

    def flush(self) -> None:
        pass


@pytest.fixture()
def window():
    win = TriggerSubWindow()
    try:
        yield win
    finally:
        win.deleteLater()


def test_the_grid_settings_survive_a_build_without_a_console(
    window, monkeypatch, theme_manager
) -> None:
    """The grid size and the visibility must reach the canvas."""
    theme_manager.preferences.set("editor/grid_size", 42)
    theme_manager.preferences.set("editor/show_grid", False)

    monkeypatch.setattr(sys, "stdout", _NoStdout())

    apply_theme_to_scene(window.scene, theme_manager)

    gr_scene = window.scene.grScene
    assert gr_scene.gridSize == 42, "the grid size did not reach the canvas"
    assert gr_scene.showGrid is False, "the grid visibility did not reach the canvas"


def test_the_grid_colours_reach_the_canvas(window, monkeypatch, theme_manager) -> None:
    """The colours are painted too, not just the settings."""
    monkeypatch.setattr(sys, "stdout", _NoStdout())

    apply_theme_to_scene(window.scene, theme_manager)

    gr_scene = window.scene.grScene
    assert gr_scene._color_light == theme_manager.color("canvas_grid_light")
    assert gr_scene._color_dark == theme_manager.color("canvas_grid_dark")


def test_the_grid_colours_are_readable_against_the_background(
    window, theme_manager
) -> None:
    """A grid nobody can see is the defect this bundle set out to fix."""
    apply_theme_to_scene(window.scene, theme_manager)

    gr_scene = window.scene.grScene
    background = gr_scene.getBackgroundColor()
    light = gr_scene._color_light
    major = gr_scene._color_dark

    def luminance(colour) -> float:
        def channel(value: int) -> float:
            v = value / 255.0
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        return (
            0.2126 * channel(colour.red())
            + 0.7152 * channel(colour.green())
            + 0.0722 * channel(colour.blue())
        )

    def contrast(a, b) -> float:
        la, lb = luminance(a), luminance(b)
        hi, lo = max(la, lb), min(la, lb)
        return (hi + 0.05) / (lo + 0.05)

    assert contrast(light, background) > 1.15, (
        "the minor grid lines are invisible against the canvas"
    )
    assert contrast(major, background) > 1.15, (
        "the major grid lines are invisible against the canvas"
    )
