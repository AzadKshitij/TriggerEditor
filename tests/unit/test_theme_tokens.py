"""Theme-token parity guard.

``base.qss`` is a ``str.format`` template: every ``{token}`` it names must
exist in every built-in theme JSON, and all built-in themes must define the
same tokens, or a theme switch or startup silently changes meaning. This test
fails fast on a missing or mismatched key instead of leaving it to a runtime
crash (docs/DESIGN_SYSTEM.md §17).

Themes use the schema ``{schema, id, name, appearance, tokens}``; the token
mapping is what ``base.qss`` is formatted against.
"""

import json
import re
from pathlib import Path

import pytest

THEMES_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "trigger_designer"
    / "resources"
    / "qt"
    / "themes"
)

# ``{name}`` placeholders, skipping the ``{{`` / ``}}`` QSS block escapes.
_TOKEN_RE = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")


def _qss_tokens() -> set[str]:
    qss = (THEMES_DIR / "base.qss").read_text(encoding="utf-8")
    return set(_TOKEN_RE.findall(qss))


def _theme_data(name: str) -> dict:
    return json.loads((THEMES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _theme_tokens(name: str) -> dict:
    data = _theme_data(name)
    if isinstance(data.get("tokens"), dict):
        return data["tokens"]
    return {
        key: value
        for key, value in data.items()
        if key not in {"schema", "id", "name", "appearance", "extends"}
    }


def _builtin_theme_names() -> list[str]:
    """Every built-in theme is a JSON file next to ``base.qss``."""
    return sorted(path.stem for path in THEMES_DIR.glob("*.json"))


def test_base_qss_uses_at_least_one_token() -> None:
    assert _qss_tokens(), (
        "base.qss parsed as having no {tokens} - regex or file changed"
    )


@pytest.mark.parametrize("theme_name", _builtin_theme_names())
def test_theme_uses_new_schema(theme_name: str) -> None:
    data = _theme_data(theme_name)
    assert data.get("id") == theme_name
    assert data.get("appearance") in {"dark", "light"}
    assert isinstance(data.get("name"), str) and data["name"]
    assert isinstance(data.get("tokens"), dict) and data["tokens"]


@pytest.mark.parametrize("theme_name", _builtin_theme_names())
def test_every_qss_token_exists_in_theme(theme_name: str) -> None:
    missing = sorted(_qss_tokens() - set(_theme_tokens(theme_name)))
    assert not missing, f"{theme_name}.json is missing keys used by base.qss: {missing}"


def test_theme_key_parity() -> None:
    reference = set(_theme_tokens("dark"))
    mismatched = {}
    for name in _builtin_theme_names():
        keys = set(_theme_tokens(name))
        if keys != reference:
            mismatched[name] = sorted(keys ^ reference)
    assert not mismatched, (
        "every built-in theme must define the same keys as dark.json; "
        f"mismatched={mismatched}"
    )


# ``#rgb``/``#rrggbb``/``#aarrggbb`` token values, the form the built-ins use.
_HEX_VALUE_RE = re.compile(
    r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$"
)


@pytest.mark.parametrize("theme_name", _builtin_theme_names())
def test_every_colour_token_is_editor_exposed(theme_name: str) -> None:
    """Every painted colour is editable, and no editor row is empty."""
    from trigger_designer.qt.theme_manager import COLOR_KEYS

    tokens = _theme_tokens(theme_name)
    painted = {
        key
        for key, value in tokens.items()
        if isinstance(value, str) and _HEX_VALUE_RE.match(value)
    }
    missing = sorted(painted - COLOR_KEYS)
    assert not missing, f"{theme_name}.json colours absent from the editor: {missing}"
    empty = sorted(COLOR_KEYS - set(tokens))
    assert not empty, f"{theme_name}.json lacks editor tokens: {empty}"
