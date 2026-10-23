"""Error preferences appear on the General page and round-trip."""

from __future__ import annotations

from trigger_designer.qt.dialogs.preferences_dialog import PreferencesDialog


def test_general_page_roundtrips_error_prefs(qtbot, clean_preferences, theme_manager):
    dialog = PreferencesDialog(None)
    qtbot.addWidget(dialog)
    assert dialog.continue_check.isChecked() is True
    assert dialog.redact_check.isChecked() is False
    assert dialog.locate_check.isChecked() is True
    assert dialog.locate_cap_spin.value() == 5_000_000

    dialog.continue_check.setChecked(False)
    dialog.redact_check.setChecked(True)
    dialog.locate_check.setChecked(False)
    dialog.locate_cap_spin.setValue(1_000_000)

    assert clean_preferences.get("errors/continue_past_failure", True) is False
    assert clean_preferences.get("errors/redact_values", False) is True
    assert clean_preferences.get("errors/locate_rows", True) is False
    assert clean_preferences.get("errors/locate_row_cap", 0) == 1_000_000
