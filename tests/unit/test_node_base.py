#!/usr/bin/env python3

import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from qtpy.QtCore import QEvent
from qtpy.QtWidgets import QApplication, QFrame

from trigger_designer.qt.node_base import TriggerChangeHandler


APP = QApplication.instance() or QApplication([])


def test_clear_input_widgets_ignores_deleted_qt_wrappers() -> None:
    handler = TriggerChangeHandler(
        scene=SimpleNamespace(history=SimpleNamespace(storeHistory=lambda *args, **kwargs: None)),
        node=SimpleNamespace(),
    )

    widget = QFrame()
    handler._input_widgets.append(widget)

    widget.deleteLater()
    APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    APP.processEvents()

    handler.clearInputWidgets()

    assert handler._input_widgets == []


def main() -> None:
    test_clear_input_widgets_ignores_deleted_qt_wrappers()
    print("ok")


if __name__ == "__main__":
    main()