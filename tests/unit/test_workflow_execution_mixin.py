#!/usr/bin/env python3

import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from qtpy.QtWidgets import QApplication

from trigger_designer.qt.helpers import workflow_execution_mixin as workflow_module
from trigger_designer.qt.helpers.workflow_execution_mixin import WorkflowExecutionMixin
from trigger_designer.qt.helpers.workflow_worker import WorkflowWorker

_APP = QApplication.instance() or QApplication([])


class FakeNode:
    """Stands in for a real TriggerNode - a plain class (hashable by
    identity, unlike types.SimpleNamespace, which defines __eq__ and is
    therefore unhashable) since nodes are used as execution_results dict
    keys."""

    def __init__(self, node_title: str, grNode: "DummyGraphicsNode") -> None:
        self.node_title = node_title
        self.grNode = grNode

    def markInvalid(self, *args, **kwargs) -> None:
        pass


class DummyGraphicsNode:
    def __init__(self) -> None:
        self.actions = []

    def setPenExecuting(self) -> None:
        self.actions.append("executing")

    def setPenExecuted(self) -> None:
        self.actions.append("executed")

    def setPenError(self) -> None:
        self.actions.append("error")

    def resetPen(self) -> None:
        self.actions.append("reset")

    def update(self) -> None:
        self.actions.append("update")


class DummyWindow(WorkflowExecutionMixin):
    def __init__(self) -> None:
        self.execution_results = {}
        self.cleanup_calls = []
        self.py_file_calls = []
        self._workflow_worker = None
        self._workflow_sorted_nodes = []

    def _execution_cleanup(self, success: bool = True) -> None:
        self.cleanup_calls.append(success)

    def getPyFile(self, sorted_nodes) -> None:
        self.py_file_calls.append(list(sorted_nodes))


def _run_worker_synchronously(window: DummyWindow, nodes, executor) -> None:
    """Drive a WorkflowWorker's run() body directly on the current thread.

    Calling run() (instead of start()) executes it synchronously without a
    real OS thread or Qt event loop - signals connected to plain callables
    on the same thread dispatch as ordinary direct calls, which keeps this
    test deterministic.
    """
    window._workflow_sorted_nodes = nodes
    worker = WorkflowWorker(nodes, executor)
    worker.nodeStarted.connect(window._on_node_started)
    worker.nodeFinished.connect(window._on_node_finished)
    worker.nodeErrored.connect(window._on_node_errored)
    worker.workflowFinished.connect(window._on_workflow_finished)
    worker.run()


def test_workflow_worker_logs_failed_results_to_global_logger() -> None:
    messages = []
    original_global_logger = workflow_module.global_logger
    workflow_module.global_logger = SimpleNamespace(error=messages.append)

    try:
        window = DummyWindow()
        node = FakeNode("Formula", DummyGraphicsNode())
        executor = SimpleNamespace(
            execute_node=lambda current_node: SimpleNamespace(
                success=False,
                error='Parser Error: syntax error at or near "AS"',
            )
        )

        _run_worker_synchronously(window, [node], executor)

        # Failure path is not deferred behind the success-only 1s cosmetic
        # QTimer delay, so cleanup(False) must have already run.
        assert window.cleanup_calls == [False]
        assert window.py_file_calls == [[node]]
        assert any("Parser Error" in message for message in messages)
        assert any("Formula" in message for message in messages)
        assert "error" in node.grNode.actions
    finally:
        workflow_module.global_logger = original_global_logger


def test_workflow_worker_records_successful_results() -> None:
    window = DummyWindow()
    node = FakeNode("Select", DummyGraphicsNode())
    executor = SimpleNamespace(
        execute_node=lambda current_node: SimpleNamespace(
            success=True,
            variables={"out": 1},
        )
    )

    _run_worker_synchronously(window, [node], executor)

    assert window.execution_results[node] == {"out": 1}
    assert "executed" in node.grNode.actions
    assert window.py_file_calls == [[node]]
    # Success path defers cleanup via QTimer.singleShot(1000, ...), which
    # needs a running event loop to fire - not expected synchronously here.
    assert window.cleanup_calls == []


def test_workflow_worker_prunes_results_to_declared_outputs() -> None:
    import polars as pl

    window = DummyWindow()
    node = FakeNode("Select", DummyGraphicsNode())
    node.param = [{"data": None, "variable_name": "out"}]
    node.value = [{"data": None, "variable_name": "out"}]
    frame = pl.DataFrame({"x": [1]})

    executor = SimpleNamespace(
        execute_node=lambda current_node: SimpleNamespace(
            success=True,
            variables={"out": 1, "df_for_duck": frame, "pl": pl},
        )
    )

    _run_worker_synchronously(window, [node], executor)

    # Only the declared output survives; the temp frame and module do not.
    assert window.execution_results[node] == {"out": 1}


def test_workflow_worker_keeps_previewable_frames_without_declarations() -> None:
    import polars as pl

    window = DummyWindow()
    node = FakeNode("Legacy", DummyGraphicsNode())
    frame = pl.DataFrame({"x": [1]})

    executor = SimpleNamespace(
        execute_node=lambda current_node: SimpleNamespace(
            success=True,
            variables={"temp": 5, "result": frame, "pl": pl},
        )
    )

    _run_worker_synchronously(window, [node], executor)

    # No declared outputs: keep the previewable frame, drop the scratch value.
    assert window.execution_results[node] == {"result": frame}


def test_workflow_worker_reports_unexpected_exceptions() -> None:
    messages = []
    original_global_logger = workflow_module.global_logger
    workflow_module.global_logger = SimpleNamespace(error=messages.append)

    try:
        window = DummyWindow()
        node = FakeNode("Join", DummyGraphicsNode())

        def _raise(_node):
            raise RuntimeError("boom")

        executor = SimpleNamespace(execute_node=_raise)

        _run_worker_synchronously(window, [node], executor)

        assert window.cleanup_calls == [False]
        assert any("boom" in message for message in messages)
        assert any("Join" in message for message in messages)
        assert "error" in node.grNode.actions
    finally:
        workflow_module.global_logger = original_global_logger


class FakeWorker:
    """Minimal QThread stand-in for the shutdown path."""

    def __init__(self, running: bool = True, stops: bool = True) -> None:
        self.running = running
        self.stops = stops
        self.cancelled = False
        self.waited_ms: int | None = None
        self.nodeStarted = FakeSignal()
        self.nodeFinished = FakeSignal()
        self.nodeErrored = FakeSignal()
        self.workflowFinished = FakeSignal()

    def isRunning(self) -> bool:
        return self.running

    def request_cancel(self) -> None:
        self.cancelled = True

    def wait(self, timeout_ms: int) -> bool:
        self.waited_ms = timeout_ms
        if self.stops:
            self.running = False
        return self.stops


class FakeSignal:
    def __init__(self) -> None:
        self.disconnected = False

    def disconnect(self) -> None:
        self.disconnected = True


def test_shutdown_workflow_worker_cancels_waits_and_detaches() -> None:
    window = DummyWindow()
    worker = FakeWorker()
    window._workflow_worker = worker

    assert window.shutdown_workflow_worker(1234) is True

    assert worker.cancelled is True
    assert worker.waited_ms == 1234
    assert window._workflow_worker is None
    assert worker.nodeStarted.disconnected
    assert worker.nodeFinished.disconnected
    assert worker.nodeErrored.disconnected
    assert worker.workflowFinished.disconnected


def test_shutdown_workflow_worker_without_a_run_is_a_noop() -> None:
    window = DummyWindow()

    assert window.shutdown_workflow_worker() is True
    assert window._workflow_worker is None


def test_shutdown_keeps_a_stuck_worker_alive_instead_of_destroying_it() -> None:
    window = DummyWindow()
    worker = FakeWorker(stops=False)
    window._workflow_worker = worker

    try:
        assert window.shutdown_workflow_worker(10) is False
        assert window._workflow_worker is None
        assert worker in workflow_module._ORPHANED_WORKERS
    finally:
        workflow_module._ORPHANED_WORKERS.discard(worker)


def test_wait_for_orphaned_workers_releases_stopped_threads() -> None:
    worker = FakeWorker(stops=True)
    workflow_module._ORPHANED_WORKERS.add(worker)

    try:
        assert workflow_module.wait_for_orphaned_workflow_workers(0) is True
        assert worker not in workflow_module._ORPHANED_WORKERS
    finally:
        workflow_module._ORPHANED_WORKERS.clear()


def main() -> None:
    test_workflow_worker_logs_failed_results_to_global_logger()
    test_workflow_worker_records_successful_results()
    test_workflow_worker_prunes_results_to_declared_outputs()
    test_workflow_worker_keeps_previewable_frames_without_declarations()
    test_workflow_worker_reports_unexpected_exceptions()
    test_shutdown_workflow_worker_cancels_waits_and_detaches()
    test_shutdown_workflow_worker_without_a_run_is_a_noop()
    test_shutdown_keeps_a_stuck_worker_alive_instead_of_destroying_it()
    test_wait_for_orphaned_workers_releases_stopped_threads()
    print("ok")


if __name__ == "__main__":
    main()
