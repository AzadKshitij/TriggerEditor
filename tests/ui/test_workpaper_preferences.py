"""The Engagement group on the General page of Preferences (plan 06 3.3)."""

from __future__ import annotations

from trigger_designer.qt.dialogs import preferences_dialog
from trigger_designer.qt.dialogs.preferences_dialog import PreferencesDialog

KEYS = {
    "engagement_client_edit": "engagement/client_name",
    "engagement_name_edit": "engagement/engagement_name",
    "engagement_period_edit": "engagement/period",
    "engagement_preparer_edit": "engagement/preparer",
}


def _dialog(qtbot, theme_manager):
    dialog = PreferencesDialog(None)
    qtbot.addWidget(dialog)
    return dialog


def test_defaults_are_empty(qtbot, clean_preferences, theme_manager):
    dialog = _dialog(qtbot, theme_manager)
    assert all(getattr(dialog, name).text() == "" for name in KEYS)
    assert dialog.engagement_logo_edit.text() == ""
    for key in (*KEYS.values(), "engagement/logo_path", "export/workpaper_dir"):
        assert clean_preferences.get(key) == ""


def test_engagement_section_roundtrip(qtbot, clean_preferences, theme_manager):
    dialog = _dialog(qtbot, theme_manager)
    for i, (name, key) in enumerate(KEYS.items()):
        edit = getattr(dialog, name)
        edit.setText(f"  value {i} ")
        edit.editingFinished.emit()
        assert clean_preferences.get(key) == f"value {i}"
    reopened = _dialog(qtbot, theme_manager)
    assert [getattr(reopened, name).text() for name in KEYS] == [
        f"value {i}" for i in range(len(KEYS))
    ]


def test_logo_browse_writes_the_preference(
    qtbot, clean_preferences, theme_manager, monkeypatch, tmp_path
):
    dialog = _dialog(qtbot, theme_manager)
    chosen = str(tmp_path / "logo.png")
    monkeypatch.setattr(
        preferences_dialog.QFileDialog,
        "getOpenFileName",
        lambda *a, **k: (chosen, ""),
    )
    dialog._browse_logo()
    assert dialog.engagement_logo_edit.text() == chosen
    assert clean_preferences.get("engagement/logo_path") == chosen
    monkeypatch.setattr(
        preferences_dialog.QFileDialog, "getOpenFileName", lambda *a, **k: ("", "")
    )
    dialog._browse_logo()
    assert clean_preferences.get("engagement/logo_path") == chosen


def test_reset_all_restores_defaults(
    qtbot, clean_preferences, theme_manager, monkeypatch
):
    dialog = _dialog(qtbot, theme_manager)
    dialog.engagement_client_edit.setText("Acme")
    dialog.engagement_client_edit.editingFinished.emit()
    monkeypatch.setattr(
        preferences_dialog.QMessageBox,
        "question",
        lambda *a, **k: preferences_dialog.QMessageBox.StandardButton.Yes,
    )
    dialog._reset_all()
    assert clean_preferences.get("engagement/client_name") == ""
    assert dialog.engagement_client_edit.text() == ""


def test_loading_does_not_rewrite_the_preferences(
    qtbot, clean_preferences, theme_manager
):
    clean_preferences.set("engagement/period", "FY25")
    dialog = _dialog(qtbot, theme_manager)
    assert dialog.engagement_period_edit.text() == "FY25"
    assert clean_preferences.get("engagement/period") == "FY25"
