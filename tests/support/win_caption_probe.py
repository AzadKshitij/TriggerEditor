#!/usr/bin/env python3
"""Probe the Win32 caption on a real window: styles, hit-test codes, geometry.

The suite runs under the offscreen plugin, where no widget has an HWND and no
message ever reaches the caption layer, so the native half is exercised here on
the ``windows`` plugin instead: the probe opens a real window, reads its frame
styles, asks ``WM_NCHITTEST`` about every region and prints one JSON document.

A caption click is deliberately not replayed. ``DefWindowProc`` enters its
push-button loop on the way into ``WM_NCLBUTTONDOWN`` and only leaves it when
the button comes up from *real* hardware input, so a synthetic click wedges the
probe in Qt's event loop with no way out. What Windows does with the click
follows from the hit-test answers the probe reports; check the click itself by
hand, along with the native behaviour only the eye can judge - snap, the Snap
Layouts flyout and the DWM shadow. The window is real and briefly maximised,
which is the point:

    uv run --project . python tests/support/win_caption_probe.py
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

GWL_STYLE = -16
WS_THICKFRAME = 0x00040000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000

WM_NCHITTEST = 0x0084

_MARKER = "PROBE-JSON "

_user32 = ctypes.windll.user32
# Spelled out: ctypes truncates an HWND to 32 bits without them.
_user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
_user32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
_user32.SendMessageW.restype = ctypes.c_ssize_t
_user32.SendMessageW.argtypes = [
    wt.HWND,
    ctypes.c_uint,
    ctypes.c_size_t,
    ctypes.c_ssize_t,
]
_user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
_user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
_user32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
_user32.IsZoomed.restype = wt.BOOL
_user32.IsZoomed.argtypes = [wt.HWND]


def _send(hwnd: int, message: int, wparam: int = 0, lparam: int = 0) -> int:
    return int(_user32.SendMessageW(hwnd, message, wparam, lparam))


def _lparam(x: int, y: int) -> int:
    """Pack a screen point the way ``WM_NCHITTEST`` carries it."""
    return (y & 0xFFFF) << 16 | (x & 0xFFFF)


def _client_origin(hwnd: int) -> tuple[int, int]:
    point = wt.POINT(0, 0)
    _user32.ClientToScreen(hwnd, ctypes.byref(point))
    return (point.x, point.y)


def _client_size(hwnd: int) -> tuple[int, int]:
    rect = wt.RECT()
    _user32.GetClientRect(hwnd, ctypes.byref(rect))
    return (rect.right, rect.bottom)


def _window_size(hwnd: int) -> tuple[int, int]:
    rect = wt.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return (rect.right - rect.left, rect.bottom - rect.top)


def _settle(app, seconds: float = 0.3) -> None:
    """Let Windows finish a transition before looking at the result."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")

    from qtpy.QtWidgets import QApplication

    from trigger_designer.qt.main_window import TriggerWindow

    app = QApplication.instance() or QApplication([])
    window = TriggerWindow()
    chrome = window.window_chrome
    # The app restores its saved geometry, usually maximised, when the window
    # is shown; asking for a normal window *before* that is the only way it
    # sticks, and the frame sizes below only mean anything on a normal window.
    window.showNormal()
    window.show()
    _settle(app)

    hwnd = int(window.winId())
    style = int(_user32.GetWindowLongPtrW(hwnd, GWL_STYLE))
    report: dict[str, object] = {
        "style": {
            "thickframe": bool(style & WS_THICKFRAME),
            "caption": bool(style & WS_CAPTION),
            "sysmenu": bool(style & WS_SYSMENU),
            "minimizebox": bool(style & WS_MINIMIZEBOX),
            "maximizebox": bool(style & WS_MAXIMIZEBOX),
        },
        "client_equals_window": _client_size(hwnd) == _window_size(hwnd),
        "window_size": _window_size(hwnd),
        "client_size": _client_size(hwnd),
    }

    dpr = float(window.devicePixelRatioF() or 1.0)
    report["dpr"] = dpr
    regions = chrome.caption_regions()
    row = regions.row
    icon = regions.icon
    buttons = regions.buttons

    def hit(x: float, y: float) -> int:
        origin_x, origin_y = _client_origin(hwnd)
        return _send(
            hwnd,
            WM_NCHITTEST,
            0,
            _lparam(origin_x + round(x * dpr), origin_y + round(y * dpr)),
        )

    below_row = row.height() + 40
    report["regions"] = {
        "row": [row.x(), row.y(), row.width(), row.height()],
        "menu": [regions.menu.x(), regions.menu.y(), regions.menu.width()],
        "icon": [icon.x(), icon.width()],
        "buttons": {name: rect.x() for name, rect in buttons.items()},
    }
    report["hit"] = {
        "caption": hit(row.width() / 2, 16),
        "menu": hit(regions.menu.center().x(), 16),
        "icon": hit(icon.center().x(), 16) if icon.width() else None,
        "minimize": hit(buttons["minimize"].center().x(), 16),
        "maximize": hit(buttons["maximize"].center().x(), 16),
        "close": hit(buttons["close"].center().x(), 16),
        "left": hit(2.0, window.height() / 2),
        "bottom_right": hit(row.width() - 2.0, window.height() - 2.0),
        "below": hit(row.width() / 2, below_row),
        # A caption button owns its pixels, top edge included: the resize ring
        # yields to it, and that answer is what opens the Snap Layouts flyout.
        "button_top": {
            name: hit(rect.center().x(), 2.0) for name, rect in buttons.items()
        },
    }

    # Maximised, the client area has to land exactly on the work area: the
    # native frame is invisible, so nothing else may be inset either. The
    # client rect is physical and Qt reports the work area in logical pixels,
    # and "zoomed" is a Windows-native zoom - Qt fills the work area itself,
    # so it stays false for a maximize Qt performed.
    window.showMaximized()
    _settle(app)
    origin_x, origin_y = _client_origin(hwnd)
    client_w, client_h = _client_size(hwnd)
    work_area = window.screen().availableGeometry()
    report["maximized"] = {
        "zoomed": bool(_user32.IsZoomed(hwnd)),
        "client": [origin_x, origin_y, client_w, client_h],
        "work_area": [
            round(work_area.x() * dpr),
            round(work_area.y() * dpr),
            round(work_area.width() * dpr),
            round(work_area.height() * dpr),
        ],
    }

    print(_MARKER + json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
