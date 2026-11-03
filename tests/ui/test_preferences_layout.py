"""Preferences pages scroll instead of squeezing or overlapping their controls.

Appearance needs more vertical room than the dialog's minimum height: the
theme preview alone is 210px and the theme list 148px. Without a scroll area
Qt ran out of space and painted the theme action row over the list (issue #8).
"""

from __future__ import annotations

from qtpy.QtCore import QPoint, QRect
from qtpy.QtWidgets import QApplication, QScrollArea

from trigger_designer.qt.dialogs.preferences_dialog import PreferencesDialog


def _open_dialog(qtbot, theme_manager) -> PreferencesDialog:
    dialog = PreferencesDialog(None)
    qtbot.addWidget(dialog)
    dialog.resize(dialog.minimumSize())
    dialog.show()
    QApplication.processEvents()
    return dialog


def test_every_page_is_scrollable(qtbot, theme_manager):
    dialog = _open_dialog(qtbot, theme_manager)

    assert dialog.stack.count() == 6
    for index in range(dialog.stack.count()):
        assert isinstance(dialog.stack.widget(index), QScrollArea)


def test_theme_actions_clear_the_list_and_fit_the_viewport(qtbot, theme_manager):
    dialog = _open_dialog(qtbot, theme_manager)
    scroll = dialog.stack.currentWidget()
    viewport = QRect(
        scroll.viewport().mapTo(dialog, QPoint(0, 0)),
        scroll.viewport().size(),
    )
    list_rect = QRect(
        dialog.theme_list.mapTo(dialog, QPoint(0, 0)),
        dialog.theme_list.size(),
    )

    for button in (
        dialog.customize_button,
        dialog.import_button,
        dialog.export_button,
        dialog.delete_button,
    ):
        rect = QRect(button.mapTo(dialog, QPoint(0, 0)), button.size())
        assert not rect.intersects(list_rect), f"{button.text()} overlaps the list"
        assert viewport.contains(rect), f"{button.text()} is clipped by the viewport"
