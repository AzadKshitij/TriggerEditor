"""``ExecutionResult.without_frames`` keeps the history free of run frames."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.ExecutionCheck.executor import ExecutionResult


def test_without_frames_describes_values_not_frames() -> None:
    frame = pl.DataFrame({"x": [1, 2, 3]})
    result = ExecutionResult(
        success=True,
        variables={"out": frame, "count": 3, "pl": pl},
    )

    light = result.without_frames()

    assert light is not result
    assert light.success is True
    assert light.variables == {
        "out": "DataFrame(3, 1)",
        "count": "int",
        "pl": "module",
    }
    # The original still carries the real objects for callers that need them.
    assert result.variables["out"] is frame


def test_without_frames_keeps_lazyframe_shape() -> None:
    lazy = pl.LazyFrame({"a": [1], "b": [2]})
    result = ExecutionResult(success=True, variables={"lf": lazy})

    assert result.without_frames().variables == {"lf": "LazyFrame"}
