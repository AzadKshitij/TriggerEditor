"""Pins what Cancel and the node time limit really do (they are limited).

* Cancel is cooperative and is only looked at **between** nodes: the node that
  is executing finishes normally, even if it runs for a long time.
* A node that exceeds the time limit is abandoned, not stopped: its worker
  thread keeps running the code until it returns on its own, while later nodes
  run on a fresh worker. At most one thread leaks per timed-out node.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

from trigger_designer.core.ExecutionCheck.executor import NodeExecutor, SecurityConfig
from trigger_designer.core.ExecutionCheck.run_loop import run_nodes


class StubNode:
    def __init__(self, code: str) -> None:
        self.code = code
        self.content = SimpleNamespace()

    def get_code(self) -> str:
        return self.code


def test_cancel_during_a_node_lets_it_finish_and_skips_the_rest() -> None:
    executor = NodeExecutor()
    cancel = threading.Event()
    started = threading.Event()
    executor.execution_context["started"] = started
    long_node = StubNode("started.set()\nimport time\ntime.sleep(0.4)\nx = 1")
    next_node = StubNode("y = 2")
    results: dict = {}
    skipped: list = []

    def request_cancel() -> None:
        assert started.wait(5)
        cancel.set()
        executor.cancel_execution()

    threading.Thread(target=request_cancel, daemon=True).start()
    outcome = run_nodes(
        [long_node, next_node],
        executor,
        cancel=cancel,
        on_node_finished=lambda node, result: results.update({node: result}),
        on_node_skipped=lambda node, blocker: skipped.append((node, blocker)),
    )
    assert results[long_node].success is True  # not interrupted
    assert results[long_node].variables["x"] == 1
    assert next_node not in results  # never executed
    assert skipped == [(next_node, None)]
    assert outcome.cancelled is True and outcome.success is False


def test_timed_out_node_keeps_running_on_its_abandoned_thread() -> None:
    executor = NodeExecutor(SecurityConfig(max_execution_time=0.2))
    release = threading.Event()
    finished = threading.Event()
    executor.execution_context["release"] = release
    executor.execution_context["finished"] = finished
    first = executor._node_worker_thread
    result = executor.execute_node(StubNode("release.wait(10)\nfinished.set()"))
    assert result.success is False
    assert type(result.exception).__name__ == "ExecutionTimeoutError"
    # the abandoned worker is still alive and still inside the node's code
    assert first.is_alive()
    assert executor._node_worker_thread is not first
    assert not finished.is_set()
    # later nodes run on the replacement worker
    assert executor.execute_node(StubNode("z = 3")).variables["z"] == 3
    # the old code only ends when it returns by itself, and the thread then exits
    release.set()
    assert finished.wait(5)
    first.join(5)
    assert not first.is_alive()
