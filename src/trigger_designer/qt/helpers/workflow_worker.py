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

import threading
from collections.abc import Mapping, Sequence
from typing import Any

from qtpy.QtCore import QThread, Signal

from trigger_designer.core.ExecutionCheck.executor import NodeExecutor
from trigger_designer.core.ExecutionCheck.run_loop import LoopOutcome, run_nodes


class WorkflowWorker(QThread):
    """Runs a topologically sorted node list through one NodeExecutor.

    The loop itself is :func:`run_nodes`; this class only turns its callbacks
    into Qt signals, so a headless runner shares identical semantics.
    """

    nodeStarted = Signal(object)  # node
    nodeFinished = Signal(object, object)  # node, ExecutionResult
    nodeErrored = Signal(object, object)  # node, Exception
    nodeSkipped = Signal(object, object)  # node, blocker (None = cancelled)
    workflowFinished = Signal(bool)  # overall success

    def __init__(
        self,
        nodes: list[Any],
        executor: NodeExecutor,
        parent=None,
        *,
        continue_on_error: bool = False,
        upstream: Mapping[Any, Sequence[Any]] | None = None,
    ) -> None:
        super().__init__(parent)
        self._nodes = nodes
        self._executor = executor
        self._continue = continue_on_error
        self._upstream = upstream
        self._cancel = threading.Event()
        #: True once ``run`` ended because of a cancel request.
        self.cancelled = False
        #: The loop's result, set just before ``workflowFinished`` is emitted.
        self.outcome: LoopOutcome | None = None

    @property
    def _cancel_requested(self) -> bool:
        return self._cancel.is_set()

    def request_cancel(self) -> None:
        """Cooperative cancellation: takes effect before the next node."""
        self._cancel.set()

    def run(self) -> None:
        try:
            self._run()
        finally:
            # The executor is per run: release its pooled thread here, on the
            # worker thread, so the GUI never waits on it.
            shutdown = getattr(self._executor, "shutdown", None)
            if callable(shutdown):
                shutdown()

    def _run(self) -> None:
        outcome = run_nodes(
            self._nodes,
            self._executor,
            continue_on_error=self._continue,
            upstream=self._upstream,
            cancel=self._cancel,
            on_node_started=self.nodeStarted.emit,
            on_node_finished=self.nodeFinished.emit,
            on_node_errored=self.nodeErrored.emit,
            on_node_skipped=self.nodeSkipped.emit,
        )
        self.outcome = outcome
        self.cancelled = outcome.cancelled
        self.workflowFinished.emit(outcome.success)
