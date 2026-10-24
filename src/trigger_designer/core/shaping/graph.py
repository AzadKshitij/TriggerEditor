"""Graph: a pass-through node (the chart lives in core/charts.py)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import as_lazy

DEFAULTS = {
    "graph_type": "line",
    "x_column": "",
    "y_column": "",
    "color_column": "",
    "aggregation": "",
    "title": "",
}


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    """Forward the input unchanged; the chart is a side effect."""
    del settings
    return [as_lazy(frames[0])]
