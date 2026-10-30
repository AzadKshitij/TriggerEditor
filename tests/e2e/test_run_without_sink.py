"""A graph with no sink must not silently succeed over a broken plan (BUG-004)."""

from __future__ import annotations

import polars as pl
import pytest

from tests.support.workflows import (
    WorkflowCase,
    materialize,
    nodes_titled,
    run_workflow_and_wait,
)
from trigger_designer.core.ExecutionCheck.executor import NodeExecutor

pytestmark = pytest.mark.e2e

SELECT_CASE = WorkflowCase(
    name="in_select",
    source="savedfiles/1. in-select.tds",
    inputs={"check.csv": "data/check.csv"},
)


class _CodeNode:
    content = None

    def __init__(self, code: str) -> None:
        self.code = code

    def get_code(self) -> str:
        return self.code


def test_bad_select_column_fails_run_without_sink(
    qtbot, tmp_path, no_modal_dialogs
) -> None:
    from trigger_designer.qt.design_window import TriggerSubWindow

    materialized = materialize(SELECT_CASE, tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(materialized.path)) is True

    select = nodes_titled(window, "Select")[0]
    # Generated code that builds a lazy plan over a column that does not
    # exist: nothing collects it, so only the plan check can see the problem.
    source = select.content.input_vars[0]
    target = select.content.output_variables[0]
    code = f"{target} = {source}.select(['NoSuchCol'])" + chr(10)
    select.get_code = lambda: code

    run_workflow_and_wait(qtbot, window)

    assert select.isInvalid()
    assert select not in window.execution_results
    error = select._errors_dict().get("run")
    assert error is not None
    assert "NoSuchCol" in (error.technical + error.detail + error.title)


def test_a_valid_plan_is_untouched_and_no_data_is_read() -> None:
    code = (
        "def boom(batch):\n"
        "    raise RuntimeError('data was read')\n"
        "plan = pl.LazyFrame({'a': [1]}).map_batches(boom, schema={'a': pl.Int64})\n"
    )
    result = NodeExecutor().execute_node(_CodeNode(code))
    assert result.success is True
    assert isinstance(result.variables["plan"], pl.LazyFrame)


def test_verify_plans_can_be_disabled() -> None:
    node = _CodeNode("plan = pl.LazyFrame({'a': [1]}).select('missing')\n")
    executor = NodeExecutor()
    failed = executor.execute_node(node)
    assert failed.success is False
    assert "missing" in failed.error

    executor.verify_plans = False
    assert executor.execute_node(node).success is True
