"""Graph core: the node forwards its input unchanged."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping import graph as core


def test_graph_forwards_a_dataframe_unchanged() -> None:
    frame = pl.DataFrame({"a": [2, 1], "b": ["y", "x"]})
    out = core.run_node([frame], core.DEFAULTS).pop()
    assert isinstance(out, pl.LazyFrame)
    forwarded = out.collect()
    assert forwarded.equals(frame)
    assert forwarded.columns == ["a", "b"]


def test_graph_forwards_a_lazyframe_unchanged() -> None:
    frame = pl.DataFrame({"a": [2, 1]}).lazy()
    out = core.run_node([frame], {}).pop()
    assert isinstance(out, pl.LazyFrame)
    assert out.collect().equals(frame.collect())


def test_graph_forwards_without_chart_settings() -> None:
    frame = pl.DataFrame({"only": [1, 2, 3]})
    out = core.run_node([frame], {"x_column": "gone", "y_column": "also_gone"})
    assert out.pop().collect().equals(frame)
