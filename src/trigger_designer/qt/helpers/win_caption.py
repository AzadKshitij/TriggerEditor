"""Native Windows caption for the frameless main window.

``window_chrome`` draws its own caption, so Windows sees a borderless popup:
it offers no snap previews, no Snap Layouts flyout over the maximize button,
no DWM shadow and no rounded corners, and Qt's ``startSystemMove`` runs the
keyboard move loop instead of the mouse one. This module hands the window a
real frame back and answers the non-client messages that decide what every
pixel of the row does:

* ``WM_NCCALCSIZE`` claims the whole window as client area, so Windows keeps
  the frame styles without drawing a caption of its own.
* ``WM_NCHITTEST`` reports the resize border, the caption buttons and the drag
  area. Snap, the Snap Layouts flyout, double-click to maximize,
  drag-from-maximized, the system menu on right-click and the native edge
  cursors all follow from those answers.

The geometry half - :func:`hit_test`, :class:`FrameMetrics`,
:func:`maximized_insets` - is pure and unit-tested off Windows. Only
:class:`WinCaption` talks to Win32.

Traps, all reproduced on Qt 6.8.1 / PyQt6 6.8.0:

* A ``nativeEvent`` override must not call the base implementation: PyQt6
  re-enters the message it was handed and aborts the process (0xC000041D).
  Unhandled messages are answered with ``(False, 0)``, which is what the base
  class returns anyway.
* ``WM_NCCALCSIZE`` carries an ``NCCALCSIZE_PARAMS`` while ``wParam`` is true,
  not a bare ``RECT``.
* ``WM_NCHITTEST`` coordinates are physical screen pixels; the row's widgets
  are in logical client coordinates, so every region is converted first.
* A caption button's hover and pressed look cannot come from QSS ``:hover``:
  Qt reads that from a real mouse move, and Windows owns these pixels now. The
  row paints them from the ``nativeHover`` / ``nativePress`` properties
  base.qss restates, never from ``setDown``.
* ``WM_NCLBUTTONDOWN`` must not reach ``DefWindowProc`` for a caption button.
  It answers by running the system's own push-button loop, which paints a
  classic beveled caption button - light face, dark glyph, at *its* button
  positions rather than ours - over the row on top of the Qt widgets, and
  leaves it there: the row never repaints that spot, so the pressed glyph stays
  until something else invalidates it. Answers to ``WM_NCHITTEST`` alone do not
  draw anything, so the look stays flat as long as the press is claimed here.
* ``WM_NCMOUSELEAVE`` cannot be used to notice the cursor leaving the row:
  the frame is claimed whole by ``WM_NCCALCSIZE``, so there is no non-client
  area to leave and the message never arrives (``TrackMouseEvent`` does not
  help). While a caption button is lit, the chrome asks where the pointer is
  instead - see :meth:`WinCaption.pointer_over_buttons`.
* Qt only forwards these messages on the ``windows`` platform plugin; the
  offscreen plugin the tests use has no HWND, hence
  :func:`native_caption_supported`.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from qtpy.QtCore import QRect
from qtpy.QtGui import QGuiApplication

if TYPE_CHECKING:  # pragma: no cover - typing only
    from trigger_designer.qt.widgets.common.window_chrome import WindowChrome

# -- window styles, messages and hit-test codes -------------------------------

GWL_STYLE = -16
WS_THICKFRAME = 0x00040000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000

#: What a caption needs to be snap-capable and resizable.
FRAME_STYLES = WS_THICKFRAME | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
#: Re-read the frame without moving, resizing, restacking or activating.
SWP_FRAME_ONLY = (
    SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
)

WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
WM_NCMOUSEMOVE = 0x00A0
WM_NCLBUTTONDOWN = 0x00A1
WM_NCLBUTTONUP = 0x00A2
WM_NCMOUSELEAVE = 0x02A3

HTCLIENT = 1
HTCAPTION = 2
HTSYSMENU = 3
HTMINBUTTON = 8
HTMAXBUTTON = 9
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17
HTCLOSE = 20

SM_CXSIZEFRAME = 32
SM_CYSIZEFRAME = 33
SM_CXPADDEDBORDER = 92

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2

#: Hit-test code -> the caption button it identifies. Windows opens the Snap
#: Layouts flyout from ``HTMAXBUTTON`` alone, however the button is drawn.
CAPTION_BUTTONS: dict[int, str] = {
    HTMINBUTTON: "minimize",
    HTMAXBUTTON: "maximize",
    HTCLOSE: "close",
}

_BUTTON_CODES: dict[str, int] = {name: code for code, name in CAPTION_BUTTONS.items()}

#: Messages that only keep the row's hover and pressed look in step.
NC_MOUSE_MESSAGES = (WM_NCMOUSEMOVE, WM_NCLBUTTONDOWN, WM_NCLBUTTONUP, WM_NCMOUSELEAVE)

#: Messages Windows presses a caption button with, and which the caption
#: answers itself: see :meth:`WinCaption._caption_click`.
NC_BUTTON_MESSAGES = (WM_NCLBUTTONDOWN, WM_NCLBUTTONUP)

#: Edge bits of a point on two borders at once, mapped to hit-test codes.
_LEFT, _RIGHT, _TOP, _BOTTOM = 1, 2, 4, 8
_EDGE_CODES: dict[int, int] = {
    _LEFT: HTLEFT,
    _RIGHT: HTRIGHT,
    _TOP: HTTOP,
    _BOTTOM: HTBOTTOM,
    _LEFT | _TOP: HTTOPLEFT,
    _RIGHT | _TOP: HTTOPRIGHT,
    _LEFT | _BOTTOM: HTBOTTOMLEFT,
    _RIGHT | _BOTTOM: HTBOTTOMRIGHT,
}


class NCCALCSIZE_PARAMS(ctypes.Structure):
    """``WM_NCCALCSIZE`` with ``wParam`` set: three rects and a window pos.

    Only ``rgrc[0]`` is read here; ``lppos`` is declared so the struct keeps
    the layout Windows hands over.
    """

    _fields_ = [
        ("rgrc", wintypes.RECT * 3),
        ("lppos", ctypes.c_void_p),
    ]


# -- pure geometry ------------------------------------------------------------


@dataclass(frozen=True)
class FrameMetrics:
    """Thickness of the invisible native frame, in physical pixels."""

    x: int
    y: int


@dataclass(frozen=True)
class CaptionRegions:
    """Logical, client-relative rectangles of the chrome row."""

    row: QRect
    menu: QRect
    icon: QRect
    buttons: dict[str, QRect] = field(default_factory=dict)


def native_caption_supported() -> bool:
    """Whether the Win32 caption layer can run here.

    ``sys.platform`` alone is not enough: the offscreen plugin the test suite
    uses also reports ``win32``, and its widgets have no HWND behind them.
    """
    if sys.platform != "win32":
        return False
    application = QGuiApplication.instance()
    return application is not None and application.platformName() == "windows"


def caption_button_for_code(code: int | None) -> str | None:
    """Which caption button an ``WM_NC*`` hit-test code points at."""
    if code is None:
        return None
    return CAPTION_BUTTONS.get(code)


def maximized_insets(zoomed: bool, frame: FrameMetrics) -> tuple[int, int, int, int]:
    """Left/top/right/bottom to take off a maximized window rect.

    Windows enlarges a maximized window by its frame on every side so that the
    *client* area lands on the monitor's work area. A window that reports no
    non-client area has to undo that itself, or the title row sits off-screen.
    """
    if not zoomed:
        return (0, 0, 0, 0)
    return (frame.x, frame.y, frame.x, frame.y)


def hit_test(
    point: tuple[int, int],
    *,
    dpr: float,
    frame: FrameMetrics,
    regions: CaptionRegions,
    size: tuple[float, float],
    resizable: bool = True,
) -> int:
    """The hit-test code Windows should hear for ``point``.

    ``point`` is a physical client coordinate, as ``WM_NCHITTEST`` carries it;
    ``frame`` is measured in physical pixels too, and is converted here so a
    scaled monitor cannot move the resize border or the buttons.

    A caption button owns its pixels outright - the ring yields to it, the way
    Windows gives Close the screen corner - while the icon slot and the menus
    own their top pixels, so a press near the top of a menu opens it instead
    of resizing.
    """
    if not resizable:
        return HTCLIENT

    x = point[0] / dpr
    y = point[1] / dpr
    width, height = size
    if not (0.0 <= x < width and 0.0 <= y < height):
        return HTCLIENT

    # A caption button owns its pixels outright, the ring included: hovering
    # the top of Maximize is what opens the Snap Layouts flyout, and Windows
    # gives Close the screen corner. The ring yields to them.
    for name, button in regions.buttons.items():
        if _contains(button, x, y):
            return _BUTTON_CODES[name]

    # The icon slot and the menus keep their own top pixels, the way the Qt
    # edge filter already cedes them: a press near the top of a menu opens it
    # instead of starting a resize. The top edge stays grabbable left of, right
    # of and behind them.
    owns_top = (regions.icon.width() > 0 and _contains(regions.icon, x, y)) or (
        regions.menu.width() > 0 and _contains(regions.menu, x, y)
    )

    border_x = frame.x / dpr
    border_y = frame.y / dpr
    edges = 0
    if x < border_x:
        edges |= _LEFT
    if x >= width - border_x:
        edges |= _RIGHT
    if y < border_y and not owns_top:
        edges |= _TOP
    if y >= height - border_y:
        edges |= _BOTTOM
    if edges:
        # A window squeezed thinner than its own border has no ring to give.
        return _EDGE_CODES.get(edges, HTCLIENT)

    if regions.icon.width() > 0 and _contains(regions.icon, x, y):
        return HTSYSMENU
    if regions.menu.width() > 0 and _contains(regions.menu, x, y):
        return HTCLIENT
    if _contains(regions.row, x, y):
        return HTCAPTION
    return HTCLIENT


def _contains(rect: QRect, x: float, y: float) -> bool:
    """Half-open containment that tolerates the float coordinates above."""
    return (
        rect.left() <= x < rect.left() + rect.width()
        and rect.top() <= y < rect.top() + rect.height()
    )


# -- Win32 --------------------------------------------------------------------


class _Api:
    """The user32/dwmapi entry points used here, with argument types declared.

    ctypes defaults every argument to a 32-bit int, which truncates an HWND on
    64-bit Windows, so the types are spelled out rather than left implicit.
    """

    def __init__(self) -> None:
        self.user32 = ctypes.windll.user32
        self.dwmapi = ctypes.windll.dwmapi

        user = self.user32
        user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        user.SetWindowLongPtrW.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_ssize_t,
        ]
        user.SetWindowPos.restype = wintypes.BOOL
        user.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        user.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        user.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        user.IsZoomed.restype = wintypes.BOOL
        user.IsZoomed.argtypes = [wintypes.HWND]
        user.GetSystemMetrics.restype = ctypes.c_int
        user.GetSystemMetrics.argtypes = [ctypes.c_int]

        # Windows 10 1607+ only; older builds fall back to the system metrics.
        self._for_dpi = getattr(user, "GetSystemMetricsForDpi", None)
        if self._for_dpi is not None:
            self._for_dpi.restype = ctypes.c_int
            self._for_dpi.argtypes = [ctypes.c_int, ctypes.c_uint]
        self._dpi_for_window = getattr(user, "GetDpiForWindow", None)
        if self._dpi_for_window is not None:
            self._dpi_for_window.restype = ctypes.c_uint
            self._dpi_for_window.argtypes = [wintypes.HWND]

        self.dwmapi.DwmSetWindowAttribute.argtypes = [
            wintypes.HWND,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
        ]
        self.dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long
        self.dwm_available = True

    def window_dpi(self, hwnd: int) -> int:
        if self._dpi_for_window is None:
            return 96
        return int(self._dpi_for_window(hwnd)) or 96

    def system_metric(self, index: int, dpi: int) -> int:
        if self._for_dpi is not None:
            try:
                return int(self._for_dpi(index, dpi))
            except OSError:  # pragma: no cover - older Windows
                pass
        return int(self.user32.GetSystemMetrics(index))

    def set_dwm_attribute(self, hwnd: int, attribute: int, value: int) -> None:
        if not self.dwm_available:
            return
        try:
            payload = ctypes.c_int(value)
            self.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(payload), ctypes.sizeof(payload)
            )
        except OSError:  # pragma: no cover - dwmapi missing (Wine)
            self.dwm_available = False


_API: _Api | None = None


def _api() -> _Api:
    global _API
    if _API is None:
        _API = _Api()
    return _API


class WinCaption:
    """The Win32 half of the window chrome: frame styles and NC messages."""

    def __init__(self, chrome: WindowChrome) -> None:
        self._chrome = chrome
        self._hwnd = 0
        self._dark: bool | None = None

    # -- setup ----------------------------------------------------------------

    def attach(self) -> None:
        """Give the window its frame, once it has an HWND.

        Called again when Qt recreates the window: changing window flags
        throws the HWND away and the new one starts as a plain popup.
        """
        if not native_caption_supported():
            return
        hwnd = int(self._chrome.window().winId())
        if hwnd == 0 or hwnd == self._hwnd:
            return
        self._hwnd = hwnd
        api = _api()
        style = int(api.user32.GetWindowLongPtrW(hwnd, GWL_STYLE))
        api.user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style | FRAME_STYLES)
        api.user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_FRAME_ONLY)
        self._apply_dwm()

    def apply_theme(self, dark: bool) -> None:
        """Match the native shadow and system menu to the app theme."""
        self._dark = dark
        self._apply_dwm()

    def _apply_dwm(self) -> None:
        if self._hwnd == 0:
            return
        api = _api()
        # Windows 11 rounds framed windows; harmless E_INVALIDARG on 10.
        api.set_dwm_attribute(self._hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)
        if self._dark is not None:
            api.set_dwm_attribute(
                self._hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if self._dark else 0
            )

    # -- messages -------------------------------------------------------------

    def native_event(self, event_type: object, message: object) -> tuple[bool, int]:
        """Answer one native message as ``(handled, result)`` for Qt."""
        if self._hwnd == 0:
            return (False, 0)
        try:
            if bytes(event_type) != b"windows_generic_MSG":
                return (False, 0)
            native = wintypes.MSG.from_address(int(message))
        except TypeError, ValueError:  # pragma: no cover - not a real message
            return (False, 0)
        if int(native.hWnd) != self._hwnd:
            return (False, 0)

        if native.message == WM_NCCALCSIZE:
            return self._nonclient_size(native)
        if native.message == WM_NCHITTEST:
            return self._hit_test(native)
        if native.message in NC_BUTTON_MESSAGES and self._caption_click(native):
            return (True, 0)
        if native.message in NC_MOUSE_MESSAGES:
            self._native_mouse(native)
        return (False, 0)

    def _nonclient_size(self, native: wintypes.MSG) -> tuple[bool, int]:
        """Keep the frame styles, claim every pixel as client area."""
        if native.wParam:
            params = NCCALCSIZE_PARAMS.from_address(native.lParam)
            rect = params.rgrc[0]
            left, top, right, bottom = maximized_insets(
                bool(_api().user32.IsZoomed(self._hwnd)), self.frame_metrics()
            )
            rect.left += left
            rect.top += top
            rect.right -= right
            rect.bottom -= bottom
            params.rgrc[0] = rect
        return (True, 0)

    def _hit_test(self, native: wintypes.MSG) -> tuple[bool, int]:
        """Tell Windows what the pixel under the cursor is."""
        screen_x = ctypes.c_short(native.lParam & 0xFFFF).value
        screen_y = ctypes.c_short((native.lParam >> 16) & 0xFFFF).value
        api = _api()
        origin = wintypes.POINT(0, 0)
        api.user32.ClientToScreen(self._hwnd, ctypes.byref(origin))
        client = wintypes.RECT()
        api.user32.GetClientRect(self._hwnd, ctypes.byref(client))
        window = self._chrome.window()
        dpr = float(window.devicePixelRatioF() or 1.0)
        return (
            True,
            hit_test(
                (screen_x - origin.x, screen_y - origin.y),
                dpr=dpr,
                frame=self.frame_metrics(),
                regions=self._chrome.caption_regions(),
                size=(client.right / dpr, client.bottom / dpr),
                resizable=not window.isFullScreen(),
            ),
        )

    def _native_mouse(self, native: wintypes.MSG) -> None:
        """Keep the row's look while Windows owns the clicks.

        A hover or press inside ``HTMAXBUTTON`` never reaches the buttons, so
        their feedback is driven from the non-client messages instead.
        """
        code = int(native.wParam)
        if native.message == WM_NCMOUSEMOVE:
            self._chrome.native_hover(code)
        elif native.message == WM_NCLBUTTONDOWN:
            self._chrome.native_press(code)
        elif native.message == WM_NCLBUTTONUP:
            self._chrome.native_press(None)
        else:  # WM_NCMOUSELEAVE, which Windows hardly ever sends here
            self._chrome.clear_native_state()

    def _caption_click(self, native: wintypes.MSG) -> bool:
        """Run a caption-button press here instead of handing it to Windows.

        ``WM_NCLBUTTONDOWN`` for one of the caption codes is claimed - the
        answer is ``(True, 0)``, so ``DefWindowProc`` never sees it and never
        runs the push-button loop that paints a classic caption button over the
        row. The button is lit on the press and acts on the release, and only
        while the cursor is still on it, the way Windows counts a click.

        Returns whether the message was one of ours.
        """
        name = caption_button_for_code(int(native.wParam))
        if name is None:
            return False
        if native.message == WM_NCLBUTTONDOWN:
            self._chrome.native_press(int(native.wParam))
            return True
        self._chrome.native_press(None)
        if self._pointer_button() == name:
            self._chrome.activate_caption_button(name)
        return True

    def pointer_over_buttons(self) -> bool:
        """Whether the cursor still sits on one of the caption buttons.

        Windows reports the cursor leaving the non-client area with
        ``WM_NCMOUSELEAVE``, and that message cannot be relied on here: the
        frame is claimed whole by ``WM_NCCALCSIZE``, so the window has no
        non-client area to leave and the tracking never fires. The chrome
        therefore asks where the pointer is instead, while a button is lit, so
        a hover cannot be left behind on a window the cursor has left.
        """
        return self._pointer_button() is not None

    def _pointer_button(self) -> str | None:
        """Which caption button, if any, the cursor is on right now."""
        if self._hwnd == 0:
            return None
        api = _api()
        point = wintypes.POINT()
        if not api.user32.GetCursorPos(ctypes.byref(point)):
            return None
        if not api.user32.ScreenToClient(self._hwnd, ctypes.byref(point)):
            return None
        chrome = self._chrome
        dpr = float(chrome.devicePixelRatioF() or 1.0)
        x = point.x / dpr
        y = point.y / dpr
        for name, rect in chrome.caption_regions().buttons.items():
            if _contains(rect, x, y):
                return name
        return None

    def frame_metrics(self) -> FrameMetrics:
        """The invisible frame's thickness in physical pixels, for this DPI."""
        api = _api()
        dpi = api.window_dpi(self._hwnd)
        padded = api.system_metric(SM_CXPADDEDBORDER, dpi)
        return FrameMetrics(
            x=api.system_metric(SM_CXSIZEFRAME, dpi) + padded,
            y=api.system_metric(SM_CYSIZEFRAME, dpi) + padded,
        )
