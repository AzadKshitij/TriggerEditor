"""Enhanced Python code executor for TriggerEditor nodes.

This module provides a robust Python code executor with timeout handling,
memory monitoring, execution statistics, and comprehensive error reporting.
All imports and functions are allowed for maximum flexibility.
"""

import io
import sys
import time
import threading
import traceback
import re
import psutil
import os
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Dict, List, Set, Callable, Union, TYPE_CHECKING, Tuple
from pathlib import Path
import weakref
import gc

from loguru import logger
from trigger_designer.qt.helpers import global_logger

if TYPE_CHECKING:
    from trigger_designer.qt.node_base import TriggerNode


@dataclass
class ExecutionResult:
    """Detailed result of code execution."""

    success: bool
    output: str = ""
    error: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    memory_used: float = 0.0
    peak_memory: float = 0.0
    lines_executed: int = 0
    warnings: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ExecutionStats:
    """Statistics for tracking execution performance."""

    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    max_memory_used: float = 0.0
    last_execution: Optional[datetime] = None


@dataclass
class SecurityConfig:
    """Configuration for code execution limits."""

    max_execution_time: float = 30.0  # seconds
    max_memory_mb: float = 512.0  # megabytes


class NodeExecutionError(Exception):
    """Custom exception for node execution errors."""

    def __init__(
        self,
        message: str,
        node_name: str = "",
        line_number: int = 0,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.node_name = node_name
        self.line_number = line_number
        self.original_exception = original_exception


class ExecutionTimeoutError(NodeExecutionError):
    """Exception raised when code execution times out."""

    pass


class ExecutionMemoryError(NodeExecutionError):
    """Exception raised when code execution exceeds memory limits."""

    pass


class NodeExecutor:
    """Enhanced Python code executor with timeout monitoring, memory tracking, and error handling."""

    max_missing_dependency_attempts = 5

    def __init__(self, security_config: Optional[SecurityConfig] = None) -> None:
        """Initialize the NodeExecutor.

        Args:
            security_config: Configuration for execution limits (timeout, memory)
        """
        self.execution_context: Dict[str, Any] = {}
        self.security_config = security_config or SecurityConfig()
        self.stats = ExecutionStats()
        self.execution_history: List[ExecutionResult] = []
        self._cancel_event = threading.Event()
        self._current_thread: Optional[threading.Thread] = None
        self._missing_dependency_attempts: Dict[str, int] = {}

    def _track_missing_dependency(self, dependency_type: str, identifier: str) -> int:
        key = f"{dependency_type}:{identifier}"
        attempts = self._missing_dependency_attempts.get(key, 0) + 1
        self._missing_dependency_attempts[key] = attempts
        return attempts

    def _log_missing_dependency(
        self,
        node_name: str,
        dependency_type: str,
        identifier: str,
    ) -> None:
        attempts = self._track_missing_dependency(dependency_type, identifier)

        if attempts > self.max_missing_dependency_attempts:
            return

        warning_message = (
            f"{node_name}: {dependency_type} '{identifier}' not found "
            f"(attempt {attempts}/{self.max_missing_dependency_attempts})"
        )
        logger.warning(warning_message)
        global_logger.warning(warning_message)

        if attempts == self.max_missing_dependency_attempts:
            give_up_message = (
                f"{node_name}: giving up after {self.max_missing_dependency_attempts} attempts "
                f"because {dependency_type} '{identifier}' was not found."
            )
            logger.error(give_up_message)
            global_logger.error(give_up_message)

    def _report_missing_dependency(self, node_name: str, error: Exception) -> None:
        source_error = getattr(error, "original_exception", None) or error

        if isinstance(source_error, NameError):
            match = re.search(r"name '([^']+)' is not defined", str(source_error))
            variable_name = match.group(1) if match else str(source_error)
            self._log_missing_dependency(node_name, "variable", variable_name)
        elif isinstance(source_error, FileNotFoundError):
            file_name = getattr(source_error, "filename", None) or str(source_error)
            self._log_missing_dependency(node_name, "file", file_name)

    @contextmanager
    def _capture_output(self):
        """Context manager to capture stdout and stderr."""
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()

        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                yield stdout_buffer, stderr_buffer
        finally:
            pass

    def _get_memory_usage(self) -> float:
        """Get current process memory usage in MB."""
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0

    def _execute_with_timeout(
        self, code: str, local_vars: Dict[str, Any], timeout: float
    ) -> Tuple[bool, Optional[Exception]]:
        """Execute code with timeout in a separate thread.

        Args:
            code: Python code to execute
            local_vars: Local variables dictionary
            timeout: Timeout in seconds

        Returns:
            Tuple of (success, exception_if_any)
        """
        exception_container = [None]

        def target():
            try:
                # Create execution environment with full access
                execution_globals = {**self.execution_context, "__name__": "__main__"}

                exec(code, execution_globals, local_vars)

            except Exception as e:
                exception_container[0] = e

        thread = threading.Thread(target=target, daemon=True)
        self._current_thread = thread
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            # Thread is still running, execution timed out
            return False, ExecutionTimeoutError(
                f"Code execution timed out after {timeout} seconds"
            )

        return True, exception_container[0]

    def execute_node(self, node: "TriggerNode") -> ExecutionResult:
        """Execute a node's code with comprehensive monitoring and error handling.

        Args:
            node: The TriggerNode to execute

        Returns:
            ExecutionResult containing detailed execution information
        """
        start_time = time.time()
        start_memory = self._get_memory_usage()
        peak_memory = start_memory

        # Reset cancellation flag
        self._cancel_event.clear()

        # Create result object
        result = ExecutionResult(success=False)

        try:
            # Get code from node
            code = node.get_code()
            node_name = getattr(node.__class__, "__name__", "Unknown")

            # Count lines of code
            result.lines_executed = len(
                [line for line in code.splitlines() if line.strip()]
            )

            # Prepare local variables
            local_variables = {}

            # Capture output during execution
            with self._capture_output() as (stdout_buffer, stderr_buffer):
                # Execute with timeout
                success, exception = self._execute_with_timeout(
                    code, local_variables, self.security_config.max_execution_time
                )

                # Monitor memory usage during execution
                current_memory = self._get_memory_usage()
                if current_memory > peak_memory:
                    peak_memory = current_memory

                # Check memory limits
                if peak_memory - start_memory > self.security_config.max_memory_mb:
                    raise ExecutionMemoryError(
                        f"Memory usage exceeded limit: {peak_memory - start_memory:.2f}MB",
                        node_name=node_name,
                    )

                if not success or exception:
                    if isinstance(exception, ExecutionTimeoutError):
                        raise exception
                    elif exception:
                        raise NodeExecutionError(
                            str(exception),
                            node_name=node_name,
                            original_exception=exception,
                        )

                # Collect results
                result.output = stdout_buffer.getvalue()
                stderr_content = stderr_buffer.getvalue()
                if stderr_content:
                    result.warnings.append(f"stderr: {stderr_content}")

                result.variables = local_variables.copy()
                result.success = True

            # Update shared execution context with new variables
            self.execution_context.update(local_variables)

            # Log successful execution
            logger.debug(f"Successfully executed node {node_name}")

        except Exception as e:
            self._report_missing_dependency(node_name, e)
            result.success = False
            result.error = str(e)

            # Add detailed traceback for debugging
            if hasattr(e, "original_exception") and e.original_exception:
                result.error += f"\n\nOriginal traceback:\n{traceback.format_exc()}"

            # Log error
            logger.error(f"Error executing node: {result.error}")

        finally:
            # Calculate final statistics
            result.execution_time = time.time() - start_time
            result.memory_used = self._get_memory_usage() - start_memory
            result.peak_memory = peak_memory - start_memory

            # Update statistics
            self._update_stats(result)

            # Add to history (keep last 100 executions)
            self.execution_history.append(result)
            if len(self.execution_history) > 100:
                self.execution_history.pop(0)

            # Clean up thread reference
            self._current_thread = None

            # Force garbage collection to free memory
            gc.collect()

        return result

    def execute_node_legacy(self, node: "TriggerNode") -> Tuple[str, Dict[str, Any]]:
        """Legacy method for backward compatibility.

        Args:
            node: The TriggerNode to execute

        Returns:
            Tuple of (output_string, variables_dict)
        """
        result = self.execute_node(node)

        if result.success:
            return result.output, result.variables
        else:
            return f"Error: {result.error}", self.execution_context

    def _update_stats(self, result: ExecutionResult) -> None:
        """Update execution statistics.

        Args:
            result: ExecutionResult to incorporate into stats
        """
        self.stats.total_executions += 1
        self.stats.last_execution = result.timestamp

        if result.success:
            self.stats.successful_executions += 1
        else:
            self.stats.failed_executions += 1

        self.stats.total_execution_time += result.execution_time
        self.stats.average_execution_time = (
            self.stats.total_execution_time / self.stats.total_executions
        )

        if result.peak_memory > self.stats.max_memory_used:
            self.stats.max_memory_used = result.peak_memory

    def cancel_execution(self) -> bool:
        """Cancel currently running execution.

        Returns:
            True if cancellation was attempted, False if no execution running
        """
        if self._current_thread and self._current_thread.is_alive():
            self._cancel_event.set()
            return True
        return False

    def clear_context(self) -> None:
        """Clear the shared execution context."""
        self.execution_context.clear()
        logger.debug("Execution context cleared")

    def get_context_info(self) -> Dict[str, Any]:
        """Get information about the current execution context.

        Returns:
            Dictionary with context variable information
        """
        context_info = {}

        for name, value in self.execution_context.items():
            try:
                context_info[name] = {
                    "type": type(value).__name__,
                    "size": sys.getsizeof(value),
                    "repr": repr(value)[:100] + "..."
                    if len(repr(value)) > 100
                    else repr(value),
                }
            except Exception:
                context_info[name] = {
                    "type": type(value).__name__,
                    "size": 0,
                    "repr": "<unable to represent>",
                }

        return context_info

    def get_statistics(self) -> ExecutionStats:
        """Get execution statistics.

        Returns:
            ExecutionStats object with current statistics
        """
        return self.stats

    def get_execution_history(
        self, limit: Optional[int] = None
    ) -> List[ExecutionResult]:
        """Get execution history.

        Args:
            limit: Maximum number of results to return (None for all)

        Returns:
            List of ExecutionResult objects
        """
        if limit is None:
            return self.execution_history.copy()
        return self.execution_history[-limit:] if limit > 0 else []

    def set_config(self, config: SecurityConfig) -> None:
        """Update execution configuration.

        Args:
            config: New SecurityConfig to apply (timeout and memory limits)
        """
        self.security_config = config
        logger.debug("Execution configuration updated")
