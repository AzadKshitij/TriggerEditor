"""ThemeManager: schema, resolution, validation, preview, user themes."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from trigger_designer.qt.theme_manager import (
    SYSTEM_THEME_ID,
    ThemeManager,
)

THEMES_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "trigger_designer"
    / "resources"
    / "qt"
    / "themes"
)

_TOKEN_RE = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")


def test_builtin_dark_loads_complete(theme_manager: ThemeManager) -> None:
    theme = theme_manager.theme("dark")
    assert theme.error is None
    assert theme.builtin
    assert theme.tokens["background_primary"] == "#14171b"
    used = set(_TOKEN_RE.findall((THEMES_DIR / "base.qss").read_text("utf-8")))
    assert not used - set(theme.tokens)


def test_stylesheet_formats_without_placeholders(theme_manager: ThemeManager) -> None:
    qss = theme_manager.stylesheet_for("dark")
    assert "#14171b" in qss
    assert "{{" not in qss and "}}" not in qss
    assert "background_primary" not in qss


def test_unknown_theme_falls_back_to_dark(theme_manager: ThemeManager) -> None:
    theme = theme_manager.theme("nope")
    assert theme.error
    assert theme.tokens["background_primary"] == "#14171b"


def test_user_theme_extends_and_overrides(theme_manager: ThemeManager) -> None:
    theme_manager.save_user_theme(
        "midnight",
        "Midnight",
        "dark",
        {"background_primary": "#000000"},
        extends="dark",
    )
    theme = theme_manager.theme("midnight")
    assert theme.error is None
    assert not theme.builtin
    assert theme.tokens["background_primary"] == "#000000"
    assert (
        theme.tokens["text_primary"]
        == theme_manager.theme("dark").tokens["text_primary"]
    )
    assert "#000000" in theme_manager.stylesheet_for("midnight")


def test_user_theme_invalid_colour_is_rejected(theme_manager: ThemeManager) -> None:
    theme_manager.save_user_theme(
        "broken",
        "Broken",
        "dark",
        {"background_primary": "not-a-colour"},
        extends="dark",
    )
    theme = theme_manager.theme("broken")
    assert theme.error is None
    assert theme.warnings, "an invalid colour must be reported"
    # The invalid override is dropped, so the inherited value stands.
    assert (
        theme.tokens["background_primary"]
        == theme_manager.theme("dark").tokens["background_primary"]
    )


def test_child_theme_inherits_everything(theme_manager: ThemeManager) -> None:
    theme_manager.save_user_theme("child", "Child", "dark", {}, extends="dark")
    child = theme_manager.theme("child")
    dark = theme_manager.theme("dark")
    assert child.tokens == dark.tokens


def test_missing_parent_warns_but_still_loads(theme_manager: ThemeManager) -> None:
    theme_manager.save_user_theme("orphan", "Orphan", "dark", {}, extends="ghost")
    theme = theme_manager.theme("orphan")
    assert any("ghost" in warning for warning in theme.warnings)
    assert theme.tokens["background_primary"] == "#14171b"


def test_broken_json_reports_error(theme_manager: ThemeManager) -> None:
    (theme_manager.user_dir).mkdir(parents=True, exist_ok=True)
    (theme_manager.user_dir / "bad.json").write_text("{ not json", encoding="utf-8")
    theme = theme_manager.theme("bad")
    assert theme.error
    assert theme.tokens


def test_accent_override_derives_variants(
    theme_manager: ThemeManager, clean_preferences
) -> None:
    clean_preferences.set("appearance/accent", "#ff0000")
    theme = theme_manager.active_theme()
    assert theme.tokens["accent_primary"] == "#ff0000"
    assert theme.tokens["accent_secondary"] != "#ff0000"
    assert theme.tokens["accent_tertiary"] != "#ff0000"


def test_preview_does_not_persist_and_cancel_restores(
    theme_manager: ThemeManager, clean_preferences
) -> None:
    assert theme_manager.requested_theme_id() == "dark"
    theme_manager.preview("light")
    assert theme_manager.active_theme().appearance == "light"
    assert clean_preferences.get("appearance/theme") == "dark"
    theme_manager.cancel_preview()
    assert theme_manager.active_theme().appearance == "dark"


def test_commit_preview_persists(
    theme_manager: ThemeManager, clean_preferences
) -> None:
    theme_manager.preview("light")
    theme_manager.commit_preview()
    assert clean_preferences.get("appearance/theme") == "light"
    assert theme_manager.requested_theme_id() == "light"


def test_system_theme_resolves(theme_manager: ThemeManager) -> None:
    theme = theme_manager.theme(SYSTEM_THEME_ID)
    assert theme.appearance in {"dark", "light"}
    assert theme.tokens


def test_system_theme_follows_preference(
    theme_manager: ThemeManager, clean_preferences
) -> None:
    clean_preferences.set("appearance/theme", SYSTEM_THEME_ID)
    theme = theme_manager.active_theme()
    assert theme.id == SYSTEM_THEME_ID
    assert theme.appearance == theme_manager.system_appearance()


def test_duplicate_theme_creates_user_copy(theme_manager: ThemeManager) -> None:
    copy = theme_manager.duplicate_theme("dark", "My Dark")
    assert not copy.builtin
    assert copy.id == "my-dark"
    assert (
        copy.tokens["background_primary"]
        == theme_manager.theme("dark").tokens["background_primary"]
    )
    assert (theme_manager.user_dir / "my-dark.json").is_file()


def test_user_theme_can_shadow_a_builtin(theme_manager: ThemeManager) -> None:
    theme_manager.user_dir.mkdir(parents=True, exist_ok=True)
    (theme_manager.user_dir / "light.json").write_text(
        json.dumps(
            {
                "schema": 2,
                "id": "light",
                "name": "Custom Light",
                "appearance": "light",
                "extends": "dark",
                "tokens": {"background_primary": "#123456"},
            }
        ),
        encoding="utf-8",
    )
    theme = theme_manager.theme("light", force=True)
    assert theme.tokens["background_primary"] == "#123456"
    assert not theme.builtin


def test_import_export_round_trip(theme_manager: ThemeManager, tmp_path: Path) -> None:
    source = tmp_path / "import.json"
    source.write_text(
        json.dumps(
            {
                "schema": 2,
                "id": "ocean",
                "name": "Ocean",
                "appearance": "dark",
                "tokens": {"background_primary": "#001122"},
            }
        ),
        encoding="utf-8",
    )
    imported = theme_manager.import_theme(source)
    assert imported.id == "ocean"
    assert imported.tokens["background_primary"] == "#001122"

    target = tmp_path / "exported.json"
    theme_manager.export_theme("ocean", target)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["id"] == "ocean"
    assert data["tokens"]["background_primary"] == "#001122"


def test_import_invalid_file_raises(
    theme_manager: ThemeManager, tmp_path: Path
) -> None:
    source = tmp_path / "empty.json"
    source.write_text("{}", encoding="utf-8")
    from trigger_designer.qt.theme_manager import ThemeError

    with pytest.raises(ThemeError):
        theme_manager.import_theme(source)


def test_delete_user_theme(theme_manager: ThemeManager) -> None:
    theme_manager.save_user_theme(
        "tempy", "Tempy", "dark", {"background_primary": "#010203"}, extends="dark"
    )
    assert theme_manager.delete_user_theme("tempy") is True
    assert theme_manager.delete_user_theme("tempy") is False
    assert theme_manager.theme("dark").builtin


def test_available_themes_lists_builtins_and_user(theme_manager: ThemeManager) -> None:
    theme_manager.save_user_theme(
        "mine", "Mine", "light", {"background_primary": "#fdfdfd"}, extends="light"
    )
    ids = {theme.id for theme in theme_manager.available_themes()}
    assert {"dark", "light", "mine"} <= ids


def test_apply_without_persist_switches_only_for_the_session(
    theme_manager: ThemeManager,
) -> None:
    """An id passed to apply() must be applied even when not remembered."""
    assert theme_manager.requested_theme_id() == "dark"

    theme = theme_manager.apply("light")

    assert theme.id == "light"
    assert theme_manager.active_theme().id == "light"
    assert theme_manager.requested_theme_id() == "dark"


def test_workspace_frame_follows_theme(theme_manager: ThemeManager) -> None:
    """QMdiArea paints its own brush, so the window must re-theme it."""
    from trigger_designer.qt.main_window import TriggerWindow

    window = TriggerWindow()
    assert (
        window.mdiArea.background().color().name()
        == theme_manager.color("canvas_background").name()
    )

    theme_manager.apply("light", persist=True)
    window.apply_appearance()
    assert (
        window.mdiArea.background().color().name()
        == theme_manager.color("canvas_background").name()
    )
