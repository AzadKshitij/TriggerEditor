from __future__ import annotations

import time
from typing import Any, Dict, List, Union

from loguru import logger
from nodeeditor.node_graph import GraphCycleError, topological_order
from qtpy.QtCore import QTimer

from trigger_designer.core.errors import translate_exception
from trigger_designer.core.ExecutionCheck.executor import NodeExecutor
from trigger_designer.qt.helpers import global_logger
from trigger_designer.qt.helpers.edge_validators import (
    cycle_message,
    select_cycle_edges,
)
from trigger_designer.qt.helpers.error_context import build_context, build_enrich_job
from trigger_designer.qt.helpers.error_enricher import start_enrichment
from trigger_designer.qt.helpers.workflow_worker import WorkflowWorker
from trigger_designer.qt.preferences import get_preferences

#: Runs whose window closed before ``run()`` returned. Qt aborts the process
#: when a running QThread is destroyed, so a reference is held here until the
#: thread stops (see ``wait_for_orphaned_workflow_workers``).
_ORPHANED_WORKERS: set[WorkflowWorker] = set()


def wait_for_orphaned_workflow_workers(timeout_ms: int = 5000) -> bool:
    """Wait for runs that outlived their window; True when none remain."""
    deadline = time.monotonic() + timeout_ms / 1000.0
    for worker in list(_ORPHANED_WORKERS):
        remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
        try:
            stopped = worker.wait(remaining_ms)
        except RuntimeError:
            # The C++ thread object was already deleted; nothing to wait for.
            stopped = True
        if stopped:
            _ORPHANED_WORKERS.discard(worker)
    return not _ORPHANED_WORKERS


class WorkflowExecutionMixin:
    """Mixin providing workflow execution orchestration and statistics tracking."""

    #: ``TriggerSubWindow`` shadows this with a real ``Signal``; this mixin is
    #: not a QObject (tests instantiate it directly), so announcing the end of
    #: a run has to stay optional.
    executionResultsChanged = None

    def init_workflow_execution(self) -> None:
        """Initialise workflow execution state tracking."""
        self.workflow_execution_count: int = 0
        self.workflow_start_time: float = 0.0
        self.total_workflow_time: float = 0.0
        self.last_execution_time: float = 0.0
        self.execution_results: Dict[Any, Dict[str, Any]] = {}
        self._workflow_worker: Union[WorkflowWorker, None] = None
        self._workflow_sorted_nodes: List[Any] = []

    def _log_to_dock(self, message: str) -> None:
        """Report a message in the Logging dock.

        The dock is the console replacement: a windowed build has no
        terminal to print to, so the run summary and the "no results"
        warnings have to go where the user can read them. Tests drive this
        mixin directly, without a dock, so the call is optional.
        """
        log_info = getattr(self, "logInfo", None)
        if callable(log_info):
            log_info(message)
        else:
            logger.info(message)

    # --- Workflow execution helpers -------------------------------------------------
    def executeWorkflow(self) -> None:  # noqa: N802 (keep Qt naming convention)
        """Run the current workflow on a single background thread while
        updating execution visuals from signals it emits."""
        if self._workflow_worker_is_running():
            # A run is already in flight - the GUI thread stays responsive
            # for the whole run now, so this guard is reachable in
            # practice (previously the GUI was blocked, so a second click
            # couldn't happen).
            return

        if hasattr(self, "run_button"):
            self.run_button.setEnabled(False)

        try:
            # Run reads values, so any coalesced edge edit must be settled
            # before the ordering and code generation below.
            coordinator = getattr(self.scene, "evaluator", None)
            if coordinator is not None:
                coordinator.flush_now()
            sorted_nodes = topological_order(self.scene)
        except GraphCycleError as exc:
            # Never leave the Run button disabled because the graph cannot be
            # ordered. The selected edges make the loop visible; the message
            # uses the TD-CLI-004 wording without inventing a node-level error.
            if hasattr(self, "run_button"):
                self.run_button.setEnabled(True)
            select_cycle_edges(self.scene, exc)
            message = cycle_message(exc)
            logger.warning(message)
            self._log_to_dock(message)
            return
        executor = NodeExecutor()

        # Reset node visuals and stored results
        self.execution_results.clear()
        problems = getattr(self, "problems", None)
        if problems is not None:
            problems.clear_source("run")
        for node in self.getAllNodes():
            node.markInvalid(False)
            clear = getattr(node, "clear_error", None)
            if callable(clear):
                clear("run")
            node.grNode.resetPen()
            node.grNode.update()

        # Start timing and increment execution counters
        self.workflow_start_time = time.time()
        self.workflow_execution_count += 1

        logger.info("🚀 Starting workflow execution #{}", self.workflow_execution_count)
        self._log_to_dock(
            f"🚀 Starting workflow execution #{self.workflow_execution_count}..."
        )

        self._workflow_sorted_nodes = sorted_nodes

        worker = WorkflowWorker(sorted_nodes, executor)
        worker.nodeStarted.connect(self._on_node_started)
        worker.nodeFinished.connect(self._on_node_finished)
        worker.nodeErrored.connect(self._on_node_errored)
        worker.workflowFinished.connect(self._on_workflow_finished)
        worker.finished.connect(worker.deleteLater)
        self._workflow_worker = worker
        worker.start()

    def _workflow_worker_is_running(self) -> bool:
        """Whether a run is in flight, tolerating a deleted Qt wrapper."""
        worker = self._workflow_worker
        if worker is None:
            return False
        try:
            return worker.isRunning()
        except RuntimeError:
            self._workflow_worker = None
            return False

    def shutdown_workflow_worker(self, timeout_ms: int = 5000) -> bool:
        """Cancel the current run and wait for its thread to stop.

        Closing a window while ``run()`` is executing must not let Qt destroy
        the QThread: that is a ``qFatal`` abort, and a thread inside Polars or
        DuckDB can fault as an access violation instead. Neither raises a
        Python exception, so waiting is the only safe way out. Cancellation is
        cooperative (checked before the next node), so a node already in
        flight is bounded by its own execution timeout.

        Returns ``True`` when the thread has stopped.
        """
        worker = self._workflow_worker
        self._workflow_worker = None
        if worker is None:
            return True

        try:
            if not worker.isRunning():
                return True
            worker.request_cancel()
            # Detach the UI before waiting: queued nodeFinished /
            # workflowFinished signals must not repaint a closing window.
            for signal in (
                worker.nodeStarted,
                worker.nodeFinished,
                worker.nodeErrored,
                worker.workflowFinished,
            ):
                try:
                    signal.disconnect()
                except (RuntimeError, TypeError):
                    pass
            if worker.wait(timeout_ms):
                return True
        except RuntimeError:
            # The C++ thread object is already gone; nothing left to wait for.
            return True

        # Still running. Hold the reference so teardown cannot destroy it
        # mid-run; ``wait_for_orphaned_workflow_workers`` waits once more
        # after the event loop has stopped.
        _ORPHANED_WORKERS.add(worker)
        logger.warning(
            "Workflow thread still running {} ms after cancel; "
            "keeping it alive until it stops",
            timeout_ms,
        )
        return False

    def _on_node_started(self, node: Any) -> None:
        """Slot: a node is about to execute (runs on the GUI thread)."""
        node.grNode.setPenExecuting()
        node.grNode.update()

    def _on_node_finished(self, node: Any, result: Any) -> None:
        """Slot: a node finished executing (runs on the GUI thread)."""
        node_name = getattr(node, "node_title", node.__class__.__name__)

        if result.success:
            clear = getattr(node, "clear_error", None)
            if callable(clear):
                clear("run")
            self.execution_results[node] = self._prune_node_results(
                node, result.variables
            )
            node.grNode.setPenExecuted()
            node.grNode.update()
        elif callable(getattr(node, "set_error", None)):
            logger.debug("Run failed for node {}", node_name)
            error = translate_exception(
                getattr(result, "exception", None) or result.error,
                node=node,
                phase="run",
                ctx=build_context(node, self, "run"),
                redact=bool(get_preferences().get("errors/redact_values", False)),
                traceback_text=getattr(result, "traceback_text", ""),
            )
            node.set_error(error, "run")
            self._start_error_enrichment(node, error)
            node.markInvalid()
            node.grNode.setPenError()
            node.grNode.update()
        else:
            error_message = f"Node execution failed for '{node_name}': {result.error}"
            logger.error(error_message)
            global_logger.error(error_message)
            node.markInvalid()
            node.grNode.setPenError()
            node.grNode.update()

    def _on_node_errored(self, node: Any, exc: Exception) -> None:
        """Slot: node raised unexpectedly outside NodeExecutor's own error
        handling (runs on the GUI thread)."""
        node_name = getattr(node, "node_title", node.__class__.__name__)
        if callable(getattr(node, "set_error", None)):
            logger.debug("Unexpected error for node {}", node_name)
            error = translate_exception(
                exc,
                node=node,
                phase="run",
                ctx=build_context(node, self, "run"),
                redact=bool(get_preferences().get("errors/redact_values", False)),
            )
            node.set_error(error, "run")
            self._start_error_enrichment(node, error)
        else:
            error_message = f"Error executing node '{node_name}': {exc}"
            logger.error(error_message)
            global_logger.error(error_message)
        node.markInvalid()
        node.grNode.setPenError()
        node.grNode.update()

    def _start_error_enrichment(self, node: Any, error) -> None:
        try:
            job = build_enrich_job(node, self, error, "run")
            start_enrichment(
                job,
                lambda result, failed=node: self._apply_enrichment(failed, result),
                store=getattr(self, "problems", None),
            )
        except Exception:  # noqa: BLE001, S110 - enrichment is optional
            pass

    def _apply_enrichment(self, node: Any, result) -> None:
        clear = getattr(node, "clear_error", None)
        if callable(clear):
            clear("run")
        culprit_id = getattr(result, "culprit_node_id", None)
        culprit = None
        if culprit_id is not None:
            culprit = next(
                (
                    item
                    for item in self.getAllNodes()
                    if getattr(item, "id", None) == culprit_id
                ),
                None,
            )
        if culprit is not None and culprit is not node:
            culprit_set = getattr(culprit, "set_error", None)
            if callable(culprit_set):
                culprit_set(result.root, "run")
            node_set = getattr(node, "set_error", None)
            if callable(node_set) and result.knock_on is not None:
                node_set(result.knock_on, "run")
        else:
            node_set = getattr(node, "set_error", None)
            if callable(node_set):
                node_set(result.root, "run")

    def _on_workflow_finished(self, success: bool) -> None:
        """Slot: the worker thread's run() has returned (runs on the GUI
        thread, since Qt auto-queues a cross-thread signal emission)."""
        # Drop our reference now, before the worker's own `finished` signal
        # (queued right behind this one) triggers deleteLater() - querying
        # a deleted QThread's isRunning() on the next Run click raises
        # "wrapped C/C++ object ... has been deleted".
        self._workflow_worker = None
        self.getPyFile(self._workflow_sorted_nodes)

        if success:
            QTimer.singleShot(1000, lambda: self._execution_cleanup(success=True))
        else:
            self._execution_cleanup(success=False)

        problems = getattr(self, "problems", None)
        count = problems.count("error", roots_only=True) if problems else 0
        if count:
            self._log_to_dock(f"Run finished with {count} problem(s).")
            raiser = getattr(self, "on_run_problems", None)
            if callable(raiser):
                try:
                    raiser()
                except Exception:  # noqa: BLE001, S110 - showing a dock must not fail
                    pass

        if self.executionResultsChanged is not None:
            self.executionResultsChanged.emit()

    def _execution_cleanup(self, success: bool = True) -> None:
        """Handle workflow cleanup, statistics, and visual reset."""
        workflow_end_time = time.time()
        current_execution_time = workflow_end_time - self.workflow_start_time
        self.last_execution_time = current_execution_time
        self.total_workflow_time += current_execution_time

        average_execution = (
            self.total_workflow_time / self.workflow_execution_count
            if self.workflow_execution_count > 0
            else 0.0
        )

        status_icon = "✅" if success else "❌"
        status_text = "COMPLETED" if success else "FAILED"

        logger.info(
            "{} Workflow execution #{} {}!",
            status_icon,
            self.workflow_execution_count,
            status_text.lower(),
        )
        logger.info("⏱️  Execution time: {:.3f} seconds", current_execution_time)
        logger.info("📊 Total executions: {}", self.workflow_execution_count)
        logger.info("📈 Average execution time: {:.3f} seconds", average_execution)
        logger.info("🕒 Total workflow time: {:.3f} seconds", self.total_workflow_time)

        summary = (
            f"🎯 WORKFLOW EXECUTION SUMMARY — "
            f"execution #{self.workflow_execution_count}, "
            f"{status_icon} {status_text}"
        )
        self._log_to_dock(summary)
        self._log_to_dock(f"⏱️  This execution: {current_execution_time:.3f} seconds")
        global_logger.info(f"⏱️  This execution: {current_execution_time:.3f} seconds")
        self._log_to_dock(f"📊 Total runs: {self.workflow_execution_count}")
        self._log_to_dock(f"📈 Average time: {average_execution:.3f} seconds")
        self._log_to_dock(f"🕒 Cumulative time: {self.total_workflow_time:.3f} seconds")
        if not success:
            self._log_to_dock("⚠️  Execution failed - check logs for details")
            global_logger.error("Workflow execution failed - check logs for details")

        for node in self.getAllNodes():
            if node.isInvalid():
                node.grNode.update()
                continue
            node.grNode.resetPen()
            node.grNode.update()

        if hasattr(self, "run_button"):
            self.run_button.setEnabled(True)

    # --- Statistics helpers ---------------------------------------------------------
    def get_workflow_statistics(self) -> Dict[str, Union[int, float]]:
        """Return aggregated workflow execution statistics."""
        average_execution = (
            self.total_workflow_time / self.workflow_execution_count
            if self.workflow_execution_count > 0
            else 0.0
        )

        return {
            "total_executions": self.workflow_execution_count,
            "total_time": self.total_workflow_time,
            "average_execution_time": average_execution,
            "last_execution_time": self.last_execution_time,
        }

    def reset_workflow_statistics(self) -> None:
        """Reset accumulated workflow statistics."""
        self.workflow_execution_count = 0
        self.total_workflow_time = 0.0
        self.last_execution_time = 0.0
        self.execution_results.clear()
        logger.info("📊 Workflow statistics reset")
        self._log_to_dock("📊 Workflow execution statistics have been reset")

    def _declared_output_variable_names(self, node: Any) -> list[str]:
        """Output variable names a node declares, in socket order.

        Reads ``node.param`` (what the node stored after its last eval), the
        evaluated ``node.value`` output list, then the content's own
        ``variable_name`` / ``*_variable_name`` / ``*_var`` attributes. Unlike
        :meth:`_get_output_variable_names` this does not need the run results,
        so it can also drive pruning.
        """
        variable_names: list[str] = []

        def add(name: Any) -> None:
            if isinstance(name, str) and name and name not in variable_names:
                variable_names.append(name)

        if hasattr(node, "param"):
            for socket_data in getattr(node, "param", []) or []:
                if isinstance(socket_data, dict):
                    add(socket_data.get("variable_name"))

        value = getattr(node, "value", None)
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    add(entry.get("variable_name"))

        content = getattr(node, "content", None)
        if content is not None:
            for attr_name, attr_value in getattr(content, "__dict__", {}).items():
                if not isinstance(attr_value, str) or attr_name == "incoming_variable":
                    continue

                is_output_name = attr_name == "variable_name" or attr_name.endswith(
                    ("_variable_name", "_var")
                )
                if is_output_name:
                    add(attr_value)

        return variable_names

    def _prune_node_results(
        self, node: Any, variables: dict[str, Any]
    ) -> dict[str, Any]:
        """Keep only a node's declared outputs from its run namespace.

        ``result.variables`` is the whole executed namespace, so it also holds
        temporary frames (``df_for_duck``), imported modules and closed DuckDB
        handles. ``execution_results`` only feeds socket lookups and the Data
        Preview, so keep the declared outputs and drop the rest. A node that
        declares nothing (older content) falls back to the previewable frames,
        and to the full namespace only when even that finds nothing.
        """
        declared = self._declared_output_variable_names(node)
        pruned = {name: variables[name] for name in declared if name in variables}
        if pruned:
            return pruned

        previewable = {
            name: value
            for name, value in variables.items()
            if self._is_previewable_value(value)
        }
        return previewable or variables

    @staticmethod
    def _is_previewable_value(value: Any) -> bool:
        """True for the values the Data Preview can render."""
        from trigger_designer.qt.models.preview_sampling import is_previewable

        return is_previewable(value)

    def _get_output_variable_names(self, node: Any) -> list[str]:
        """Output variable names for a node, restricted to stored results."""
        node_results = self.execution_results.get(node, {})
        return [
            name
            for name in self._declared_output_variable_names(node)
            if name in node_results
        ]

    def getSocketData(self, node: Any, socket_index: int) -> Any:  # noqa: N802
        """Return the execution result bound to a socket after workflow run."""
        if not self.execution_results:
            self._log_to_dock("No execution results available. Run the workflow first.")
            return None

        if node not in self.execution_results:
            self._log_to_dock(f"No results found for node {node}")
            return None

        node_results = self.execution_results[node]
        output_variable_names = self._get_output_variable_names(node)

        if 0 <= socket_index < len(output_variable_names):
            return node_results.get(output_variable_names[socket_index])

        if socket_index == 0 and len(node_results) == 1:
            return next(iter(node_results.values()))

        self._log_to_dock(
            f"No socket data found for node {node} at socket index {socket_index}"
        )

        return None
