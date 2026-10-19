from __future__ import annotations

import time
from typing import Any, Dict, List, Union

from loguru import logger
from qtpy.QtCore import QTimer

from trigger_designer.core.ExecutionCheck.executor import NodeExecutor
from trigger_designer.qt.helpers import global_logger
from trigger_designer.qt.helpers.workflow_worker import WorkflowWorker


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
        if self._workflow_worker is not None and self._workflow_worker.isRunning():
            # A run is already in flight - the GUI thread stays responsive
            # for the whole run now, so this guard is reachable in
            # practice (previously the GUI was blocked, so a second click
            # couldn't happen).
            return

        if hasattr(self, "run_button"):
            self.run_button.setEnabled(False)

        connections = self.getNodeConnections()
        sorted_nodes = self.topologicalSort(connections)
        executor = NodeExecutor()

        # Reset node visuals and stored results
        self.execution_results.clear()
        for node in self.getAllNodes():
            node.markInvalid(False)
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

    def _on_node_started(self, node: Any) -> None:
        """Slot: a node is about to execute (runs on the GUI thread)."""
        node.grNode.setPenExecuting()
        node.grNode.update()

    def _on_node_finished(self, node: Any, result: Any) -> None:
        """Slot: a node finished executing (runs on the GUI thread)."""
        node_name = getattr(node, "node_title", node.__class__.__name__)

        if result.success:
            self.execution_results[node] = self._prune_node_results(
                node, result.variables
            )
            node.grNode.setPenExecuted()
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
        error_message = f"Error executing node '{node_name}': {exc}"
        logger.error(error_message)
        global_logger.error(error_message)
        node.markInvalid()
        node.grNode.setPenError()
        node.grNode.update()

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
