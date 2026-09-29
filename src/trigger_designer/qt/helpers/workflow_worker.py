"""Background-thread runner for "Run Workflow".

Previously the GUI thread itself executed every node (via a QTimer.singleShot
chain in workflow_execution_mixin.py), blocking synchronously for the full
duration of each node's computation. WorkflowWorker moves that whole loop onto
one persistent background QThread instead, so the GUI stays responsive for
the entire run. It never touches Qt widgets/graphics items directly (that
would be unsafe off the GUI thread) - it only emits signals, which callers
connect to slots that do the actual pen-color/bookkeeping work.

Calling `run()` directly (instead of `start()`) executes it synchronously on
the caller's own thread, with signals dispatched as ordinary direct calls -
useful for tests that don't need a real OS thread or event loop.
"""

from __future__ import annotations

from typing import Any

from qtpy.QtCore import QThread, Signal

from trigger_designer.core.ExecutionCheck.executor import NodeExecutor


class WorkflowWorker(QThread):
    """Runs a topologically sorted node list through one NodeExecutor."""

    nodeStarted = Signal(object)  # node
    nodeFinished = Signal(object, object)  # node, ExecutionResult
    nodeErrored = Signal(object, object)  # node, Exception
    workflowFinished = Signal(bool)  # overall success

    def __init__(self, nodes: list[Any], executor: NodeExecutor, parent=None) -> None:
        super().__init__(parent)
        self._nodes = nodes
        self._executor = executor
        self._cancel_requested = False

    def request_cancel(self) -> None:
        """Cooperative cancellation: takes effect before the next node."""
        self._cancel_requested = True

    def run(self) -> None:
        success = True

        for node in self._nodes:
            if self._cancel_requested:
                success = False
                break

            self.nodeStarted.emit(node)

            try:
                result = self._executor.execute_node(node)
            except (
                Exception
            ) as exc:  # pragma: no cover - defensive, mirrors old behavior
                self.nodeErrored.emit(node, exc)
                success = False
                break

            self.nodeFinished.emit(node, result)

            if not result.success:
                success = False
                break

        self.workflowFinished.emit(success)
