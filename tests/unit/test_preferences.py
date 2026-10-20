"""Preferences: one INI, typed access, legacy migration, reset."""

from __future__ import annotations

from qtpy.QtCore import QSettings

from trigger_designer.qt.preferences import SCHEMA_VERSION, Preferences


def _store(tmp_path, name: str = "preferences.ini"):
    return Preferences(tmp_path / name, migrate=False)


def test_defaults_when_file_missing(tmp_path) -> None:
    prefs = _store(tmp_path)
    assert prefs.get("appearance/theme") == "dark"
    assert prefs.get("appearance/accent") == ""
    assert prefs.get("layout/restore") is True
    assert prefs.get("layout/session") is False
    assert prefs.get("editor/grid_size") == 20
    assert prefs.get("editor/show_grid") is True
    assert prefs.get("editor/render_detail_threshold") == 50
    assert prefs.get("editor/render_detail_card") == "auto"
    assert prefs.get("editor/render_detail_sockets") == "auto"
    assert prefs.get("editor/render_detail_label") == "always"
    assert prefs.get("editor/render_detail_indicator") == "auto"
    assert prefs.get("general/schema_version") == SCHEMA_VERSION
    assert prefs.path.exists()


def test_write_read_round_trip(tmp_path) -> None:
    path = tmp_path / "preferences.ini"
    first = Preferences(path, migrate=False)
    first.set("appearance/theme", "light")
    first.set("editor/grid_size", 42)
    second = Preferences(path, migrate=False)
    assert second.get("appearance/theme") == "light"
    assert second.get("editor/grid_size") == 42


def test_changed_signal(tmp_path) -> None:
    prefs = _store(tmp_path)
    seen = []
    prefs.changed.connect(lambda key, value: seen.append((key, value)))
    prefs.set("editor/show_grid", False)
    assert seen == [("editor/show_grid", False)]


def test_bool_and_int_coercion(tmp_path) -> None:
    prefs = _store(tmp_path)
    prefs.settings.setValue("layout/session", "true")
    prefs.settings.setValue("editor/grid_size", "35")
    prefs.settings.sync()
    assert prefs.get("layout/session") is True
    assert prefs.get("editor/grid_size") == 35
    prefs.settings.setValue("layout/session", "0")
    prefs.settings.sync()
    assert prefs.get("layout/session") is False


def test_migration_from_legacy_scope(tmp_path) -> None:
    legacy = QSettings(str(tmp_path / "legacy.ini"), QSettings.Format.IniFormat)
    legacy.setValue("theme", "light")
    legacy.setValue("grid_size", 33)
    legacy.setValue("show_grid", False)
    legacy.setValue("show_welcome_dialog", False)
    legacy.setValue("recentFiles", ["C:/work/a.td", "C:/work/b.td"])
    legacy.setValue("node_editor_colors/edges/default", "#123456")
    legacy.setValue("data_preview_dock/visible", True)
    legacy.setValue("pos", "10,20")
    legacy.setValue("size", "800,600")
    legacy.sync()

    prefs = _store(tmp_path)
    migrated = prefs.migrate_legacy([legacy])

    assert prefs.get("appearance/theme") == "light"
    assert prefs.get("editor/grid_size") == 33
    assert prefs.get("editor/show_grid") is False
    assert prefs.get("show_welcome_dialog") is False
    assert prefs.get("recentFiles") == ["C:/work/a.td", "C:/work/b.td"]
    assert prefs.get("node_editor_colors/edges/default") == "#123456"
    assert prefs.get("layout/legacy_preview_visible") is True
    assert prefs.get("layout/legacy_pos") == "10,20"
    assert prefs.get("layout/legacy_size") == "800,600"
    assert migrated, "migration should report the keys it copied"


def test_existing_values_win_over_migration(tmp_path) -> None:
    legacy = QSettings(str(tmp_path / "legacy.ini"), QSettings.Format.IniFormat)
    legacy.setValue("theme", "light")
    legacy.setValue("grid_size", 33)
    legacy.sync()

    prefs = _store(tmp_path)
    prefs.set("appearance/theme", "dark")
    prefs.set("editor/grid_size", 12)
    prefs.migrate_legacy([legacy])

    assert prefs.get("appearance/theme") == "dark"
    assert prefs.get("editor/grid_size") == 12


def test_reset_restores_defaults(tmp_path) -> None:
    prefs = _store(tmp_path)
    prefs.set("appearance/theme", "light")
    prefs.set("layout/session", True)
    prefs.reset()
    assert prefs.get("appearance/theme") == "dark"
    assert prefs.get("layout/session") is False
    assert prefs.get("general/schema_version") == SCHEMA_VERSION


def test_reset_prefix_leaves_other_keys(tmp_path) -> None:
    prefs = _store(tmp_path)
    prefs.set("appearance/theme", "light")
    prefs.set("layout/session", True)
    prefs.reset("layout")
    assert prefs.get("layout/session") is False
    assert prefs.get("appearance/theme") == "light"
