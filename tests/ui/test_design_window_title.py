#!/usr/bin/env python3
"""Document titles: the MDI window shows the name without the ``.tds`` suffix.

``TriggerSubWindow.getUserFriendlyFilename`` feeds the MDI window title, the
chrome row and the Window menu, so the extension is dropped in one place.
"""

import os
import sys
from collections.abc import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def window() -> Iterator[TriggerSubWindow]:
    win = TriggerSubWindow()
    yield win
    win.deleteLater()


def test_title_drops_the_tds_extension(window: TriggerSubWindow) -> None:
    window.filename = os.path.join("workflows", "1 - Copy.tds")

    window.setTitle()

    assert window.windowTitle() == "1 - Copy"


def test_title_keeps_the_modified_marker(
    window: TriggerSubWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    window.filename = os.path.join("workflows", "monthly_sales.tds")
    monkeypatch.setattr(TriggerSubWindow, "isModified", lambda self: True)

    window.setTitle()

    assert window.windowTitle() == "monthly_sales*"


def test_title_without_a_file_stays_new_graph(window: TriggerSubWindow) -> None:
    window.filename = None

    window.setTitle()

    assert window.windowTitle() == "New Graph"


def test_title_without_an_extension_is_unchanged(window: TriggerSubWindow) -> None:
    window.filename = "notes"

    window.setTitle()

    assert window.windowTitle() == "notes"
