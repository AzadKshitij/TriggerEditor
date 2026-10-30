"""Enhanced Python code executor for TriggerEditor nodes.

This module provides a robust Python code executor with timeout handling and
comprehensive error reporting.
All imports and functions are allowed for maximum flexibility.
"""

import os
import queue
import re
import threading
import traceback
import weakref
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import polars as pl
from loguru import logger

from trigger_designer.qt.helpers import global_logger

if TYPE_CHECKING:
    from trigger_designer.qt.node_base import TriggerNode


@dataclass
class ExecutionResult:
    """Detailed result of code execution."""

    success: bool
    error: str = ""
    variables: dict[str, Any] = field(default_factory=dict)
    exception: BaseException | None = None
    traceback_text: str = ""
    exception_type: str = ""
    code: str = ""
    started_at: str = ""
    finished_at: str = ""
    #: True when the failing source exception carries the class attribute
    #: ``policy_violation = True`` (set by a ``code_filter`` that refuses code).
    policy_violation: bool = False


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass
class SecurityConfig:
    """Configuration for code execution limits."""

    max_execution_time: float = 30.0  # seconds


def _node_worker_loop(tasks: queue.Queue[Callable[[], None] | None]) -> None:
    """Pooled worker body. Deliberately holds no reference to the executor."""
    while True:
        task = tasks.get()
        if task is None:
            return
        try:
            task()
        except BaseException:  # noqa: BLE001 - the worker must outlive any task
            logger.exception("Node executor task raised unexpectedly")
        del task


class NodeExecutionError(Exception):
    """Custom exception for node execution errors."""

    def __init__(
        self,
        message: str,
        node_name: str = "",
        line_number: int = 0,
        original_exception: BaseException | None = None,
    ):
        super().__init__(message)
        self.node_name = node_name
        self.line_number = line_number
        self.original_exception = original_exception


class ExecutionTimeoutError(NodeExecutionError):
    """Exception raised when code execution times out."""


class NodeExecutor:
    """Python code executor with timeout monitoring and error handling."""

    def __init__(self, security_config: SecurityConfig | None = None) -> None:
        """Initialize the NodeExecutor.

        Args:
            security_config: Configuration for execution limits (timeout)
        """
        self.execution_context: dict[str, Any] = {}
        self._seed_base_globals()
        self.security_config = security_config or SecurityConfig()
        # One daemon worker thread reused for every node execution in this
        # NodeExecutor's lifetime, instead of spawning+joining a fresh OS
        # thread per node. Kept as a plain daemon thread + queue (rather
        # than concurrent.futures.ThreadPoolExecutor, whose workers are
        # deliberately non-daemon) so an abandoned/timed-out node can never
        # block process exit - matching the old per-node thread's behavior.
        # A fresh NodeExecutor (and worker) is created per "Run Workflow"
        # click, so a timed-out task can only ever leak one thread per run.
        self.before_node: Callable[[Any], None] | None = None
        self.after_node: Callable[[Any, dict, ExecutionResult], None] | None = None
        self.code_filter: Callable[[str], str] | None = None
        # Cooperative cancel latch. Cleared by reset_cancel() at the start of a
        # run (the run loop does it), never by execute_node, so a request made
        # before the next node starts is not lost. Observers may poll
        # ``cancel_requested``; a node already inside ``exec`` is not stopped.
        #: Resolve the schema of every lazy output after exec (BUG-004); set
        #: False to let a broken plan "succeed" until something collects it.
        self.verify_plans: bool = True
        self._cancel_event = threading.Event()
        self._node_running = False
        self._start_worker()

    def _start_worker(self) -> None:
        """Start a fresh pooled worker with its own queue.

        The worker target is a module-level function that sees only its queue,
        never ``self``: a bound method would keep the executor alive for as
        long as the thread idles, so a discarded executor could never be
        collected and its thread would live until process exit (one leaked
        thread per Run click - hundreds across a test session).
        ``weakref.finalize`` posts the stop sentinel when the executor is
        garbage collected, as a backstop for owners that never call
        :meth:`shutdown`.
        """
        old_finalizer = getattr(self, "_worker_finalizer", None)
        if old_finalizer is not None:
            old_finalizer.detach()
        tasks: queue.Queue[Callable[[], None] | None] = queue.Queue()
        self._node_task_queue = tasks
        self._node_worker_thread = threading.Thread(
            target=_node_worker_loop,
            args=(tasks,),
            daemon=True,
            name="NodeExecutorWorker",
        )
        self._node_worker_thread.start()
        self._worker_finalizer = weakref.finalize(self, tasks.put, None)

    def shutdown(self, timeout: float = 2.0) -> None:
        """Stop the pooled worker thread; idempotent and never raises.

        Posts the stop sentinel and waits at most ``timeout`` seconds. A worker
        stuck inside a node (the case ``_execute_with_timeout`` abandons) is
        not killed: it is a daemon, exits once the node returns, and the wait
        is bounded so the GUI never hangs. A later ``execute_node`` starts a
        fresh worker, so a shut-down executor stays usable.
        """
        try:
            finalizer = getattr(self, "_worker_finalizer", None)
            if finalizer is not None:
                finalizer.detach()
            thread = getattr(self, "_node_worker_thread", None)
            if thread is None:
                return
            self._node_task_queue.put(None)
            if thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout)
        except Exception:  # noqa: BLE001 - shutdown runs from slots/destructors
            logger.exception("Node executor shutdown failed")

    def _ensure_worker(self) -> None:
        thread = self._node_worker_thread
        if not thread.is_alive():
            self._start_worker()

    def reset_cancel(self) -> None:
        """Forget an earlier cancel request (called when a run starts)."""
        self._cancel_event.clear()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_event.is_set()

    def cancel_execution(self) -> bool:
        """Latch a cancel request; True when a node is executing right now.

        The running node cannot be interrupted: the request only stops the
        run before the next node.
        """
        self._cancel_event.set()
        return self._node_running

    def _call_hook(self, hook, *args) -> None:
        if hook is None:
            return
        try:
            hook(*args)
        except Exception as exc:  # noqa: BLE001 - observers must never fail a run
            message = f"{getattr(hook, '__name__', 'hook')} failed: {exc!r}"
            logger.warning(message)

    def _seed_base_globals(self) -> None:
        # ponytail: seed once here instead of per-node imports; generated code
        # uses bare pl/timedelta and previously relied on FileInput leakage
        self.execution_context.update(
            {"pl": pl, "os": os, "datetime": datetime, "timedelta": timedelta}
        )

    def _report_missing_dependency(self, node_name: str, error: Exception) -> None:
        source_error = getattr(error, "original_exception", None) or error

        if isinstance(source_error, NameError):
            match = re.search(r"name '([^']+)' is not defined", str(source_error))
            kind, identifier = (
                "variable",
                match.group(1) if match else str(source_error),
            )
        elif isinstance(source_error, FileNotFoundError):
            kind = "file"
            identifier = getattr(source_error, "filename", None) or str(source_error)
        else:
            return
        message = f"{node_name}: {kind} '{identifier}' not found"
        logger.warning(message)
        global_logger.warning(message)

    def _execute_with_timeout(
        self, code: str, local_vars: dict[str, Any], timeout: float
    ) -> tuple[bool, BaseException | None]:
        """Execute code with timeout, on the one pooled worker thread.

        Args:
            code: Python code to execute
            local_vars: Local variables dictionary
            timeout: Timeout in seconds

        Returns:
            Tuple of (success, exception_if_any)
        """
        exception_container: list[BaseException | None] = [None]
        done = threading.Event()

        def target():
            try:
                # Create execution environment with full access
                execution_globals = {**self.execution_context, "__name__": "__main__"}

                exec(code, execution_globals, local_vars)  # noqa: S102

                if self.verify_plans:
                    # Generated code only *builds* lazy plans, so a bad column
                    # or join key would surface later at some sink, far from
                    # the node that caused it. Resolving the schema checks the
                    # plan without reading any data.
                    for value in local_vars.values():
                        if isinstance(value, pl.LazyFrame):
                            value.collect_schema()

            except BaseException as e:  # noqa: BLE001
                exception_container[0] = e
            finally:
                done.set()

        self._ensure_worker()
        self._node_task_queue.put(target)

        if not done.wait(timeout):
            # The old worker is stuck inside `target()` and cannot be killed.
            # Put a sentinel on its queue so it exits if the task ever
            # returns, then give subsequent nodes a fresh worker: with
            # continue-on-error a later node must not wait on a queue nobody
            # reads.
            self._node_task_queue.put(None)
            self._start_worker()
            return False, ExecutionTimeoutError(
                f"Code execution timed out after {timeout} seconds"
            )

        return True, exception_container[0]

    def execute_node(self, node: TriggerNode) -> ExecutionResult:
        """Execute a node's code with comprehensive monitoring and error handling.

        Args:
            node: The TriggerNode to execute

        Returns:
            ExecutionResult containing detailed execution information
        """
        # Create result object
        result = ExecutionResult(success=False)
        result.started_at = _utc_now_iso()

        node_name = getattr(node.__class__, "__name__", "Unknown")
        try:
            # Get code from node
            code = node.get_code()
            result.code = code
            if self.code_filter is not None:
                code = self.code_filter(code)
            self._call_hook(self.before_node, node)

            # Prepare local variables
            local_variables = {}

            self._node_running = True
            try:
                success, exception = self._execute_with_timeout(
                    code, local_variables, self.security_config.max_execution_time
                )
            finally:
                self._node_running = False
            if not success or exception:
                if isinstance(exception, ExecutionTimeoutError):
                    raise exception
                elif exception:
                    raise NodeExecutionError(
                        str(exception),
                        node_name=node_name,
                        original_exception=exception,
                    ) from exception
            result.success = True

            # Before the hook: a node's after_execution reads these values.
            result.variables = local_variables.copy()
            after_execution = getattr(
                getattr(node, "content", None), "after_execution", None
            )
            if callable(after_execution):
                try:
                    after_execution(result.variables)
                except Exception as hook_error:  # noqa: BLE001
                    logger.warning(
                        f"after_execution hook failed for {node_name}: {hook_error}"
                    )

            self._call_hook(self.after_node, node, local_variables, result)
            # An observer may have added or replaced a variable; the result
            # and the shared context must agree on what the node produced.
            result.variables = {**result.variables, **local_variables}

            # Update shared execution context with new variables
            self.execution_context.update(local_variables)

            # Log successful execution
            logger.debug(f"Successfully executed node {node_name}")

        except Exception as e:  # noqa: BLE001
            self._report_missing_dependency(node_name, e)
            result.success = False
            result.error = str(e)

            # Add detailed traceback for debugging
            if hasattr(e, "original_exception") and e.original_exception:
                result.error += f"\n\nOriginal traceback:\n{traceback.format_exc()}"

            source = getattr(e, "original_exception", None) or e
            result.exception = source
            result.exception_type = (
                f"{type(source).__module__}.{type(source).__qualname__}"
            )
            result.traceback_text = "".join(traceback.format_exception(source))
            result.policy_violation = bool(getattr(source, "policy_violation", False))
            source.__traceback__ = None

            # Log error
            logger.error(f"Error executing node: {result.error}")

        finally:
            result.finished_at = _utc_now_iso()
            # No gc.collect() here. This runs on the run's worker thread, and
            # a full collection there also destroys any unreachable Qt
            # wrappers (graphics items, widgets of discarded windows) on a
            # non-GUI thread: an intermittent Windows access violation, 0/24
            # crashes with this removed against ~40% before. Frames are
            # refcounted, so the automatic collector is enough.

        return result
