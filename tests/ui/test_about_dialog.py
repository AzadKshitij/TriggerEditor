#!/usr/bin/env python3
"""The About box describes this application, not the upstream example.

``about()`` used to open a message box titled "About Calculator NodeEditor
Example" with a link to a BlenderFreak tutorial - the boilerplate of the
upstream nodeeditor sample. The replacement shows the app's real name,
version, settings location and repository.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest
from qtpy.QtWidgets import QApplication, QLabel

from trigger_designer.core.constants import VERSION
from trigger_designer.qt.dialogs.about_dialog import REPOSITORY_URL, AboutDialog

_APP = QApplication.instance() or QApplication([])


@pytest.fixture()
def dialog():
    dlg = AboutDialog()
    try:
        yield dlg
    finally:
        dlg.deleteLater()


def _text(dialog: AboutDialog) -> str:
    return " ".join(label.text() for label in dialog.findChildren(QLabel))


def test_the_dialog_names_this_application(dialog) -> None:
    assert dialog.windowTitle() == "About Trigger Designer"
    assert "Trigger Designer" in _text(dialog)


def test_the_dialog_shows_the_real_version(dialog) -> None:
    assert VERSION in _text(dialog)


def test_the_dialog_shows_where_the_settings_live(dialog) -> None:
    """There is no config file - the preferences are one INI."""
    from trigger_designer.qt.preferences import preferences_path

    assert str(preferences_path()) in _text(dialog)


def test_the_dialog_links_to_the_repository(dialog) -> None:
    assert REPOSITORY_URL in _text(dialog)


def test_the_dialog_is_released_when_it_closes(dialog) -> None:
    """Every open of the About box must not leave a window behind."""
    from qtpy.QtCore import Qt

    assert dialog.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)


def test_no_placeholder_text_survives_anywhere() -> None:
    """The old boilerplate must not reappear."""
    root = os.path.join(
        os.path.dirname(__file__), "..", "..", "src", "trigger_designer"
    )
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, encoding="utf-8", errors="replace") as handle:
                source = handle.read()
            assert "BlenderFreak" not in source, path
            assert "Calculator NodeEditor" not in source, path
