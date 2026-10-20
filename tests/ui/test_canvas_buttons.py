#!/usr/bin/env python3
"""The canvas overlay buttons render and follow the design system.

The four canvas buttons (run, zoom in, zoom out, fit view) used
``QIcon.fromTheme`` on a button with no text, so on Windows they were blank
white rectangles with nothing on them. They are now icon-only ``IconButton``
s: 30x30 with a 12px icon, a tooltip and an accessible name
(docs/DESIGN_SYSTEM.md §4).
"""

import itertools
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest
from qtpy.QtCore import QSize
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow

_APP = QApplication.instance() or QApplication([])


@pytest.fixture()
def window():
    win = TriggerSubWindow()
    try:
        yield win
    finally:
        win.deleteLater()


def _buttons(window: TriggerSubWindow) -> list:
    return [
        window.run_button,
        window.zoom_in_button,
        window.zoom_out_button,
        window.fit_button,
    ]


def test_every_canvas_button_has_a_visible_icon(window) -> None:
    """The defect: ``fromTheme`` renders blank on Windows."""
    for button in _buttons(window):
        assert not button.icon().isNull(), f"{button.toolTip()} has no icon at all"
        assert not button.icon().pixmap(QSize(16, 16)).isNull(), (
            f"{button.toolTip()} renders an empty pixmap"
        )


def test_every_canvas_button_is_an_icon_button(window) -> None:
    for button in _buttons(window):
        assert button.objectName() == "IconButton"
        assert button.text() == "", "an icon button must carry no text"
        assert button.size() == QSize(30, 30)
        assert button.iconSize() == QSize(12, 12)


def test_every_canvas_button_has_a_tooltip_and_an_accessible_name(window) -> None:
    for button in _buttons(window):
        assert button.toolTip(), "a button without a tooltip is unusable"
        assert button.accessibleName() == button.toolTip()


def test_the_canvas_buttons_do_not_overlap(window) -> None:
    """Four 30px buttons need a 36px pitch, not the old 110px."""
    buttons = _buttons(window)
    for left, right in itertools.pairwise(buttons):
        assert left.x() + left.width() <= right.x(), "the canvas buttons overlap"


def test_the_source_does_not_use_from_theme() -> None:
    """A desktop theme icon is the last resort and is blank on Windows."""
    source_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "src",
        "trigger_designer",
        "qt",
        "design_window.py",
    )
    with open(source_path, encoding="utf-8") as handle:
        source = handle.read()
    assert "QIcon.fromTheme" not in source


def test_the_run_button_still_runs_the_workflow(monkeypatch) -> None:
    """The rewrite must not break the wiring."""
    calls: list[bool] = []
    monkeypatch.setattr(
        TriggerSubWindow, "run_workflow", lambda self: calls.append(True)
    )
    window = TriggerSubWindow()
    try:
        window.run_button.click()
    finally:
        window.deleteLater()
    assert calls == [True]
