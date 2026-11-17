"""Frameless dialog base: the main window's chrome, scaled down for popups.

Every app dialog subclasses :class:`FramelessDialog` instead of ``QDialog`` so
its title bar follows the colour scheme like the main window's chrome does,
rather than the OS caption (dark bar on a light theme, GitHub issue #45).

Two layers, each used for what it is good at:

* **QSS** owns the look - ``#DialogChrome`` / ``#DialogChromeTitle`` and
  ``QDialog[frameless="true"]`` in ``base.qss``; the close button reuses the
  ``WindowChromeButton`` rules, including the ``danger`` hover.
* **QStyle** owns the painting and polish - both widgets draw their QSS box
  through ``QStyleOption`` + ``drawPrimitive(PE_Widget)`` (a plain ``QWidget``
  subclass paints no stylesheet background otherwise), and a theme change goes
  through :func:`repolish` (``unpolish`` / ``polish``).

Layout: subclasses keep ``QVBoxLayout(self)``. The base reserves the row with
``setContentsMargins(0, CHROME_H, 0, 0)`` and floats the chrome over it, so no
dialog's layout code changes.

Platforms:

* Windows gives the dialog a real frame (``WinCaption``): DWM shadow, rounded
  corners, native resize border, native drag from the row and the system menu.
  The close button is reported as ``HTCLIENT`` so Qt keeps its hover and click;
  no min/max style is set, so a double-click on the row cannot maximize.
* macOS / Linux have no such layer: drag uses ``startSystemMove()`` (with a
  manual move when the compositor refuses it, as Wayland may) and resize uses
  the shared ``_ResizeEdgeFilter``. There is no native shadow, so QSS draws a
  1px border.

Trap: a ``nativeEvent`` override must not call the base implementation (see
``win_caption``); unhandled messages are answered ``(False, 0)``.
"""

from __future__ import annotations

from qtpy.QtCore import QEvent, QPoint, QRect, Qt
from qtpy.QtGui import QPainter
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QStyleOption,
    QWidget,
)

from trigger_designer.qt.helpers.win_caption import (
    CaptionRegions,
    WinCaption,
    dialog_frame_styles,
    native_caption_supported,
)
from trigger_designer.qt.theme_manager import get_theme_manager, repolish
from trigger_designer.qt.widgets.common.window_chrome import (
    CHROME_H,
    CaptionButton,
    _ResizeEdgeFilter,
)

__all__ = ["DialogChrome", "FramelessDialog"]


def _paint_styled(widget: QWidget) -> None:
    """Draw ``widget``'s QSS box (background, border) through its QStyle."""
    option = QStyleOption()
    option.initFrom(widget)
    painter = QPainter(widget)
    widget.style().drawPrimitive(
        QStyle.PrimitiveElement.PE_Widget, option, painter, widget
    )
    painter.end()


class _ElidedLabel(QLabel):
    """A label that elides its text to whatever width layout gives it.

    Eliding from the dialog's resize would use the width the layout has not
    assigned yet; the label's own resize event always sees the final one.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def set_full_text(self, text: str) -> None:
        self._full_text = text
        self._elide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        width = self.width()
        text = self._full_text
        if width > 0:
            text = self.fontMetrics().elidedText(
                text, Qt.TextElideMode.ElideRight, width
            )
        self.setText(text)
        self.setToolTip(self._full_text)


class DialogChrome(QWidget):
    """The title row of a dialog: the title, centred left, and a close button."""

    def __init__(self, dialog: FramelessDialog) -> None:
        super().__init__(dialog)
        self.setObjectName("DialogChrome")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(CHROME_H)
        self._dialog = dialog
        #: Cursor offset inside the dialog while a manual move is running.
        self._drag_offset: QPoint | None = None

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 0, 0)
        row.setSpacing(0)

        self._title_label = _ElidedLabel(self)
        self._title_label.setObjectName("DialogChromeTitle")
        self._title_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        row.addWidget(self._title_label, 1)

        self._close_button = CaptionButton("close", "Close", danger=True, parent=self)
        # A QDialog promotes its first autoDefault button to "default", which
        # the Qlementine style paints solid blue; the close button is chrome,
        # never the dialog's answer (Esc already rejects).
        self._close_button.setAutoDefault(False)
        self._close_button.setDefault(False)
        self._close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._close_button.clicked.connect(dialog.reject)
        row.addWidget(self._close_button)

        dialog.windowTitleChanged.connect(self._refresh_title)
        self._refresh_title()

    # -- accessors ------------------------------------------------------------

    def close_button(self) -> CaptionButton:
        return self._close_button

    def title_text(self) -> str:
        """The title as the dialog set it, before eliding."""
        return self._dialog.windowTitle()

    @property
    def resizable(self) -> bool:
        """Read by ``WinCaption`` to decide whether the border is live."""
        return self._dialog.is_resizable()

    # -- theme and labels -----------------------------------------------------

    def apply_theme(self) -> None:
        self._close_button.apply_theme()
        repolish(self)
        repolish(self._title_label)

    def _refresh_title(self, *_args: object) -> None:
        self._title_label.set_full_text(self.title_text())

    # -- Win32 caption contract ----------------------------------------------

    def caption_regions(self) -> CaptionRegions:
        """Row, with the close button carved out so Qt keeps its clicks.

        ``menu`` is the slot ``hit_test`` treats as client area that also owns
        its top pixels; the close button needs exactly that.
        """
        button = self._close_button.geometry()
        return CaptionRegions(
            row=self.geometry(),
            menu=QRect(
                self.x() + button.x(),
                self.y() + button.y(),
                button.width(),
                button.height(),
            ),
            icon=QRect(),
            buttons={},
        )

    def native_hover(self, _code: int | None) -> None:
        """Windows reports hovers over the row only; nothing is lit for them."""

    def native_press(self, _code: int | None) -> None:
        """See :meth:`native_hover`."""

    def clear_native_state(self) -> None:
        """See :meth:`native_hover`."""

    def activate_caption_button(self, _name: str) -> None:
        """Never called: the close button is client area, not a caption button."""

    # -- events ---------------------------------------------------------------

    def paintEvent(self, event: QEvent) -> None:
        _paint_styled(self)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        handle = self._dialog.windowHandle()
        if handle is not None and handle.startSystemMove():
            event.accept()
            return
        # The platform refused the native move loop (Wayland without a serial,
        # an embedded platform): follow the cursor by hand.
        self._drag_offset = (
            event.globalPosition().toPoint() - self._dialog.frameGeometry().topLeft()
        )
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if (
            self._drag_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self._dialog.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class FramelessDialog(QDialog):
    """A ``QDialog`` whose title bar is the app's own, themed chrome.

    ``exec()`` and the result codes are unchanged: the close button calls
    ``reject()`` and Esc keeps working, so callers and tests need no changes.
    Pass ``resizable=False`` for a fixed-size dialog.
    """

    def __init__(
        self, parent: QWidget | None = None, *, resizable: bool = True
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setProperty("frameless", True)
        self.setContentsMargins(0, CHROME_H, 0, 0)
        self._resizable = resizable

        self.chrome = DialogChrome(self)
        self.chrome.setGeometry(0, 0, self.width(), CHROME_H)
        self.chrome.raise_()

        #: Windows: owns the frame styles and the non-client messages.
        self.caption: WinCaption | None = None
        #: Elsewhere: native edge resize through ``startSystemResize()``.
        self.resizer: _ResizeEdgeFilter | None = None
        if native_caption_supported():
            self.caption = WinCaption(
                self.chrome, styles=dialog_frame_styles(resizable)
            )
        elif resizable:
            self.resizer = _ResizeEdgeFilter(self)

        get_theme_manager().themeChanged.connect(self._on_theme_changed)

    def is_resizable(self) -> bool:
        return self._resizable

    # -- theme ----------------------------------------------------------------

    def _on_theme_changed(self, _theme: object) -> None:
        self.chrome.apply_theme()
        if self.caption is not None:
            self.caption.apply_theme(get_theme_manager().is_dark())
        repolish(self)

    def _attach_caption(self) -> None:
        caption = self.caption
        if caption is None:
            return
        caption.apply_theme(get_theme_manager().is_dark())
        caption.attach()

    # -- events ---------------------------------------------------------------

    def nativeEvent(self, event_type, message):
        caption = self.caption
        if caption is None:
            return (False, 0)
        return caption.native_event(event_type, message)

    def event(self, event: QEvent) -> bool:
        # Qt throws the HWND away when window flags change; the frame styles
        # have to be given to the new one.
        if event.type() == QEvent.Type.WinIdChange:
            self._attach_caption()
        return super().event(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._attach_caption()
        self.chrome.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.chrome.setGeometry(0, 0, self.width(), CHROME_H)
        self.chrome.raise_()

    def paintEvent(self, event: QEvent) -> None:
        _paint_styled(self)
