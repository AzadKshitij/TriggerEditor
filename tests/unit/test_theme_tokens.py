"""Theme-token parity guard.

``base.qss`` is a ``str.format`` template: every ``{token}`` it names must
exist in both theme JSONs or ``ResourceManager.load_theme`` raises at
startup. This test fails fast on a missing or mismatched key instead of
leaving it to a runtime crash (docs/DESIGN_SYSTEM.md §17).
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


def _tokens() -> set[str]:
    qss = (THEMES_DIR / "base.qss").read_text(encoding="utf-8")
    return set(_TOKEN_RE.findall(qss))


def _theme(name: str) -> dict:
    return json.loads((THEMES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def test_base_qss_uses_at_least_one_token() -> None:
    assert _tokens(), "base.qss parsed as having no {tokens} - regex or file changed"


@pytest.mark.parametrize("theme_name", ["dark", "light"])
def test_every_qss_token_exists_in_theme(theme_name: str) -> None:
    missing = sorted(_tokens() - set(_theme(theme_name)))
    assert not missing, f"{theme_name}.json is missing keys used by base.qss: {missing}"


def test_theme_key_parity() -> None:
    dark = set(_theme("dark"))
    light = set(_theme("light"))
    assert dark == light, (
        "dark.json and light.json must define the same keys; "
        f"dark-only={sorted(dark - light)} light-only={sorted(light - dark)}"
    )
