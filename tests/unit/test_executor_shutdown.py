"""NodeExecutor owns one pooled thread: it must be releasable and never leak."""

from __future__ import annotations

import gc
import threading
import time
from types import SimpleNamespace

from trigger_designer.core.ExecutionCheck.executor import NodeExecutor, SecurityConfig


class StubNode:
    def __init__(self, code: str) -> None:
        self.code = code
        self.content = SimpleNamespace()

    def get_code(self) -> str:
        return self.code


def _workers() -> list[threading.Thread]:
    return [
        t
        for t in threading.enumerate()
        if t.name == "NodeExecutorWorker" and t.is_alive()
    ]


def _wait_for(predicate, timeout: float = 3.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_shutdown_stops_the_worker_and_is_idempotent() -> None:
    baseline = len(_workers())
    executor = NodeExecutor()
    assert len(_workers()) == baseline + 1
    executor.shutdown()
    executor.shutdown()
    assert len(_workers()) == baseline


def test_shutdown_executor_is_still_usable() -> None:
    executor = NodeExecutor()
    executor.shutdown()
    assert executor.execute_node(StubNode("x = 1")).success
    executor.shutdown()


def test_discarded_executors_do_not_accumulate_threads() -> None:
    baseline = len(_workers())
    for _ in range(40):
        executor = NodeExecutor()
        assert executor.execute_node(StubNode("x = 1")).success
        del executor
    gc.collect()
    assert _wait_for(lambda: len(_workers()) <= baseline)


def test_explicit_shutdown_of_many_executors_leaves_no_threads() -> None:
    baseline = len(_workers())
    executors = [NodeExecutor() for _ in range(25)]
    for executor in executors:
        executor.shutdown()
    assert len(_workers()) == baseline


def test_shutdown_while_a_node_is_running_is_bounded() -> None:
    release = threading.Event()
    executor = NodeExecutor(SecurityConfig(max_execution_time=30.0))
    executor.execution_context["release"] = release
    runner = threading.Thread(
        target=lambda: executor.execute_node(StubNode("release.wait(10)")),
        daemon=True,
    )
    runner.start()
    time.sleep(0.2)
    started = time.monotonic()
    executor.shutdown(timeout=0.3)
    assert time.monotonic() - started < 2.0
    release.set()
    runner.join(5)
    assert _wait_for(
        lambda: all(t is not executor._node_worker_thread for t in _workers())
    )


def test_shutdown_after_timeout_respawn_is_safe() -> None:
    release = threading.Event()
    executor = NodeExecutor(SecurityConfig(max_execution_time=0.2))
    executor.execution_context["release"] = release
    result = executor.execute_node(StubNode("release.wait(10)"))
    assert not result.success
    executor.shutdown(timeout=0.3)
    release.set()
    assert executor.execute_node(StubNode("y = 2")).success
    executor.shutdown()
    assert _wait_for(lambda: not _workers())


def test_shutdown_never_raises() -> None:
    executor = NodeExecutor()
    real_queue = executor._node_task_queue
    executor._node_task_queue = None  # type: ignore[assignment]
    executor.shutdown()  # logs, must not raise
    real_queue.put(None)
    assert _wait_for(lambda: not executor._node_worker_thread.is_alive())
