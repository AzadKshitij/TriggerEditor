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


def main() -> None:
    test_workflow_worker_logs_failed_results_to_global_logger()
    test_workflow_worker_records_successful_results()
    test_workflow_worker_reports_unexpected_exceptions()
    print("ok")


if __name__ == "__main__":
    main()
