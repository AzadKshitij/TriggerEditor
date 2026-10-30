"""The Cancel button: visible only while a run is in flight."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from qtpy.QtCore import QSize

from trigger_designer.qt.design_window import CANVAS_ICON_SIZE, TriggerSubWindow
from trigger_designer.qt.helpers import workflow_execution_mixin as mixin_module


@pytest.fixture()
def window(qtbot):
    win = TriggerSubWindow()
    qtbot.addWidget(win)
    win.show()
    return win


def test_cancel_button_is_hidden_until_a_run_starts(window) -> None:
    assert window.cancel_button.isHidden()
    assert window.run_button.isVisible()


def test_cancel_button_follows_the_design_system(window) -> None:
    button = window.cancel_button
    assert button.objectName() == "IconButton"
    assert button.text() == ""
    assert button.size() == QSize(30, 30)
    assert button.iconSize() == QSize(CANVAS_ICON_SIZE, CANVAS_ICON_SIZE)
    assert button.toolTip()
    assert button.accessibleName() == button.toolTip()
    assert not button.icon().isNull()
    assert not button.icon().pixmap(QSize(16, 16)).isNull()


def test_cancel_takes_the_place_of_run(window) -> None:
    assert window.cancel_button.pos() == window.run_button.pos()
    window._show_run_controls(True)
    assert window.cancel_button.isVisible() and window.cancel_button.isEnabled()
    assert window.run_button.isHidden()
    window._show_run_controls(False)
    assert window.run_button.isVisible() and window.run_button.isEnabled()
    assert window.cancel_button.isHidden()


def test_clicking_cancel_without_a_run_is_a_noop(window) -> None:
    window._show_run_controls(True)
    window.cancel_button.click()
    assert window._run_cancelled is False


def test_clicking_cancel_with_a_running_worker_requests_cancel_once(window) -> None:
    class Worker:
        calls = 0

        def isRunning(self) -> bool:
            return True

        def request_cancel(self) -> None:
            Worker.calls += 1

    window._workflow_worker = Worker()
    window._show_run_controls(True)
    window.cancel_button.click()
    assert Worker.calls == 1
    assert not window.cancel_button.isEnabled()
    assert "Cancelling" in window.cancel_button.toolTip()
    assert window._run_cancelled is True
    window._workflow_worker = None


class _GraphicsNode:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def __getattr__(self, name: str):
        def record(*_args, **_kwargs) -> None:
            self.actions.append(name)

        return record


class _SleepyNode:
    content = None

    def __init__(self, title: str, code: str) -> None:
        self.node_title = title
        self.code = code
        self.grNode = _GraphicsNode()
        self.inputs: list = []

    def get_code(self) -> str:
        return self.code

    def markInvalid(self, *_args) -> None:
        pass

    def isInvalid(self) -> bool:
        return False


def test_cancel_during_a_real_run_skips_the_remaining_nodes(
    qtbot, window, monkeypatch
) -> None:
    from qtpy.QtCore import QCoreApplication, QEvent

    first = _SleepyNode("first", "import time\ntime.sleep(0.3)\nx = 1\n")
    second = _SleepyNode("second", "y = 2\n")
    third = _SleepyNode("third", "z = 3\n")
    nodes = [first, second, third]
    monkeypatch.setattr(mixin_module, "topological_order", lambda scene: list(nodes))
    monkeypatch.setattr(window, "getAllNodes", lambda: nodes)
    monkeypatch.setattr(window, "getPyFile", lambda *_a, **_k: "")
    monkeypatch.setattr(window, "doEvalOutputs", lambda *_a, **_k: None, raising=False)

    with qtbot.waitSignal(window.executionResultsChanged, timeout=20_000):
        window.executeWorkflow()
        worker = window._workflow_worker
        assert worker is not None
        assert window.cancel_button.isVisible()
        qtbot.waitUntil(lambda: "setPenExecuting" in first.grNode.actions, timeout=5000)
        assert window.request_run_cancel() is True
    assert worker.wait(20_000)
    QCoreApplication.sendPostedEvents(worker, QEvent.Type.DeferredDelete)

    assert worker.cancelled is True
    assert "setPenExecuting" not in second.grNode.actions
    assert "setPenExecuting" not in third.grNode.actions
    assert first in window.execution_results
    assert second not in window.execution_results
    assert window.run_button.isEnabled() and window.run_button.isVisible()
    assert window.cancel_button.isHidden()
