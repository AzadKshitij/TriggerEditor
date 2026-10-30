"""A node may declare its own execution time limit (``execution_timeout``)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from trigger_designer.core.ExecutionCheck.executor import (
    MAX_NODE_TIMEOUT,
    ExecutionTimeoutError,
    NodeExecutor,
    SecurityConfig,
)

SLOW = "import time\ntime.sleep(1.2)\nx = 1"


class StubNode:
    def __init__(self, code: str, timeout=None, on_content=False) -> None:
        self.code = code
        self.content = SimpleNamespace()
        if timeout is not None:
            target = self.content if on_content else self
            target.execution_timeout = timeout

    def get_code(self) -> str:
        return self.code


def _executor(default: float) -> NodeExecutor:
    return NodeExecutor(SecurityConfig(max_execution_time=default))


@pytest.mark.parametrize("on_content", [False, True])
def test_declared_timeout_lets_a_slow_step_finish(on_content) -> None:
    executor = _executor(1.0)
    try:
        result = executor.execute_node(StubNode(SLOW, 10.0, on_content))
        assert result.success is True
        assert result.variables["x"] == 1
    finally:
        executor.shutdown()


def test_node_without_the_attribute_keeps_the_default() -> None:
    executor = _executor(1.0)
    try:
        result = executor.execute_node(StubNode(SLOW))
        assert result.success is False
        assert isinstance(result.exception, ExecutionTimeoutError)
        # the message states the real limit
        assert "timed out after 1 seconds" in result.error
    finally:
        executor.shutdown()


def test_error_states_the_declared_limit() -> None:
    executor = _executor(30.0)
    try:
        result = executor.execute_node(StubNode(SLOW, 0.5))
        assert result.success is False
        assert "timed out after 0.5 seconds" in result.error
    finally:
        executor.shutdown()


def test_effective_timeout_rules() -> None:
    executor = _executor(30.0)
    try:
        assert executor.effective_timeout(StubNode("")) == 30.0
        assert executor.effective_timeout(StubNode("", 600.0)) == 600.0
        assert executor.effective_timeout(StubNode("", None)) == 30.0
        assert executor.effective_timeout(StubNode("", 10**6)) == MAX_NODE_TIMEOUT
        for junk in (0, -5, True, "600"):
            assert executor.effective_timeout(StubNode("", junk)) == 30.0
    finally:
        executor.shutdown()


def test_unlimited_default_is_never_lowered() -> None:
    """The CLI sets a huge (or --timeout based) limit; a node must not lower it."""
    executor = _executor(1e9)
    try:
        assert executor.effective_timeout(StubNode("", 600.0)) == 1e9
    finally:
        executor.shutdown()


def test_workpaper_output_declares_ten_minutes() -> None:
    from trigger_designer.qt.widgets.nodes.InOut.workpaper_output import (
        TriggerNode_WorkpaperOutput,
    )

    assert TriggerNode_WorkpaperOutput.execution_timeout == 600.0
    assert MAX_NODE_TIMEOUT >= 600.0


def test_workpaper_abandon_check_follows_the_run_record() -> None:
    """A step the executor gave up on is seen as abandoned by the writer."""
    from trigger_designer.core.audit.recorder import set_run_record_provider
    from trigger_designer.core.workpaper.node_runner import _abandon_check

    record = {"status": "running", "nodes": [{"node_id": 7, "status": "running"}]}
    set_run_record_provider(lambda: record)
    try:
        check = _abandon_check(7)
        assert check() is False
        record["nodes"][0]["status"] = "failed"
        assert check() is True
        assert _abandon_check(8)() is False
        record["status"] = "failed"
        assert _abandon_check(8)() is True
    finally:
        set_run_record_provider(None)
