"""Token -> Qlementine theme mapping. Pure: needs neither Qlementine nor a window."""

from __future__ import annotations

import re

import pytest

from trigger_designer.qt import qlementine_style
from trigger_designer.qt.qlementine_style import (
    CONTROL_HEIGHT,
    QlementineBackend,
    theme_dict,
)

#: Shaped like ``Theme.makeDark().toJson()``: colours in ``#rrggbbaa``.
BASE = {
    "backgroundColorMain1": "#1f2127ff",
    "primaryColor": "#5086ffff",
    "shadowColor1": "#00000066",
    "semiTransparentColor1": "#b7c9ff18",
    "animationDuration": 192,
    "borderRadius": 6,
    "checkBoxBorderRadius": 4,
    "menuItemBorderRadius": 4,
    "menuBarItemBorderRadius": 4,
    "spacing": 8,
    "fontSize": 12,
}

TOKENS = {
    "background_primary": "#14171b",
    "background_secondary": "#191e22",
    "background_tertiary": "#1e242a",
    "background_hover": "#22282e",
    "background_pressed": "#2c333a",
    "background_disabled": "#14171b",
    "editor_background": "#101418",
    "canvas_background": "#0e1115",
    "button_bg": "#191e21",
    "text_primary": "#f5f7f9",
    "text_secondary": "#c6cdd5",
    "text_inactive": "#919ba6",
    "text_disabled": "#5c6672",
    "accent_primary": "#5680c2",
    "accent_secondary": "#6a96d7",
    "accent_tertiary": "#3a76ba",
    "accent_disabled": "#3a76ba",
    "text_on_accent": "#ffffff",
    "success": "#48a878",
    "warning": "#d9a441",
    "danger": "#e0686c",
    "info": "#5ba8d6",
    "border_default": "#2f363d",
    "border_strong": "#3e4750",
    "border_subtle": "#242a30",
    "border_radius": "4px",
    "spacing_medium": "4px",
}

_RRGGBBAA = re.compile(r"^#[0-9a-f]{8}$")


def _build(tokens=None, **kwargs):
    return theme_dict(
        TOKENS if tokens is None else tokens, base=BASE, **kwargs, dark=True
    )


def test_colours_use_qlementines_rrggbbaa_syntax() -> None:
    out = _build()
    colours = {k: v for k, v in out.items() if isinstance(v, str) and k != "meta"}
    assert colours
    assert all(_RRGGBBAA.match(v) for v in colours.values()), colours


def test_surfaces_text_and_accent_map_from_tokens() -> None:
    out = _build()
    # Inputs sit on the inset surface, the window on the base one.
    assert out["backgroundColorMain1"] == "#101418ff"
    assert out["backgroundColorMain2"] == "#14171bff"
    assert out["backgroundColorMain3"] == "#191e22ff"
    assert out["backgroundColorMain4"] == "#1e242aff"
    assert out["backgroundColorWorkspace"] == "#0e1115ff"
    assert out["secondaryColor"] == "#f5f7f9ff"
    assert out["secondaryAlternativeColor"] == "#919ba6ff"
    assert out["primaryColor"] == "#5680c2ff"
    assert out["primaryColorHovered"] == "#6a96d7ff"
    assert out["primaryColorPressed"] == "#3a76baff"
    assert out["primaryColorForeground"] == "#ffffffff"
    assert out["neutralColor"] == "#191e21ff"
    assert out["neutralColorHovered"] == "#22282eff"
    assert out["neutralColorPressed"] == "#2c333aff"
    assert out["borderColor"] == "#2f363dff"
    assert out["borderColorHovered"] == "#3e4750ff"
    assert out["statusColorError"] == "#e0686cff"


def test_focus_ring_is_the_accent_made_translucent() -> None:
    focus = _build()["focusColor"]
    assert focus.startswith("#5680c2")
    assert focus.endswith("66")


def test_keys_the_tokens_do_not_cover_keep_qlementines_values() -> None:
    out = _build()
    for key in ("shadowColor1", "semiTransparentColor1", "animationDuration"):
        assert out[key] == BASE[key]


def test_a_missing_accent_leaves_the_base_primary_alone() -> None:
    tokens = {k: v for k, v in TOKENS.items() if not k.startswith("accent_")}
    assert _build(tokens)["primaryColor"] == BASE["primaryColor"]


def test_invalid_colour_tokens_are_skipped_not_fatal() -> None:
    out = _build({**TOKENS, "text_primary": "not-a-colour"})
    # Nothing is written, so the base's value (here: none) is what remains.
    assert "secondaryColor" not in out
    assert out["primaryColor"] == "#5680c2ff"


def test_metrics_follow_the_design_tokens() -> None:
    out = _build(font_px=14, scale=1.5)
    assert out["borderRadius"] == 4.0
    assert out["spacing"] == 4
    assert out["controlHeightLarge"] == round(CONTROL_HEIGHT * 1.5)
    assert out["tabBarPaddingTop"] == 0
    assert out["fontSize"] == 14
    assert out["fontSizeMonospace"] == 14
    assert out["fontSizeS1"] == 12
    assert out["useSystemFonts"] is True


def test_controls_never_shrink_below_the_design_height() -> None:
    assert _build(scale=0.5)["controlHeightLarge"] == CONTROL_HEIGHT


def test_inner_radii_never_exceed_the_outer_one() -> None:
    out = _build({**TOKENS, "border_radius": "2px"})
    assert out["checkBoxBorderRadius"] <= out["borderRadius"]
    assert out["menuItemBorderRadius"] <= out["borderRadius"]
    assert out["menuBarItemBorderRadius"] <= out["borderRadius"]


def test_status_foreground_is_legible_on_the_status_colour() -> None:
    dark_text = _build({**TOKENS, "warning": "#ffe066"})["statusColorForeground"]
    light_text = _build({**TOKENS, "warning": "#7a3b00"})["statusColorForeground"]
    assert dark_text.startswith("#10151a")
    assert light_text.startswith("#ffffff")


def test_the_input_mapping_is_not_mutated() -> None:
    before = dict(TOKENS), dict(BASE)
    _build()
    assert (TOKENS, BASE) == before


def test_the_tab_bar_band_is_the_window_colour_on_dark_and_light_themes() -> None:
    """Tab bars blend in; ``tab_indicator`` marks the active tab instead."""
    light = {**TOKENS, "background_primary": "#f3f3f3", "text_primary": "#202124"}
    for out in (_build(), theme_dict(light, dark=False, base=BASE)):
        assert out["backgroundColorTabBar"] == out["backgroundColorMain2"]


class TestBackendWithoutTheLibrary:
    @pytest.fixture(autouse=True)
    def _no_qlementine(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(qlementine_style, "_q", None)

    def test_it_reports_itself_unavailable(self) -> None:
        backend = QlementineBackend()
        assert not backend.available
        assert not backend.active

    def test_install_and_uninstall_are_harmless_no_ops(self) -> None:
        backend = QlementineBackend()
        assert backend.install(None, TOKENS, dark=True, font_px=12, scale=1.0) is False
        assert backend.uninstall(None) is False
