#!/usr/bin/env python3
"""Tests for the revived ``TriggerSubWindow`` close path.

``TriggerSubWindow.closeEvent`` dispatches the registered close listeners.
A listener that ignores the event must veto the close - that is how
``TriggerWindow.onSubWndClose`` cancels closing a modified design when the
user picks "Cancel" in the save prompt.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow

_APP = QApplication.instance() or QApplication([])


class TestDesignWindowClose(unittest.TestCase):
    """The close event must reach the registered listeners."""

    def setUp(self) -> None:
        self.window = TriggerSubWindow()
        self.window.show()

    def tearDown(self) -> None:
        self.window.hide()
        self.window.deleteLater()

    def test_ignoring_listener_vetoes_close(self) -> None:
        seen = []

        def listener(widget, event):
            seen.append(widget is self.window)
            event.ignore()

        self.window.addCloseEventListener(listener)

        self.assertFalse(self.window.close())
        self.assertTrue(self.window.isVisible())
        self.assertEqual(seen, [True])

    def test_accepting_listener_closes(self) -> None:
        seen = []

        def listener(widget, event):
            seen.append(widget is self.window)
            event.accept()

        self.window.addCloseEventListener(listener)

        self.assertTrue(self.window.close())
        self.assertFalse(self.window.isVisible())
        self.assertEqual(seen, [True])

    def test_listeners_run_in_registration_order(self) -> None:
        order = []

        def first(widget, event):
            order.append("first")

        def second(widget, event):
            order.append("second")

        self.window.addCloseEventListener(first)
        self.window.addCloseEventListener(second)

        self.assertTrue(self.window.close())
        self.assertEqual(order, ["first", "second"])

    def test_accepted_close_stops_the_workflow_runner(self) -> None:
        stopped = []
        self.window.shutdown_workflow_worker = lambda: stopped.append(True)

        self.assertTrue(self.window.close())

        self.assertEqual(stopped, [True])

    def test_vetoed_close_leaves_the_workflow_runner_alone(self) -> None:
        stopped = []
        self.window.shutdown_workflow_worker = lambda: stopped.append(True)
        self.window.addCloseEventListener(lambda _widget, event: event.ignore())

        self.assertFalse(self.window.close())

        self.assertEqual(stopped, [])

    def test_listener_runs_before_the_workflow_runner_is_stopped(self) -> None:
        order = []
        self.window.shutdown_workflow_worker = lambda: order.append("stopped")
        self.window.addCloseEventListener(
            lambda _widget, event: (order.append("listener"), event.accept())
        )

        self.assertTrue(self.window.close())

        self.assertEqual(order, ["listener", "stopped"])


if __name__ == "__main__":
    unittest.main()
