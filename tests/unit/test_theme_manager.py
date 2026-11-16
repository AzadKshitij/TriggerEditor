"""ThemeManager: schema, resolution, validation, preview, user themes."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from trigger_designer.qt.theme_manager import (
    DERIVED_TOKENS,
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
    assert not used - DERIVED_TOKENS - set(theme.tokens)


def test_stylesheet_formats_without_placeholders(theme_manager: ThemeManager) -> None:
    qss = theme_manager.stylesheet_for("dark")
    assert "#14171b" in qss
    assert "{{" not in qss and "}}" not in qss
    assert "background_primary" not in qss


def test_base_qss_is_read_once_per_manager(
    theme_manager: ThemeManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preview/apply rebuilds the stylesheet often; the file is read once."""
    reads: list[Path] = []
    real_read_text = Path.read_text

    def counting_read_text(self: Path, *args, **kwargs):
        if self.name == "base.qss":
            reads.append(self)
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)

    theme_manager.stylesheet_for("dark")
    theme_manager.stylesheet_for("light")

    assert len(reads) == 1


def test_fallback_tokens_are_cached(
    theme_manager: ThemeManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Warm the theme and the fallback tokens (both read dark.json today).
    theme = theme_manager.theme("dark")

    reads: list[Path] = []
    real_read_data = theme_manager._read_data

    def counting_read_data(path: Path):
        reads.append(Path(path))
        return real_read_data(path)

    monkeypatch.setattr(theme_manager, "_read_data", counting_read_data)

    theme_manager.stylesheet(theme)
    theme_manager.stylesheet(theme)

    # Two stylesheet builds must not re-read the default token file.
    assert sum(path.name == "dark.json" for path in reads) == 0


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
    assert theme_manager.requested_theme_id() == "qlementine-dark"
    theme_manager.preview("light")
    assert theme_manager.active_theme().appearance == "light"
    assert clean_preferences.get("appearance/theme") == "qlementine-dark"
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
    assert theme_manager.requested_theme_id() == "qlementine-dark"

    theme = theme_manager.apply("light")

    assert theme.id == "light"
    assert theme_manager.active_theme().id == "light"
    assert theme_manager.requested_theme_id() == "qlementine-dark"


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


# -- theme engines ------------------------------------------------------------


def test_builtin_qlementine_themes_inherit_colours_and_name_the_engine(
    theme_manager: ThemeManager,
) -> None:
    for theme_id, parent in (
        ("qlementine-dark", "dark"),
        ("qlementine-light", "light"),
    ):
        theme = theme_manager.theme(theme_id)
        assert theme.error is None
        assert theme.builtin
        assert theme.engine == "qlementine"
        assert theme.appearance == theme_manager.theme(parent).appearance
        assert theme.tokens == theme_manager.theme(parent).tokens


def test_classic_themes_default_to_the_qss_engine(theme_manager: ThemeManager) -> None:
    assert theme_manager.theme("dark").engine == "qss"
    assert theme_manager.theme("nord").engine == "qss"


def test_qlementine_themes_are_listed(theme_manager: ThemeManager) -> None:
    ids = {theme.id for theme in theme_manager.available_themes()}
    assert {"qlementine-dark", "qlementine-light"} <= ids


def test_a_theme_inherits_the_engine_it_extends(theme_manager: ThemeManager) -> None:
    theme_manager.save_user_theme(
        "mine", "Mine", "dark", {"accent_primary": "#ff0000"}, extends="qlementine-dark"
    )
    theme = theme_manager.theme("mine")
    assert theme.engine == "qlementine"
    assert theme.tokens["accent_primary"] == "#ff0000"


def test_a_theme_can_override_the_engine_it_extends(
    theme_manager: ThemeManager, tmp_path: Path
) -> None:
    theme_manager.user_dir.mkdir(parents=True, exist_ok=True)
    (theme_manager.user_dir / "classic.json").write_text(
        json.dumps(
            {
                "schema": 2,
                "id": "classic",
                "name": "Classic",
                "appearance": "dark",
                "engine": "qss",
                "extends": "qlementine-dark",
                "tokens": {},
            }
        ),
        encoding="utf-8",
    )
    assert theme_manager.theme("classic").engine == "qss"


def test_only_a_non_default_engine_is_written(theme_manager: ThemeManager) -> None:
    theme_manager.save_user_theme("a", "A", "dark", {"text_primary": "#fff"})
    theme_manager.save_user_theme(
        "b", "B", "dark", {"text_primary": "#fff"}, engine="qlementine"
    )
    a = json.loads((theme_manager.user_dir / "a.json").read_text(encoding="utf-8"))
    b = json.loads((theme_manager.user_dir / "b.json").read_text(encoding="utf-8"))
    assert "engine" not in a
    assert b["engine"] == "qlementine"
    assert theme_manager.theme("b").engine == "qlementine"


def test_duplicate_keeps_the_engine(theme_manager: ThemeManager) -> None:
    copy = theme_manager.duplicate_theme("qlementine-dark", "My Q")
    assert copy.engine == "qlementine"
    assert theme_manager.duplicate_theme("dark", "My Classic").engine == "qss"


def test_export_and_import_round_trip_the_engine(
    theme_manager: ThemeManager, tmp_path: Path
) -> None:
    target = tmp_path / "q.json"
    theme_manager.export_theme("qlementine-dark", target)
    assert json.loads(target.read_text(encoding="utf-8"))["engine"] == "qlementine"

    imported = theme_manager.import_theme(target)
    assert imported.engine == "qlementine"
    assert not imported.builtin


def test_export_of_a_classic_theme_names_no_engine(
    theme_manager: ThemeManager, tmp_path: Path
) -> None:
    target = tmp_path / "d.json"
    theme_manager.export_theme("dark", target)
    assert "engine" not in json.loads(target.read_text(encoding="utf-8"))


def test_an_unknown_engine_falls_back_to_qss_with_a_warning(
    theme_manager: ThemeManager,
) -> None:
    theme_manager.user_dir.mkdir(parents=True, exist_ok=True)
    (theme_manager.user_dir / "weird.json").write_text(
        json.dumps(
            {
                "schema": 2,
                "id": "weird",
                "name": "Weird",
                "appearance": "dark",
                "engine": "neon",
                "extends": "dark",
                "tokens": {},
            }
        ),
        encoding="utf-8",
    )
    theme = theme_manager.theme("weird")
    assert theme.engine == "qss"
    assert any("Unknown engine" in warning for warning in theme.warnings)


def test_a_missing_library_falls_back_to_the_qss_look(
    theme_manager: ThemeManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    from trigger_designer.qt import qlementine_style

    monkeypatch.setattr(qlementine_style, "_q", None)
    theme_manager.invalidate()

    theme = theme_manager.theme("qlementine-dark")
    assert theme.engine == "qlementine"
    assert not theme_manager.uses_qlementine(theme)
    assert any("not installed" in warning for warning in theme.warnings)


def test_a_qlementine_theme_formats_the_same_qss_as_its_parent(
    theme_manager: ThemeManager,
) -> None:
    """The engine decides whether the sheet is applied, not what it says."""
    assert theme_manager.stylesheet_for(
        "qlementine-dark"
    ) == theme_manager.stylesheet_for("dark")


# -- style engines ------------------------------------------------------------


def test_a_fresh_install_starts_on_qlementine(theme_manager: ThemeManager) -> None:
    assert theme_manager.requested_engine() == "qlementine"
    assert theme_manager.active_theme().engine == "qlementine"


def test_every_qss_theme_has_a_qlementine_twin_with_the_same_look(
    theme_manager: ThemeManager,
) -> None:
    qss = {t.id: t for t in theme_manager.themes_for_engine("qss")}
    qlementine = {t.id: t for t in theme_manager.themes_for_engine("qlementine")}

    assert qss, "the classic themes are still shipped"
    for theme_id, classic in qss.items():
        if not classic.builtin:
            continue
        twin = qlementine[f"qlementine-{theme_id}"]
        assert twin.appearance == classic.appearance
        assert twin.tokens == classic.tokens, theme_id  # colours and metrics alike


def test_the_engine_lists_do_not_overlap(theme_manager: ThemeManager) -> None:
    qss = {t.id for t in theme_manager.themes_for_engine("qss")}
    qlementine = {t.id for t in theme_manager.themes_for_engine("qlementine")}

    assert qss.isdisjoint(qlementine)
    assert {t.id for t in theme_manager.available_themes()} == qss | qlementine


@pytest.mark.parametrize(
    ("theme_id", "engine", "expected"),
    [
        ("nord", "qlementine", "qlementine-nord"),
        ("qlementine-nord", "qss", "nord"),
        ("qlementine-dracula", "qlementine", "qlementine-dracula"),
        ("light", "qlementine", "qlementine-light"),
        ("system", "qss", "system"),
    ],
)
def test_switching_engine_keeps_the_same_theme_where_there_is_a_twin(
    theme_manager: ThemeManager, theme_id: str, engine: str, expected: str
) -> None:
    assert theme_manager.counterpart_id(theme_id, engine) == expected


def test_a_theme_without_a_twin_falls_back_to_its_appearance(
    theme_manager: ThemeManager,
) -> None:
    theme_manager.save_user_theme("mine", "Mine", "light", {}, extends="light")

    assert theme_manager.counterpart_id("mine", "qlementine") == "qlementine-light"


def test_system_mode_follows_the_chosen_engine(
    theme_manager: ThemeManager, clean_preferences, monkeypatch
) -> None:
    monkeypatch.setattr(theme_manager, "_system_appearance", lambda: "light")
    clean_preferences.set("appearance/theme", "system")

    clean_preferences.set("appearance/engine", "qss")
    theme_manager.invalidate()
    assert theme_manager.active_theme().engine == "qss"

    clean_preferences.set("appearance/engine", "qlementine")
    theme_manager.invalidate()
    active = theme_manager.active_theme()
    assert active.engine == "qlementine"
    assert active.appearance == "light"


def test_committing_a_preview_remembers_the_engine(
    theme_manager: ThemeManager, clean_preferences
) -> None:
    theme_manager.preview("nord")
    assert clean_preferences.get("appearance/engine") == "qlementine"  # not yet
    assert theme_manager.requested_engine() == "qss"

    theme_manager.commit_preview()

    assert clean_preferences.get("appearance/engine") == "qss"
    assert clean_preferences.get("appearance/theme") == "nord"


def test_cancelling_an_engine_preview_restores_the_stored_one(
    theme_manager: ThemeManager, clean_preferences
) -> None:
    clean_preferences.set("appearance/theme", "system")
    theme_manager.preview_engine("qss")
    assert theme_manager.requested_engine() == "qss"

    theme_manager.cancel_preview()

    assert theme_manager.requested_engine() == "qlementine"
    assert clean_preferences.get("appearance/engine") == "qlementine"
