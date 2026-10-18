#!/usr/bin/env python3
"""Window chrome: menus, drag area and caption buttons in one 32px row.

The window is frameless and a custom ``WindowChrome`` owns the menu slot, so
the assertions pin the documented traps:

* ``setMenuWidget(chrome)`` explicitly hides the real ``QMenuBar`` - it has
  to be shown again or the menus vanish;
* calling the base ``QMainWindow.menuBar()`` after the swap creates a *new*
  empty bar and replaces the chrome with it, so ``TriggerWindow.menuBar()``
  must keep returning the embedded one - and Alt, which activates the visible
  bar, must not disturb the arrangement either.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from qtpy.QtCore import QPoint, Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QLabel, QMenu

from trigger_designer.qt.helpers.win_caption import HTCLOSE, HTMAXBUTTON
from trigger_designer.qt.main_window import TriggerWindow
from trigger_designer.qt.widgets.common.window_chrome import CHROME_H, CaptionButton

_APP = QApplication.instance() or QApplication([])


class TestWindowChrome(unittest.TestCase):
    def setUp(self) -> None:
        self.window = TriggerWindow()
        self.chrome = self.window.window_chrome
        self.menu_bar = self.chrome.menu_bar()
        self.window.show()
        _APP.processEvents()

    def tearDown(self) -> None:
        # close() would run TriggerWindow.closeEvent, which saves the session
        # and quits the shared QApplication; tear down the way the other UI
        # tests do instead.
        self.window.hide()
        self.window.deleteLater()
        _APP.processEvents()

    def _button(self, tooltip: str) -> CaptionButton:
        for button in self.chrome.findChildren(CaptionButton):
            if button.toolTip() == tooltip:
                return button
        raise AssertionError(f"caption button {tooltip!r} not found")

    def _title_label(self) -> QLabel:
        label = self.chrome.findChild(QLabel, "WindowChromeTitle")
        assert label is not None
        return label

    def test_chrome_owns_the_menu_slot(self) -> None:
        self.assertTrue(self.window.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertIs(self.window.menuWidget(), self.chrome)
        self.assertIs(self.window.menuBar(), self.menu_bar)
        self.assertTrue(self.menu_bar.isVisible())
        self.assertEqual(self.chrome.y(), 0)
        self.assertEqual(self.chrome.height(), CHROME_H)
        self.assertGreater(self.menu_bar.width(), 0)

    def test_menus_are_intact(self) -> None:
        titles = [action.text() for action in self.menu_bar.actions()]
        for expected in ("&File", "&Edit", "&Window", "&Help"):
            self.assertIn(expected, titles)
        self.assertTrue(self.window.fileMenu.actions())
        self.assertTrue(self.window.helpMenu.actions())

    def test_alt_focuses_the_embedded_bar(self) -> None:
        QTest.keyClick(self.window, Qt.Key.Key_Alt)
        _APP.processEvents()
        self.assertTrue(self.menu_bar.hasFocus())
        # Alt must not have swapped the chrome for a fresh, empty bar.
        self.assertIs(self.window.menuWidget(), self.chrome)

        active = self.menu_bar.activeAction()
        self.assertIsNotNone(active)
        menu = active.menu()
        self.assertIsInstance(menu, QMenu)

        QTest.keyClick(self.menu_bar, Qt.Key.Key_Down)
        _APP.processEvents()
        self.assertTrue(menu.isVisible())
        QTest.keyClick(self.menu_bar, Qt.Key.Key_Escape)
        _APP.processEvents()
        self.assertFalse(menu.isVisible())

    def test_caption_buttons_carry_labels_and_tone(self) -> None:
        buttons = self.chrome.findChildren(CaptionButton)
        self.assertEqual(len(buttons), 3)
        self.assertEqual(
            {button.toolTip() for button in buttons},
            {"Minimize", "Maximize", "Close"},
        )
        for button in buttons:
            self.assertTrue(button.accessibleName())
            self.assertFalse(button.icon().isNull())
        self.assertTrue(self._button("Close").property("danger"))
        self.assertFalse(self._button("Maximize").property("danger"))

    def test_maximize_button_toggles_and_swaps_its_glyph(self) -> None:
        maximize = self._button("Maximize")
        QTest.mouseClick(maximize, Qt.MouseButton.LeftButton)
        _APP.processEvents()
        self.assertTrue(self.window.isMaximized())
        self.assertEqual(maximize.toolTip(), "Restore")
        self.assertTrue(maximize.accessibleName())

        QTest.mouseClick(maximize, Qt.MouseButton.LeftButton)
        _APP.processEvents()
        self.assertFalse(self.window.isMaximized())
        self.assertEqual(maximize.toolTip(), "Maximize")
        self.assertIs(self.window.menuWidget(), self.chrome)

    def test_minimize_button_is_wired(self) -> None:
        QTest.mouseClick(self._button("Minimize"), Qt.MouseButton.LeftButton)
        _APP.processEvents()
        self.assertTrue(self.window.isMinimized())
        self.window.showNormal()
        _APP.processEvents()

    def test_native_hover_and_press_are_style_properties(self) -> None:
        """Windows owns the caption pixels, so its look arrives as messages.

        Qt's ``:hover`` never sees a non-client move, so base.qss restates the
        two states against ``nativeHover`` / ``nativePress``. ``setDown`` is
        deliberately not used: Windows carries the click out itself, and a
        window minimized from the button never reports the button up.
        """
        maximize = self._button("Maximize")
        close = self._button("Close")

        self.chrome.native_hover(HTMAXBUTTON)
        self.assertTrue(maximize.property("nativeHover"))
        self.assertFalse(maximize.isDown())

        self.chrome.native_press(HTMAXBUTTON)
        self.assertTrue(maximize.property("nativePress"))
        # Pressed and hovered are independent: the lit button stays lit.
        self.assertTrue(maximize.property("nativeHover"))
        self.assertFalse(maximize.isDown())

        self.chrome.native_hover(HTCLOSE)
        self.assertFalse(maximize.property("nativeHover"))
        self.assertTrue(close.property("nativeHover"))
        self.assertTrue(maximize.property("nativePress"))

        self.chrome.native_press(None)
        self.assertFalse(maximize.property("nativePress"))
        self.assertTrue(close.property("nativeHover"))

        # A state change - minimize above all - drops the lit button.
        self.chrome.clear_native_state()
        for button in (maximize, close):
            self.assertFalse(button.property("nativeHover"))
            self.assertFalse(button.property("nativePress"))

    def test_a_lit_button_is_dropped_once_the_pointer_leaves(self) -> None:
        """Windows never reports the cursor leaving the caption.

        The frame is claimed whole by ``WM_NCCALCSIZE``, so the window has no
        non-client area to leave and the tracking message never arrives. While
        a button is lit the chrome asks the caption where the pointer is, and
        drops the look as soon as it is off the buttons.
        """

        class _Caption:
            def __init__(self) -> None:
                self.over = True

            def pointer_over_buttons(self) -> bool:
                return self.over

        caption = _Caption()
        self.chrome.caption = caption  # type: ignore[assignment]
        maximize = self._button("Maximize")

        self.chrome.native_hover(HTMAXBUTTON)
        self.assertTrue(self.chrome._native_watch is not None)
        self.assertTrue(self.chrome._native_watch.isActive())
        self.chrome._check_native_hover()
        self.assertTrue(maximize.property("nativeHover"))

        caption.over = False
        self.chrome._check_native_hover()
        self.assertFalse(maximize.property("nativeHover"))
        self.assertFalse(self.chrome._native_watch.isActive())
        self.chrome.caption = None

    def test_double_click_on_the_row_toggles_maximized(self) -> None:
        point = QPoint(self.chrome.width() // 2, CHROME_H // 2)
        QTest.mouseDClick(self.chrome, Qt.MouseButton.LeftButton, pos=point)
        _APP.processEvents()
        self.assertTrue(self.window.isMaximized())
        QTest.mouseDClick(self.chrome, Qt.MouseButton.LeftButton, pos=point)
        _APP.processEvents()
        self.assertFalse(self.window.isMaximized())

    def test_context_title_elides_and_falls_back(self) -> None:
        self.window.resize(1600, 900)
        _APP.processEvents()
        self.chrome.set_context_title("roadmap_2026.tds")
        self.assertEqual(self._title_label().text(), "roadmap_2026.tds")

        self.chrome.set_context_title("very_long_document_name_" * 12)
        self.assertIn("\u2026", self._title_label().text())

        self.chrome.set_context_title(None)
        self.assertEqual(self._title_label().text(), self.window.windowTitle())

    def test_title_is_centred_in_the_window(self) -> None:
        """The menus are wider than the caption buttons; the title still centres.

        The stretches alone would centre it in the gap between the two groups,
        which sits right of the window's middle; the balance spacer cancels
        that offset.
        """
        self.window.resize(1280, 800)
        _APP.processEvents()
        label = self._title_label()
        self.assertLessEqual(
            abs(label.x() + label.width() // 2 - self.chrome.width() // 2), 1
        )

        # A wide title elides in the room the centred slot has, and never
        # runs under the caption buttons.
        self.chrome.set_context_title("wide_document_name_" * 20)
        _APP.processEvents()
        label = self._title_label()
        self.assertIn("\u2026", label.text())
        self.assertLessEqual(label.x() + label.width(), self._button("Minimize").x())
        self.assertLessEqual(
            abs(label.x() + label.width() // 2 - self.chrome.width() // 2), 1
        )


if __name__ == "__main__":
    unittest.main()
