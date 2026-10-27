"""The application font size preference scales text without touching layout tokens."""

from trigger_designer.qt.preferences import get_preferences


def test_default_font_size_leaves_the_stylesheet_alone(theme_manager) -> None:
    theme_manager._base_font_pt = 9.0
    assert theme_manager.requested_font_size() == 0
    assert theme_manager.font_scale() == 1.0
    assert "font-size: 10px" in theme_manager.stylesheet_for("dark")


def test_chosen_font_size_scales_the_px_literals(theme_manager) -> None:
    theme_manager._base_font_pt = 9.0
    get_preferences().set("appearance/font_size", 18)

    assert theme_manager.font_scale() == 2.0
    qss = theme_manager.stylesheet_for("dark")
    assert "font-size: 20px" in qss  # was 10px
    assert "font-size: 10px" not in qss


def test_scaled_font_sizes_never_drop_below_a_readable_floor(theme_manager) -> None:
    theme_manager._base_font_pt = 20.0
    get_preferences().set("appearance/font_size", 8)

    qss = theme_manager.stylesheet_for("dark")
    assert "font-size: 7px" in qss  # 9px * 0.4 would be 4px


def test_invalid_font_size_falls_back_to_default(theme_manager) -> None:
    get_preferences().set("appearance/font_size", "huge")
    assert theme_manager.requested_font_size() == 0
