from __future__ import annotations

import time
from typing import Any, Dict, List, Union

from loguru import logger
from qtpy.QtCore import QTimer

from trigger_designer.core.ExecutionCheck.executor import NodeExecutor
from trigger_designer.qt.helpers import global_logger


class WorkflowExecutionMixin:
    """Mixin providing workflow execution orchestration and statistics tracking."""

    def init_workflow_execution(self) -> None:
        """Initialise workflow execution state tracking."""
        self.workflow_execution_count: int = 0
        self.workflow_start_time: float = 0.0
        self.total_workflow_time: float = 0.0
        self.last_execution_time: float = 0.0
        self.execution_results: Dict[Any, Dict[str, Any]] = {}

    # --- Workflow execution helpers -------------------------------------------------
    def executeWorkflow(self) -> None:  # noqa: N802 (keep Qt naming convention)
        """Run the current workflow sequentially while updating execution visuals."""
        if hasattr(self, "run_button"):
            self.run_button.setEnabled(False)

        connections = self.getNodeConnections()
        sorted_nodes = self.topologicalSort(connections)
        executor = NodeExecutor()

        # Reset node visuals and stored results
        self.execution_results.clear()
        for node in self.getAllNodes():
            node.grNode.resetPen()
            node.grNode.update()

        # Start timing and increment execution counters
        self.workflow_start_time = time.time()
        self.workflow_execution_count += 1

        logger.info("🚀 Starting workflow execution #{}", self.workflow_execution_count)
        print(f"🚀 Starting workflow execution #{self.workflow_execution_count}...")

        self._execute_next_node(sorted_nodes, 0, executor)
        self.getPyFile(sorted_nodes)

    def _execute_next_node(  # noqa: PLR0913 (matching existing signature)
        self,
        nodes: List[Any],
        current_index: int,
        executor: NodeExecutor,
    ) -> None:
        """Execute nodes sequentially with visual transitions."""
        if current_index >= len(nodes):
            QTimer.singleShot(1000, lambda: self._execution_cleanup(success=True))
            return

        node = nodes[current_index]
        node_name = getattr(node, "node_title", node.__class__.__name__)

        node.grNode.setPenExecuting()
        node.grNode.update()

        try:
            result = executor.execute_node(node)
        except Exception as exc:  # pragma: no cover - visual/UI side effects
            error_message = f"Error executing node '{node_name}': {exc}"
            logger.error(error_message)
            global_logger.error(error_message)
            node.grNode.resetPen()
            node.grNode.update()
            self._execution_cleanup(success=False)
            return

        if result.success:
            self.execution_results[node] = result.variables
            node.grNode.setPenExecuted()
            node.grNode.update()
        else:
            error_message = f"Node execution failed for '{node_name}': {result.error}"
            logger.error(error_message)
            global_logger.error(error_message)
            node.grNode.resetPen()
            node.grNode.update()
            self._execution_cleanup(success=False)
            return

        QTimer.singleShot(
            100,
            lambda: self._execute_next_node(nodes, current_index + 1, executor),
        )

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
