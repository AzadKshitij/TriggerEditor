"""The Audit trail group on the General page of Preferences (plan 02 3.14)."""

from __future__ import annotations

from trigger_designer.qt.dialogs import preferences_dialog
from trigger_designer.qt.dialogs.preferences_dialog import PreferencesDialog
from trigger_designer.qt.widgets.common.config_widgets import NoWheelComboBox


def _dialog(qtbot, theme_manager):
    dialog = PreferencesDialog(None)
    qtbot.addWidget(dialog)
    return dialog


def test_dialog_shows_the_defaults(qtbot, clean_preferences, theme_manager):
    dialog = _dialog(qtbot, theme_manager)
    assert dialog.audit_record_check.isChecked() is True
    assert dialog.audit_identity_check.isChecked() is True
    assert dialog.audit_hash_inputs_check.isChecked() is True
    assert dialog.audit_hash_outputs_check.isChecked() is True
    assert dialog.audit_embed_check.isChecked() is True
    assert dialog.audit_warn_check.isChecked() is True
    assert dialog.audit_dir_edit.text() == ""
    assert dialog.audit_counts_combo.currentData() == "auto"
    assert dialog.audit_threshold_spin.value() == 256
    assert dialog.audit_hash_max_spin.value() == 2048


def test_row_count_combo_writes_the_preference(qtbot, clean_preferences, theme_manager):
    dialog = _dialog(qtbot, theme_manager)
    assert isinstance(dialog.audit_counts_combo, NoWheelComboBox)
    labels = [
        dialog.audit_counts_combo.itemText(i)
        for i in range(dialog.audit_counts_combo.count())
    ]
    assert labels == ["Auto", "All nodes", "Sinks only", "Off"]
    dialog.audit_counts_combo.setCurrentIndex(
        dialog.audit_counts_combo.findData("sink")
    )
    assert clean_preferences.get("audit/row_counts") == "sink"
    dialog.audit_counts_combo.setCurrentIndex(dialog.audit_counts_combo.findData("off"))
    assert clean_preferences.get("audit/row_counts") == "off"


def test_checkboxes_and_spins_write_their_keys(qtbot, clean_preferences, theme_manager):
    dialog = _dialog(qtbot, theme_manager)
    dialog.audit_record_check.setChecked(False)
    dialog.audit_identity_check.setChecked(False)
    dialog.audit_hash_inputs_check.setChecked(False)
    dialog.audit_hash_outputs_check.setChecked(False)
    dialog.audit_embed_check.setChecked(False)
    dialog.audit_warn_check.setChecked(False)
    dialog.audit_threshold_spin.setValue(64)
    dialog.audit_hash_max_spin.setValue(100)
    get = clean_preferences.get
    assert get("audit/record_runs") is False
    assert get("audit/record_identity") is False
    assert get("audit/hash_inputs") is False
    assert get("audit/hash_outputs") is False
    assert get("audit/embed_code") is False
    assert get("audit/warn_on_input_change") is False
    assert get("audit/exact_counts_max_mb") == 64
    assert get("audit/hash_max_mb") == 100


def test_folder_edit_and_browse_write_the_preference(
    qtbot, clean_preferences, theme_manager, monkeypatch, tmp_path
):
    dialog = _dialog(qtbot, theme_manager)
    dialog.audit_dir_edit.setText(str(tmp_path / "logs"))
    dialog.audit_dir_edit.editingFinished.emit()
    assert clean_preferences.get("audit/run_log_dir") == str(tmp_path / "logs")

    chosen = tmp_path / "picked"
    monkeypatch.setattr(
        preferences_dialog.QFileDialog,
        "getExistingDirectory",
        lambda *a, **k: str(chosen),
    )
    dialog._browse_audit_dir()
    assert dialog.audit_dir_edit.text() == str(chosen)
    assert clean_preferences.get("audit/run_log_dir") == str(chosen)


def test_saved_values_are_loaded_back(qtbot, clean_preferences, theme_manager):
    clean_preferences.set("audit/row_counts", "all")
    clean_preferences.set("audit/embed_code", False)
    clean_preferences.set("audit/exact_counts_max_mb", 12)
    clean_preferences.set("audit/run_log_dir", "D:/logs")
    dialog = _dialog(qtbot, theme_manager)
    assert dialog.audit_counts_combo.currentData() == "all"
    assert dialog.audit_embed_check.isChecked() is False
    assert dialog.audit_threshold_spin.value() == 12
    assert dialog.audit_dir_edit.text() == "D:/logs"


def test_loading_does_not_rewrite_the_preferences(
    qtbot, clean_preferences, theme_manager
):
    changes: list[str] = []
    clean_preferences.changed.connect(lambda key, _value: changes.append(key))
    _dialog(qtbot, theme_manager)
    assert [key for key in changes if key.startswith("audit/")] == []
