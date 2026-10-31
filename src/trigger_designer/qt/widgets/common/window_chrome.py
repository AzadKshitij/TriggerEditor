"""VSCode-style window chrome: menus, drag area and window controls in one row.

The main window goes frameless and ``QMainWindow.setMenuWidget()`` is handed this
32px row; the window's real :class:`QMenuBar` is reparented into it, so File /
Edit / Window / Help keep their actions, shortcuts and Alt mnemonics - Qt routes
Alt to a visible menu bar wherever it lives (guarded by
``tests/ui/test_window_chrome.py``).

Drawing the caption ourselves costs the window its Windows behaviour: a
frameless popup gets no snap previews, no Snap Layouts flyout over the maximize
button, no DWM shadow and no rounded corners. On Windows the row hands those
jobs back to the system - ``qt/helpers/win_caption.py`` gives the window a real
frame and answers ``WM_NCCALCSIZE`` / ``WM_NCHITTEST``, so Windows owns
dragging, resizing, the caption buttons and the system menu while this widget
keeps drawing them. Everywhere else the Qt path stays: dragging and edge
resizing go through ``QWindow.startSystemMove()`` / ``startSystemResize()``,
which is what those platforms offer.

Trap: once a custom widget owns the menu slot, ``QMainWindow.menuBar()`` returns
a *new* empty bar and swaps the chrome out of the window.
``TriggerWindow.menuBar()`` is overridden to keep handing back the embedded one;
nothing else may reach the base implementation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from loguru import logger
from qtpy.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QSize, Qt, QTimer
from qtpy.QtGui import (
    QColor,
    QFontMetrics,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QSizePolicy,
    QSpacerItem,
    QWidget,
)

from trigger_designer.qt.helpers.win_caption import (
    CaptionRegions,
    WinCaption,
    caption_button_for_code,
    native_caption_supported,
)
from trigger_designer.qt.theme_manager import get_theme_manager
from trigger_designer.qt.widgets.common.config_widgets import IconButton

#: Chrome row height and caption-button hit area (docs/DESIGN_SYSTEM.md §17).
CHROME_H = 32
#: Caption glyphs are hand-drawn on a 12px grid; independent of IconButton.
CAPTION_ICON_SIZE = 12
CAPTION_BUTTON_W = 44
#: Width of the edge zone that starts a native resize on a frameless window.
RESIZE_MARGIN = 5
#: App-icon slot: the 16px icon plus the gap before the menus.
_ICON_SLOT_W = 32
#: How often a lit caption button re-checks where the pointer is, in ms.
_NATIVE_WATCH_MS = 120

# -- caption glyphs -----------------------------------------------------------
#
# Drawn here rather than shipped as bitmaps: the strokes follow the theme
# colour, stay crisp at any device-pixel ratio, and there are no new resource
# ids to keep in sync. Geometry is the Windows caption grid (10x10 in a
# 12px box, 1px strokes).


def _draw_minimize(painter: QPainter) -> None:
    painter.drawLine(1, 6, 10, 6)


def _draw_maximize(painter: QPainter) -> None:
    painter.drawRect(1, 1, 9, 9)


def _draw_restore(painter: QPainter) -> None:
    painter.drawRect(1, 4, 6, 6)
    painter.drawPolyline(QPolygonF([QPointF(3, 1), QPointF(10, 1), QPointF(10, 8)]))
    painter.drawLine(3, 1, 3, 4)


def _draw_close(painter: QPainter) -> None:
    painter.drawLine(1, 1, 10, 10)
    painter.drawLine(10, 1, 1, 10)


_GLYPH_PAINTERS: dict[str, Callable[[QPainter], None]] = {
    "minimize": _draw_minimize,
    "maximize": _draw_maximize,
    "restore": _draw_restore,
    "close": _draw_close,
}


def caption_icon(glyph: str, color: QColor) -> QIcon:
    """One 12px caption glyph as a multi-DPI ``QIcon``."""
    icon = QIcon()
    for dpr in (1.0, 1.25, 1.5, 2.0):
        pixmap = QPixmap(round(CAPTION_ICON_SIZE * dpr), round(CAPTION_ICON_SIZE * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(color)
        pen.setWidthF(1.0)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        _GLYPH_PAINTERS[glyph](painter)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class CaptionButton(IconButton):
    """Minimize / maximize / close: flat 44x32 hit area, glyph follows the theme.

    All three share ``WindowChromeButton``; Close carries a ``danger`` property
    so base.qss can paint its hover red without a second selector family.
    Hover and pressed are restated for that objectName in base.qss - an
    ``#objectName`` selector outranks ``QPushButton:hover``.
    """

    def __init__(
        self,
        glyph: str,
        tooltip: str,
        danger: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(tooltip, parent=parent)
        self.setObjectName("WindowChromeButton")
        if danger:
            self.setProperty("danger", True)
        self.setFixedSize(QSize(CAPTION_BUTTON_W, CHROME_H))
        self._glyph = glyph
        self.apply_theme()

    def set_glyph(self, glyph: str, tooltip: str) -> None:
        """Swap the painted glyph (maximize <-> restore) and its labels."""
        self._glyph = glyph
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.apply_theme()

    def set_native_visual(self, *, hovered: bool, pressed: bool) -> None:
        """Paint the hover/pressed look Windows reported, through base.qss.

        Qt's own ``:hover`` cannot be switched on from a non-client message -
        the style reads it from a real mouse move, and Windows owns these
        pixels now - so base.qss restates both states against these two
        properties and the widget is repolished when they change. ``setDown``
        is deliberately not used: Windows carries the click out itself and a
        minimized window never reports the button up, which left the button
        painted pressed for good.
        """
        hovered = bool(hovered)
        pressed = bool(pressed)
        if (
            bool(self.property("nativeHover")) == hovered
            and bool(self.property("nativePress")) == pressed
        ):
            return
        self.setProperty("nativeHover", hovered)
        self.setProperty("nativePress", pressed)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def apply_theme(self) -> None:
        color = get_theme_manager().color("text_secondary", "#c6cdd5")
        self.setIcon(caption_icon(self._glyph, color))


class WindowChrome(QWidget):
    """The single row that replaces the caption and the menu bar."""

    def __init__(
        self,
        window: QMainWindow,
        menu_bar: QMenuBar,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent if parent is not None else window)
        self.setObjectName("WindowChrome")
        self.setFixedHeight(CHROME_H)

        self._window = window
        self._menu_bar = menu_bar
        self._context_title = ""
        #: Width of the spacer that keeps the title centred in the window.
        self._title_balance = -1

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 0, 0, 0)
        row.setSpacing(0)

        self._icon_label = QLabel(self)
        self._icon_label.setObjectName("WindowChromeIcon")
        self._icon_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self._icon_label.setFixedWidth(_ICON_SLOT_W)
        self._icon_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        row.addWidget(self._icon_label)

        # Hug the menus so the empty stretch of the bar is chrome background:
        # presses there start the window drag instead of landing on the bar.
        menu_bar.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        row.addWidget(menu_bar)

        row.addStretch(1)
        self._title_label = QLabel(self)
        self._title_label.setObjectName("WindowChromeTitle")
        self._title_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        # The box hugs the elided text; centre inside it anyway so a squeezed
        # layout cannot push the visible title off the middle of the row.
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._title_label)
        row.addStretch(1)

        #: Mirrors the part of the left group the caption buttons do not
        #: cover, so the stretches leave the title in the middle of the
        #: window instead of the middle of the gap; sized by _balance_title().
        self._balance_item = QSpacerItem(
            0, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum
        )
        row.addSpacerItem(self._balance_item)

        self._minimize_button = CaptionButton("minimize", "Minimize", parent=self)
        self._maximize_button = CaptionButton("maximize", "Maximize", parent=self)
        self._close_button = CaptionButton("close", "Close", danger=True, parent=self)
        self._caption_buttons: dict[str, CaptionButton] = {
            "minimize": self._minimize_button,
            "maximize": self._maximize_button,
            "close": self._close_button,
        }
        for button in (
            self._minimize_button,
            self._maximize_button,
            self._close_button,
        ):
            row.addWidget(button)

        self._minimize_button.clicked.connect(window.showMinimized)
        self._maximize_button.clicked.connect(self.toggle_maximized)
        self._close_button.clicked.connect(window.close)

        window.installEventFilter(self)
        window.windowTitleChanged.connect(self._refresh_title)
        window.windowIconChanged.connect(self._refresh_icon)

        #: Kept as an attribute so the filter cannot be collected; its Qt
        #: parent is the window.
        self.resizer: _ResizeEdgeFilter | None = None
        #: The Win32 caption, attached by install_window_chrome() on Windows:
        #: it owns the frame styles and the non-client messages.
        self.caption: WinCaption | None = None
        #: Caption button Windows currently reports as hovered or pressed. A
        #: click inside HTMAXBUTTON never reaches Qt, so both looks are driven
        #: from WM_NCMOUSEMOVE / WM_NCLBUTTONDOWN and painted through the two
        #: properties base.qss keys on.
        self._native_hover: CaptionButton | None = None
        self._native_pressed: CaptionButton | None = None
        #: Runs while a caption button is lit, to notice the cursor leaving.
        self._native_watch: QTimer | None = None

        self.apply_theme()
        self._refresh_icon()
        self._refresh_title()
        self._sync_maximize_button()

    # -- accessors ------------------------------------------------------------

    def menu_bar(self) -> QMenuBar:
        """The window's real menu bar, now living inside the chrome row."""
        return self._menu_bar

    def window(self) -> QMainWindow:
        """The window the row belongs to."""
        return self._window

    def set_context_title(self, text: str | None) -> None:
        """Show the active document in the middle (``None`` = window title)."""
        self._context_title = (text or "").strip()
        self._refresh_title()

    # -- theme and labels -----------------------------------------------------

    def apply_theme(self) -> None:
        for button in (
            self._minimize_button,
            self._maximize_button,
            self._close_button,
        ):
            button.apply_theme()
        self._refresh_icon()
        # Menu padding is themed: the left group may have changed width.
        self._balance_title()
        if self.caption is not None:
            self.caption.apply_theme(get_theme_manager().is_dark())

    def _left_group_width(self) -> int:
        """Width of the app icon and the menus, left margin included.

        ``QMainWindow`` still tracks the ``QMenuBar`` object it handed over,
        so a style-sheet change resizes the reparented bar to the whole
        window width for a moment. Trusting that transient in
        :meth:`_balance_title` sizes the spacer from the entire window, the
        row then cannot fit its children, and the bar collapses to its
        overflow minimum - the title bar glitch after a theme change. A bar
        is never legitimately wider than its own hint, so the smaller of the
        two is the width the chrome's layout gives it.
        """
        bar = self._menu_bar
        width = self.layout().contentsMargins().left()
        if self._icon_label.isVisibleTo(self):
            width += _ICON_SLOT_W
        return width + min(bar.width(), bar.sizeHint().width())

    def _balance_title(self) -> None:
        """Put the middle of the row back on the middle of the window.

        The two stretches around the title centre it in the gap between the
        icon and menus on one side and the caption buttons on the other.
        Menus are wider than buttons, which pushes the title right by half the
        difference; an equally wide spacer before the buttons cancels it.
        """
        extra = max(0, self._left_group_width() - 3 * CAPTION_BUTTON_W)
        if extra == self._title_balance:
            return
        self._title_balance = extra
        self._balance_item.changeSize(
            extra, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum
        )
        self.layout().invalidate()

    def _refresh_icon(self, *_ignored: object) -> None:
        window = self._window
        dpr = float(window.devicePixelRatioF() or 1.0)
        side = max(1, round(16 * dpr))
        pixmap = window.windowIcon().pixmap(QSize(side, side))
        if pixmap.isNull():
            self._icon_label.setVisible(False)
            return
        pixmap.setDevicePixelRatio(dpr)
        self._icon_label.setPixmap(pixmap)
        self._icon_label.setVisible(True)

    def _refresh_title(self, *_ignored: object) -> None:
        full = self._context_title or self._window.windowTitle()
        if not full or self.width() <= 0:
            self._title_label.setText("")
            return
        # The title is centred, so it can grow by the free space on both
        # sides of the left group - not the whole room between the groups.
        available = max(0, self.width() - 2 * self._left_group_width())
        if available < 60:
            self._title_label.setText("")
            return
        metrics = QFontMetrics(self._title_label.font())
        self._title_label.setText(
            metrics.elidedText(full, Qt.TextElideMode.ElideMiddle, available)
        )

    def _sync_maximize_button(self) -> None:
        if self._window.isMaximized():
            self._maximize_button.set_glyph("restore", "Restore")
        else:
            self._maximize_button.set_glyph("maximize", "Maximize")

    # -- window controls ------------------------------------------------------

    def toggle_maximized(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def activate_caption_button(self, name: str) -> None:
        """Run the action a caption button stands for.

        The native caption claims the press and the release itself, so the
        click never reaches the ``QPushButton``s and this is where Windows'
        answer to the release lands. Every button runs what its ``clicked``
        signal does, so a click through the native path and a click through Qt
        cannot drift apart.
        """
        if name == "minimize":
            self._window.showMinimized()
        elif name == "maximize":
            self.toggle_maximized()
        elif name == "close":
            self._window.close()

    # -- native caption (Windows) ---------------------------------------------

    def caption_regions(self) -> CaptionRegions:
        """The row split the way the native hit test has to see it.

        Logical, client-relative rectangles. The resize ring is not in here:
        ``hit_test`` derives it from the system's own frame metrics, so only
        the parts that belong to widgets are named.
        """
        window = self._window

        def rect_of(widget: QWidget) -> QRect:
            return QRect(widget.mapTo(window, QPoint(0, 0)), widget.size())

        # No icon on the window means no system-menu slot: the drag area takes
        # the space instead.
        icon = (
            rect_of(self._icon_label) if self._icon_label.isVisibleTo(self) else QRect()
        )
        return CaptionRegions(
            row=self.geometry(),
            menu=rect_of(self._menu_bar),
            icon=icon,
            buttons={
                name: rect_of(button) for name, button in self._caption_buttons.items()
            },
        )

    def native_event(self, event_type: object, message: object) -> tuple[bool, int]:
        """Route one native message to the Win32 caption, if it is attached."""
        caption = self.caption
        if caption is None:
            return (False, 0)
        return caption.native_event(event_type, message)

    def native_hover(self, code: int | None) -> None:
        """Light up the button Windows says the cursor is over."""
        button = self._caption_button(code)
        if button is self._native_hover:
            return
        self._native_hover = button
        self._sync_native_look()
        self._watch_native_hover()

    def native_press(self, code: int | None) -> None:
        """Mark the button Windows is about to activate, if any."""
        button = self._caption_button(code)
        if button is self._native_pressed:
            return
        self._native_pressed = button
        self._sync_native_look()
        self._watch_native_hover()

    def clear_native_state(self) -> None:
        """Drop hover and pressed: the window moved, hid or lost the cursor."""
        self._stop_native_watch()
        if self._native_hover is None and self._native_pressed is None:
            return
        self._native_hover = None
        self._native_pressed = None
        self._sync_native_look()

    def _caption_button(self, code: int | None) -> CaptionButton | None:
        name = caption_button_for_code(code)
        return None if name is None else self._caption_buttons[name]

    def _sync_native_look(self) -> None:
        """Hand the current hover/pressed pair to every button.

        The two are independent - a button stays lit while it is held - and
        base.qss orders the rules so pressed outranks hover.
        """
        for button in self._caption_buttons.values():
            button.set_native_visual(
                hovered=button is self._native_hover,
                pressed=button is self._native_pressed,
            )

    def _watch_native_hover(self) -> None:
        """Follow the lit button with a pointer check, while one is lit.

        Windows does not report the cursor leaving the caption (see
        :meth:`WinCaption.pointer_over_buttons`), so the look is dropped once
        the pointer is no longer on a button. The check only runs while a
        button is lit, and the first tick that finds the pointer gone stops it.
        """
        if self._native_hover is None and self._native_pressed is None:
            self._stop_native_watch()
            return
        if self.caption is None:  # offscreen, or not Windows
            return
        watch = self._native_watch
        if watch is None:
            watch = self._native_watch = QTimer(self)
            watch.setInterval(_NATIVE_WATCH_MS)
            watch.timeout.connect(self._check_native_hover)
        if not watch.isActive():
            watch.start()

    def _stop_native_watch(self) -> None:
        if self._native_watch is not None:
            self._native_watch.stop()

    def _check_native_hover(self) -> None:
        """Drop the lit button once the pointer is no longer on one."""
        caption = self.caption
        if caption is not None and caption.pointer_over_buttons():
            return
        self.clear_native_state()

    def _attach_caption(self) -> None:
        """Apply the native frame, if this window has one to apply it to."""
        caption = self.caption
        if caption is None:
            return
        caption.apply_theme(get_theme_manager().is_dark())
        caption.attach()

    # -- events ---------------------------------------------------------------

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        if obj is self._window:
            # Qt throws the HWND away when window flags change; the frame
            # styles have to be given to the new one.
            if event.type() in (QEvent.Type.Show, QEvent.Type.WinIdChange):
                self._attach_caption()
            if event.type() in (
                QEvent.Type.WindowStateChange,
                QEvent.Type.Show,
                QEvent.Type.Hide,
                QEvent.Type.WindowDeactivate,
            ):
                # Minimizing from the caption button is carried out by Windows
                # before the button-up arrives, so the lit button is dropped
                # here rather than left painted for the rest of the session.
                self.clear_native_state()
            if event.type() in (
                QEvent.Type.WindowStateChange,
                QEvent.Type.Show,
            ):
                self._sync_maximize_button()
                self._refresh_title()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._balance_title()
        self._refresh_title()

    def mousePressEvent(self, event) -> None:
        # Hand the mouse to the native move loop: Aero snap, dragging a
        # maximized window back to normal, multi-monitor behaviour included.
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._window.isFullScreen()
        ):
            handle = self._window.windowHandle()
            if handle is not None and handle.startSystemMove():
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class _ResizeEdgeFilter(QObject):
    """Native edge-resize for a frameless window.

    The window has no native sizing border, so a left-button press within
    ``RESIZE_MARGIN`` of an edge is intercepted before the widget under the
    cursor sees it and handed to ``QWindow.startSystemResize()`` - the same
    native loop a real border runs. The filter watches the whole application
    because the margin can fall on any child: docks, splitter handles, canvas.
    """

    _CURSORS: ClassVar[dict[Qt.Edge, Qt.CursorShape]] = {
        Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor,
        Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
        Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor,
        Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor,
        Qt.Edge.LeftEdge | Qt.Edge.TopEdge: Qt.CursorShape.SizeFDiagCursor,
        Qt.Edge.RightEdge | Qt.Edge.BottomEdge: Qt.CursorShape.SizeFDiagCursor,
        Qt.Edge.RightEdge | Qt.Edge.TopEdge: Qt.CursorShape.SizeBDiagCursor,
        Qt.Edge.LeftEdge | Qt.Edge.BottomEdge: Qt.CursorShape.SizeBDiagCursor,
    }

    def __init__(
        self,
        window: QMainWindow,
        menu_bar: QMenuBar,
        margin: int = RESIZE_MARGIN,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._menu_bar = menu_bar
        self._margin = margin
        self._cursor_widget: QWidget | None = None
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        # The filter sees every event of the application: one bad event must
        # never take the event loop down with it.
        try:
            return self._filter_mouse(obj, event)
        except Exception:  # noqa: BLE001 - guard, see comment above
            logger.exception("edge-resize filter failed")
            return False

    def _filter_mouse(self, obj: object, event: QEvent) -> bool:
        window = self._window
        if (
            not isinstance(obj, QWidget)
            or event.type() not in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove)
            or obj.window() is not window
            or window.isMaximized()
            or window.isFullScreen()
            or not window.isVisible()
        ):
            return False

        edges = self._edges_at(event.globalPosition().toPoint())
        if obj is self._menu_bar:
            # The bar owns its own top few pixels: a press near the top of a
            # menu must open it, not start a resize. The top edge stays
            # resizable left of, right of and behind the menus.
            edges = edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() != Qt.MouseButton.LeftButton or not edges:
                return False
            handle = window.windowHandle()
            # The press belongs to the resize, not to the child under it.
            return handle is not None and handle.startSystemResize(edges)

        if event.buttons() != Qt.MouseButton.NoButton:
            return False
        self._set_cursor(self._CURSORS.get(edges) if edges else None, obj)
        return False

    def _edges_at(self, position: QPoint) -> Qt.Edge:
        rect = self._window.frameGeometry()
        if not rect.contains(position):
            return Qt.Edge(0)
        margin = self._margin
        edges = Qt.Edge(0)
        if position.x() - rect.left() < margin:
            edges |= Qt.Edge.LeftEdge
        if rect.right() - position.x() < margin:
            edges |= Qt.Edge.RightEdge
        if position.y() - rect.top() < margin:
            edges |= Qt.Edge.TopEdge
        if rect.bottom() - position.y() < margin:
            edges |= Qt.Edge.BottomEdge
        return edges

    def _set_cursor(self, cursor: Qt.CursorShape | None, widget: QWidget) -> None:
        if self._cursor_widget is not None and self._cursor_widget is not widget:
            self._clear_cursor()
        if cursor is None:
            self._clear_cursor()
            return
        try:
            widget.setCursor(cursor)
        except RuntimeError:  # the widget died between two moves
            return
        self._cursor_widget = widget

    def _clear_cursor(self) -> None:
        widget = self._cursor_widget
        self._cursor_widget = None
        if widget is None:
            return
        try:
            widget.unsetCursor()
        except RuntimeError:
            pass


def install_window_chrome(window: QMainWindow) -> WindowChrome:
    """Give ``window`` the single-row chrome.

    Must run after the menus exist and before the window is first shown. On
    Windows the row also gets its frame styles here, so the window is already
    snap-capable by the time it appears.
    """
    menu_bar = window.menuBar()  # the real bar must exist before the swap
    chrome = WindowChrome(window, menu_bar)
    window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    window.setMenuWidget(chrome)
    # setMenuWidget() explicitly hides the previous menu widget - the real
    # QMenuBar, already reparented into the chrome above.
    menu_bar.show()
    if native_caption_supported():
        # Windows owns dragging, resizing, the caption buttons and the system
        # menu from here; the Qt-side edge filter would only fight the native
        # border over the same pixels.
        chrome.caption = WinCaption(chrome)
    else:
        chrome.resizer = _ResizeEdgeFilter(window, menu_bar)
    return chrome
