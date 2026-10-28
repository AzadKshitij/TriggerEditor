"""ExecutionResult hook fields and call ordering."""

from __future__ import annotations

from types import SimpleNamespace

from trigger_designer.core.ExecutionCheck.executor import NodeExecutor


class StubNode:
    def __init__(self, code: str) -> None:
        self.code = code
        self.content = SimpleNamespace()

    def get_code(self) -> str:
        return self.code


def test_result_fields_and_filtered_code_contract() -> None:
    executor = NodeExecutor()
    events: list[str] = []
    executor.before_node = lambda node: events.append("before")
    executor.after_node = lambda node, variables, result: events.append("after")
    executor.code_filter = lambda code: code + "\ny = 2\n"
    result = executor.execute_node(StubNode("x = 1"))
    assert result.success
    assert events == ["before", "after"]
    assert result.code == "x = 1"
    assert result.variables["y"] == 2
    assert result.started_at.endswith("Z")
    assert result.finished_at.endswith("Z")


def test_hook_failure_does_not_fail_the_run() -> None:
    executor = NodeExecutor()
    executor.before_node = lambda node: (_ for _ in ()).throw(RuntimeError("boom"))
    result = executor.execute_node(StubNode("x = 1"))
    assert result.success is True


def test_after_node_only_on_success() -> None:
    executor = NodeExecutor()
    events: list[str] = []
    executor.after_node = lambda node, variables, result: events.append("after")
    result = executor.execute_node(StubNode("raise ValueError('no')"))
    assert result.success is False
    assert events == []


def test_before_node_not_called_when_get_code_raises() -> None:
    executor = NodeExecutor()
    events: list[str] = []
    executor.before_node = lambda node: events.append("before")

    class Broken(StubNode):
        def get_code(self) -> str:
            raise ValueError("no code")

    result = executor.execute_node(Broken(""))
    assert result.success is False
    assert events == []


def test_after_execution_receives_the_node_variables() -> None:
    seen: list[dict] = []
    node = StubNode("x = 1")
    node.content = SimpleNamespace(after_execution=lambda ctx: seen.append(dict(ctx)))
    result = NodeExecutor().execute_node(node)
    assert result.success
    assert seen == [{"x": 1}]
