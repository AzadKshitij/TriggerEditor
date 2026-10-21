#!/usr/bin/env python3
"""The Win32 caption hit test: pure geometry, no Win32 needed.

Windows decides what every pixel of the chrome row does from ``WM_NCHITTEST``.
The resize border has to stay grabbable, the caption buttons must be reported
as buttons (that answer is what opens the Snap Layouts flyout, not the glyph),
a button owns its pixels even where the ring would overlap it, the menus must
stay client area so they keep their clicks, and the rest of the row must
behave like a caption. All of that is :func:`hit_test`, which takes
physical pixels in and returns a hit-test code, so it is checked here on every
platform.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from qtpy.QtCore import QRect

from trigger_designer.qt.helpers.win_caption import (
    HTBOTTOM,
    HTBOTTOMLEFT,
    HTBOTTOMRIGHT,
    HTCAPTION,
    HTCLIENT,
    HTCLOSE,
    HTLEFT,
    HTMAXBUTTON,
    HTMINBUTTON,
    HTRIGHT,
    HTSYSMENU,
    HTTOP,
    HTTOPLEFT,
    CaptionRegions,
    FrameMetrics,
    caption_button_for_code,
    hit_test,
    maximized_insets,
)

#: 125% scaling: 9 physical pixels of border are 7.2 logical pixels.
DPR = 1.25
FRAME = FrameMetrics(9, 9)
SIZE = (1200.0, 800.0)


def _regions(*, icon: bool = True) -> CaptionRegions:
    return CaptionRegions(
        row=QRect(0, 0, 1200, 32),
        menu=QRect(40, 0, 240, 32),
        icon=QRect(8, 0, 24, 32) if icon else QRect(),
        buttons={
            "minimize": QRect(1068, 0, 44, 32),
            "maximize": QRect(1112, 0, 44, 32),
            "close": QRect(1156, 0, 44, 32),
        },
    )


def _hit(
    x: float,
    y: float,
    *,
    icon: bool = True,
    regions: CaptionRegions | None = None,
    size: tuple[float, float] = SIZE,
    resizable: bool = True,
) -> int:
    """Hit-test a *logical* point the way the window would report it."""
    return hit_test(
        (round(x * DPR), round(y * DPR)),
        dpr=DPR,
        frame=FRAME,
        regions=regions if regions is not None else _regions(icon=icon),
        size=size,
        resizable=resizable,
    )


def test_the_drag_area_is_a_caption():
    assert _hit(600, 16) == HTCAPTION


def test_each_caption_button_reports_itself():
    assert _hit(1090, 16) == HTMINBUTTON
    assert _hit(1134, 16) == HTMAXBUTTON
    assert _hit(1178, 16) == HTCLOSE


def test_the_icon_slot_opens_the_system_menu():
    assert _hit(20, 16) == HTSYSMENU


def test_without_an_icon_the_slot_drags_instead():
    assert _hit(20, 16, icon=False) == HTCAPTION


def test_the_menus_keep_their_clicks():
    assert _hit(150, 16) == HTCLIENT


def test_below_the_row_is_client_area():
    assert _hit(600, 200) == HTCLIENT


def test_the_frame_ring_resizes():
    assert _hit(2, 400) == HTLEFT
    assert _hit(1198, 400) == HTRIGHT
    assert _hit(600, 2) == HTTOP
    assert _hit(600, 798) == HTBOTTOM


def test_corners_resize_diagonally():
    # The top-right corner is the Close button's, handled below.
    assert _hit(2, 2) == HTTOPLEFT
    assert _hit(2, 798) == HTBOTTOMLEFT
    assert _hit(1198, 798) == HTBOTTOMRIGHT


def test_a_caption_button_owns_its_pixels():
    # Windows opens Snap Layouts from any pixel of Maximize and gives Close
    # the screen corner, so the resize ring yields to the buttons. Hovering or
    # clicking the top of a button must reach the button, not resize.
    assert _hit(1090, 2) == HTMINBUTTON
    assert _hit(1134, 2) == HTMAXBUTTON
    assert _hit(1178, 2) == HTCLOSE
    assert _hit(1198, 2) == HTCLOSE
    # Left of the buttons the top edge is still a resize border.
    assert _hit(600, 2) == HTTOP


def test_the_left_group_keeps_its_top_pixels():
    # Same rule the Qt edge filter applies to the menu bar: a press near the
    # top of a menu opens it instead of starting a resize.
    assert _hit(150, 2) == HTCLIENT
    assert _hit(20, 2) == HTSYSMENU


def test_the_ring_scales_with_the_monitor():
    # 9 physical pixels are 7.2 logical ones: inside is border, outside is not.
    def _physical(x: int) -> int:
        return hit_test(
            (x, 20),  # 16 logical pixels down: inside the row
            dpr=DPR,
            frame=FRAME,
            regions=_regions(),
            size=SIZE,
        )

    assert _physical(8) == HTLEFT
    assert _physical(44) == HTCAPTION


def test_fullscreen_has_neither_caption_nor_border():
    assert _hit(600, 16, resizable=False) == HTCLIENT
    assert _hit(2, 400, resizable=False) == HTCLIENT


def test_a_window_thinner_than_its_border_is_all_client():
    # Squeezed to 10x10 logical pixels the four borders overlap; there is no
    # ring left to report, and it must not raise a KeyError either.
    assert _hit(5, 5, size=(10.0, 10.0)) == HTCLIENT


def test_caption_button_for_code_names_the_three_buttons():
    assert caption_button_for_code(HTMINBUTTON) == "minimize"
    assert caption_button_for_code(HTMAXBUTTON) == "maximize"
    assert caption_button_for_code(HTCLOSE) == "close"


def test_caption_button_for_code_ignores_everything_else():
    assert caption_button_for_code(None) is None
    assert caption_button_for_code(HTCAPTION) is None
    assert caption_button_for_code(HTCLIENT) is None


def test_maximized_insets_undo_the_window_growth():
    assert maximized_insets(True, FRAME) == (9, 9, 9, 9)
    assert maximized_insets(False, FRAME) == (0, 0, 0, 0)
