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

    def init_workflow_execution(self) -> None:
        """Initialise workflow execution state tracking."""
        self.workflow_execution_count: int = 0
        self.workflow_start_time: float = 0.0
        self.total_workflow_time: float = 0.0
        self.last_execution_time: float = 0.0
        self.execution_results: Dict[Any, Dict[str, Any]] = {}
        self._workflow_worker: Union[WorkflowWorker, None] = None
        self._workflow_sorted_nodes: List[Any] = []

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
        print(f"🚀 Starting workflow execution #{self.workflow_execution_count}...")

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
            self.execution_results[node] = result.variables
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

        print(f"\n{'=' * 60}")
        print("🎯 WORKFLOW EXECUTION SUMMARY")
        print(f"{'=' * 60}")
        print(
            f"Execution #{self.workflow_execution_count} - {status_icon} {status_text}"
        )

        print(f"⏱️  This execution: {current_execution_time:.3f} seconds")
        global_logger.info(f"⏱️  This execution: {current_execution_time:.3f} seconds")
        print(f"📊 Total runs: {self.workflow_execution_count}")
        print(f"📈 Average time: {average_execution:.3f} seconds")
        print(f"🕒 Cumulative time: {self.total_workflow_time:.3f} seconds")
        if not success:
            print("⚠️  Execution failed - check logs for details")
            global_logger.error("Workflow execution failed - check logs for details")
        print(f"{'=' * 60}\n")

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
        print("📊 Workflow execution statistics have been reset")

    def _get_output_variable_names(self, node: Any) -> list[str]:
        """Infer output variable names for a node from the latest execution."""
        node_results = self.execution_results.get(node, {})
        variable_names: list[str] = []

        if hasattr(node, "param"):
            for socket_data in getattr(node, "param", []) or []:
                if not isinstance(socket_data, dict):
                    continue
                var_name = socket_data.get("variable_name")
                if (
                    isinstance(var_name, str)
                    and var_name in node_results
                    and var_name not in variable_names
                ):
                    variable_names.append(var_name)

        content = getattr(node, "content", None)
        if content is not None:
            for attr_name, attr_value in getattr(content, "__dict__", {}).items():
                if not isinstance(attr_value, str) or attr_name == "incoming_variable":
                    continue

                is_output_name = (
                    attr_name == "variable_name"
                    or attr_name.endswith("_variable_name")
                    or attr_name.endswith("_var")
                )
                if (
                    is_output_name
                    and attr_value in node_results
                    and attr_value not in variable_names
                ):
                    variable_names.append(attr_value)

        return variable_names

    def getSocketData(self, node: Any, socket_index: int) -> Any:  # noqa: N802
        """Return the execution result bound to a socket after workflow run."""
        if not self.execution_results:
            print("No execution results available. Run the workflow first.")
            return None

        if node not in self.execution_results:
            print(f"No results found for node {node}")
            return None

        node_results = self.execution_results[node]
        output_variable_names = self._get_output_variable_names(node)

        if 0 <= socket_index < len(output_variable_names):
            return node_results.get(output_variable_names[socket_index])

        if socket_index == 0 and len(node_results) == 1:
            return next(iter(node_results.values()))

        print(f"No socket data found for node {node} at socket index {socket_index}")

        return None
