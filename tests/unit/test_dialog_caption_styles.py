"""Win32 pieces behind FramelessDialog and the native title theming.

Pure functions, so they are checked on every platform.
"""

from qtpy.QtCore import QRect

from trigger_designer.qt.helpers.win_caption import (
    FRAME_STYLES,
    HTCLIENT,
    WS_CAPTION,
    WS_MAXIMIZEBOX,
    WS_MINIMIZEBOX,
    WS_SYSMENU,
    WS_THICKFRAME,
    CaptionRegions,
    FrameMetrics,
    colorref,
    dialog_frame_styles,
    hit_test,
)


def test_dialog_styles_never_carry_a_min_or_max_box() -> None:
    for resizable in (True, False):
        styles = dialog_frame_styles(resizable)
        assert not styles & WS_MAXIMIZEBOX
        assert not styles & WS_MINIMIZEBOX
        assert styles & WS_CAPTION
        assert styles & WS_SYSMENU


def test_only_a_resizable_dialog_gets_the_sizing_border() -> None:
    assert dialog_frame_styles(True) & WS_THICKFRAME
    assert not dialog_frame_styles(False) & WS_THICKFRAME


def test_main_window_styles_are_unchanged() -> None:
    assert FRAME_STYLES == (
        WS_THICKFRAME | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
    )


def test_colorref_is_blue_green_red() -> None:
    assert colorref(0x11, 0x22, 0x33) == 0x332211
    assert colorref(255, 255, 255) == 0xFFFFFF


def test_fixed_size_dialog_has_no_live_border() -> None:
    regions = CaptionRegions(
        row=QRect(0, 0, 400, 32), menu=QRect(356, 0, 44, 32), icon=QRect()
    )
    code = hit_test(
        (1, 100),
        dpr=1.0,
        frame=FrameMetrics(8, 8),
        regions=regions,
        size=(400.0, 300.0),
        resizable=False,
    )
    assert code == HTCLIENT
