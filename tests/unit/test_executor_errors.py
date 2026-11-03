"""Executor keeps the source exception and survives BaseException."""

from __future__ import annotations

from types import SimpleNamespace

import polars as pl

from trigger_designer.core.errors import ErrorContext, translate_exception
from trigger_designer.core.ExecutionCheck.executor import (
    NodeExecutor,
    SecurityConfig,
)


class StubNode:
    def __init__(self, code: str) -> None:
        self.code = code
        self.content = SimpleNamespace()

    def get_code(self) -> str:
        return self.code


def test_result_keeps_original_exception_and_traceback_text() -> None:
    executor = NodeExecutor()
    result = executor.execute_node(
        StubNode("import polars as pl\nraise pl.exceptions.ColumnNotFoundError('x')")
    )
    assert result.success is False
    assert isinstance(result.exception, pl.exceptions.ColumnNotFoundError)
    assert "ColumnNotFoundError" in result.traceback_text
    assert "Original traceback" not in result.error or result.exception is not None
    assert result.started_at.endswith("Z")
    assert result.finished_at.endswith("Z")


def test_panic_is_failure_and_worker_survives() -> None:
    executor = NodeExecutor()
    result = executor.execute_node(
        StubNode(
            "from polars.exceptions import PanicException\nraise PanicException('boom')"
        )
    )
    assert result.success is False
    assert type(result.exception).__name__ == "PanicException"
    assert result.exception.__traceback__ is None

    follow_up = executor.execute_node(StubNode("x = 1"))
    assert follow_up.success is True
    assert follow_up.variables["x"] == 1


def test_timeout_replaces_the_stuck_worker() -> None:
    executor = NodeExecutor(SecurityConfig(max_execution_time=0.2))
    timed_out = executor.execute_node(StubNode("import time\ntime.sleep(1)"))
    assert timed_out.success is False
    next_result = executor.execute_node(StubNode("x = 2"))
    assert next_result.success is True
    assert next_result.variables["x"] == 2


def test_get_code_error_is_an_ordinary_failure() -> None:
    executor = NodeExecutor()

    class BrokenNode(StubNode):
        def get_code(self) -> str:
            raise ValueError("cannot generate")

    result = executor.execute_node(BrokenNode(""))
    assert result.success is False
    assert isinstance(result.exception, ValueError)
    assert result.error == "cannot generate"


def test_result_translates_with_preserved_technical_text() -> None:
    executor = NodeExecutor()
    result = executor.execute_node(
        StubNode(
            "import polars as pl\nraise pl.exceptions.ColumnNotFoundError('missing')"
        )
    )
    error = translate_exception(
        result.exception,
        ctx=ErrorContext(node_id=3),
        traceback_text=result.traceback_text,
    )
    assert error.code == "TD-SCH-001"
    assert error.technical == str(result.exception)
    assert error.exc_type == "ColumnNotFoundError"
    assert "Traceback" in error.traceback
