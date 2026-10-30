"""One cancel entry point: executor latch, worker, listeners, reporting."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy.QtWidgets import QApplication

from trigger_designer.core.ExecutionCheck.executor import NodeExecutor
from trigger_designer.qt.helpers.workflow_execution_mixin import WorkflowExecutionMixin

_APP = QApplication.instance() or QApplication([])


class Recorder:
    def __init__(self, running: bool = True) -> None:
        self.running = running
        self.calls: list[str] = []

    def isRunning(self) -> bool:
        return self.running

    def request_cancel(self) -> None:
        self.calls.append("worker.request_cancel")

    def cancel_execution(self) -> bool:
        self.calls.append("executor.cancel_execution")
        return True


class FakeButton:
    def __init__(self) -> None:
        self.enabled = True
        self.visible = False
        self.tooltip = ""

    def setEnabled(self, value: bool) -> None:
        self.enabled = value

    def setVisible(self, value: bool) -> None:
        self.visible = value

    def setToolTip(self, text: str) -> None:
        self.tooltip = text


class Window(WorkflowExecutionMixin):
    def __init__(self) -> None:
        self.init_workflow_execution()
        self.logged: list[str] = []
        self.cleanup_calls: list[bool] = []
        self.cancel_button = FakeButton()

    def _log_to_dock(self, message: str) -> None:
        self.logged.append(message)

    def _execution_cleanup(self, success: bool = True) -> None:
        self.cleanup_calls.append(success)

    def getPyFile(self, sorted_nodes) -> None:
        pass


def test_cancel_execution_always_sets_the_event() -> None:
    executor = NodeExecutor()
    assert executor.cancel_requested is False
    assert executor.cancel_execution() is False  # nothing is running
    assert executor.cancel_requested is True
    executor.reset_cancel()
    assert executor.cancel_requested is False


def test_execute_node_does_not_clear_a_pending_cancel() -> None:
    class Node:
        content = None

        def get_code(self) -> str:
            return "x = 1"

    executor = NodeExecutor()
    executor.cancel_execution()
    executor.execute_node(Node())
    assert executor.cancel_requested is True


def test_request_run_cancel_sets_worker_executor_session_and_listeners() -> None:
    window = Window()
    shared = Recorder()
    window._workflow_worker = shared
    window._workflow_executor = shared
    session = type("S", (), {"calls": 0})()

    def session_cancel() -> None:
        session.calls += 1

    window._run_session = type(
        "Sess", (), {"request_cancel": staticmethod(session_cancel)}
    )
    heard: list[int] = []
    window.add_cancel_listener(lambda: heard.append(1))

    assert window.request_run_cancel() is True

    assert shared.calls == ["worker.request_cancel", "executor.cancel_execution"]
    assert session.calls == 1
    assert heard == [1]
    assert window._run_cancelled is True
    assert window.cancel_button.enabled is False
    assert "Cancelling" in window.cancel_button.tooltip
    assert any("Cancel requested" in line for line in window.logged)


def test_request_run_cancel_idle_is_a_noop_but_calls_listeners() -> None:
    window = Window()
    heard: list[int] = []
    window.add_cancel_listener(lambda: heard.append(1))
    window.add_cancel_listener(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert window.request_run_cancel() is False
    assert heard == [1]
    assert window._run_cancelled is False


def test_deleted_worker_wrapper_counts_as_idle() -> None:
    class Dead:
        def isRunning(self) -> bool:
            raise RuntimeError("wrapped C/C++ object has been deleted")

    window = Window()
    window._workflow_worker = Dead()
    assert window.request_run_cancel() is False


def test_cancelled_run_is_reported_as_cancelled() -> None:
    window = Window()
    window._run_cancelled = True
    window._on_workflow_finished(False)
    assert window.cleanup_calls == [False]  # immediately, no QTimer


def test_cancel_after_the_last_node_does_not_mark_a_complete_run() -> None:
    """The worker decides: a cancel that arrived too late cancelled nothing."""
    window = Window()
    window._run_cancelled = True
    window._workflow_worker = type(
        "W", (), {"cancelled": False, "isFinished": lambda self: True}
    )()
    from qtpy.QtCore import QTimer

    scheduled: list[int] = []
    original = QTimer.singleShot
    QTimer.singleShot = staticmethod(lambda ms, fn: scheduled.append(ms))
    try:
        window._on_workflow_finished(True)
    finally:
        QTimer.singleShot = original
    assert scheduled == [1000]
    assert window._run_cancelled is False


def test_cleanup_logs_run_cancelled() -> None:
    class Node:
        def isInvalid(self) -> bool:
            return True

    class Full(Window):
        _execution_cleanup = WorkflowExecutionMixin._execution_cleanup

        def getAllNodes(self):
            return []

    window = Full()
    window._run_cancelled = True
    window._execution_cleanup(success=False)
    assert any(line == "Run cancelled" for line in window.logged)
    assert not any("Execution failed" in line for line in window.logged)
    assert any("CANCELLED" in line for line in window.logged)
