#!/usr/bin/env python3
"""Document titles: the MDI window shows the name without the ``.tds`` suffix.

``TriggerSubWindow.getUserFriendlyFilename`` feeds the MDI window title and the
Window menu, so the extension is dropped in one place. The frameless titlebar
names the application instead; the document name belongs to the MDI tab.
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
from qtpy.QtWidgets import QApplication, QLabel

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.main_window import TriggerWindow

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


def test_chrome_title_shows_the_app_name(tmp_path) -> None:
    """The titlebar names the app; the document name lives in the MDI tab (#7).

    A modified workflow used to replace the app name with its own title, which
    left a stale ``*`` in the titlebar after saving.
    """
    window = TriggerWindow()
    try:
        editor = TriggerSubWindow()
        sub = window.createMdiChild(editor)
        window.resize(1600, 900)
        window.show()
        sub.show()
        window.mdiArea.setActiveSubWindow(sub)
        _APP.processEvents()

        editor.filename = str(tmp_path / "monthly_sales.tds")
        editor.scene.has_been_modified = True
        _APP.processEvents()

        title = window.window_chrome.findChild(QLabel, "WindowChromeTitle")
        assert sub.windowTitle() == "monthly_sales*"
        assert window.windowTitle() == "Trigger Designer"
        assert title.text() == "Trigger Designer"
    finally:
        window.hide()
        window.deleteLater()
        _APP.processEvents()
