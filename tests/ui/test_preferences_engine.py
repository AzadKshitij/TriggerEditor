"""The style engine choice in Preferences and the theme list under it."""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.dialogs.preferences_dialog import PreferencesDialog
from trigger_designer.qt.theme_manager import SYSTEM_THEME_ID


def _open(qtbot, theme_manager) -> PreferencesDialog:
    dialog = PreferencesDialog(None)
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    return dialog


def _ids(dialog: PreferencesDialog) -> list[str]:
    return [
        dialog.theme_list.item(row).data(Qt.ItemDataRole.UserRole)
        for row in range(dialog.theme_list.count())
    ]


def test_the_dialog_opens_on_qlementine_and_lists_only_its_themes(
    qtbot, theme_manager
) -> None:
    dialog = _open(qtbot, theme_manager)

    assert dialog.engine_combo.currentData() == "qlementine"
    ids = _ids(dialog)
    assert ids[0] == SYSTEM_THEME_ID
    assert "qlementine-dark" in ids
    assert "dark" not in ids
    assert all(i == SYSTEM_THEME_ID or i.startswith("qlementine-") for i in ids)
    assert dialog._selected_theme_id() == "qlementine-dark"


def test_switching_to_classic_lists_the_qss_themes_and_keeps_the_look(
    qtbot, theme_manager
) -> None:
    dialog = _open(qtbot, theme_manager)
    dialog._select_theme("qlementine-nord")

    dialog.engine_combo.setCurrentIndex(dialog.engine_combo.findData("qss"))

    ids = _ids(dialog)
    assert "nord" in ids
    assert not any(i.startswith("qlementine-") for i in ids)
    assert dialog._selected_theme_id() == "nord"
    assert theme_manager.active_theme().engine == "qss"


def test_the_engine_choice_is_saved_with_ok_and_dropped_with_cancel(
    qtbot, theme_manager, clean_preferences
) -> None:
    dialog = _open(qtbot, theme_manager)
    dialog.engine_combo.setCurrentIndex(dialog.engine_combo.findData("qss"))
    dialog.reject()
    assert clean_preferences.get("appearance/engine") == "qlementine"
    assert theme_manager.requested_engine() == "qlementine"

    dialog = _open(qtbot, theme_manager)
    dialog.engine_combo.setCurrentIndex(dialog.engine_combo.findData("qss"))
    dialog.accept()

    assert clean_preferences.get("appearance/engine") == "qss"
    assert clean_preferences.get("appearance/theme") == "dark"


def test_system_mode_stays_selected_when_the_engine_changes(
    qtbot, theme_manager
) -> None:
    dialog = _open(qtbot, theme_manager)
    dialog._select_theme(SYSTEM_THEME_ID)

    dialog.engine_combo.setCurrentIndex(dialog.engine_combo.findData("qss"))

    assert dialog._selected_theme_id() == SYSTEM_THEME_ID
    assert theme_manager.active_theme().engine == "qss"
