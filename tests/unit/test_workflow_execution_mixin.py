#!/usr/bin/env python3

import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from trigger_designer.qt.helpers import workflow_execution_mixin as workflow_module
from trigger_designer.qt.helpers.workflow_execution_mixin import WorkflowExecutionMixin


class DummyGraphicsNode:
    def __init__(self) -> None:
        self.actions = []

    def setPenExecuting(self) -> None:
        self.actions.append("executing")

    def setPenExecuted(self) -> None:
        self.actions.append("executed")

    def resetPen(self) -> None:
        self.actions.append("reset")

    def update(self) -> None:
        self.actions.append("update")


class DummyWindow(WorkflowExecutionMixin):
    def __init__(self) -> None:
        self.execution_results = {}
        self.cleanup_calls = []

    def _execution_cleanup(self, success: bool = True) -> None:
        self.cleanup_calls.append(success)


def test_execute_next_node_logs_failed_results_to_global_logger() -> None:
    messages = []
    original_global_logger = workflow_module.global_logger
    workflow_module.global_logger = SimpleNamespace(error=messages.append)

    try:
        window = DummyWindow()
        node = SimpleNamespace(node_title="Formula", grNode=DummyGraphicsNode())
        executor = SimpleNamespace(
            execute_node=lambda current_node: SimpleNamespace(
                success=False,
                error='Parser Error: syntax error at or near "AS"',
            )
        )

        window._execute_next_node([node], 0, executor)

        assert window.cleanup_calls == [False]
        assert any("Parser Error" in message for message in messages)
        assert any("Formula" in message for message in messages)
    finally:
        workflow_module.global_logger = original_global_logger


def main() -> None:
    test_execute_next_node_logs_failed_results_to_global_logger()
    print("ok")


if __name__ == "__main__":
    main()