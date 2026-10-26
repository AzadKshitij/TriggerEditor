"""Frame helpers moved out of node_base stay compatible."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.frames import frame_schema, frame_shape
from trigger_designer.qt.node_base import frame_schema as reexported_schema
from trigger_designer.qt.node_base import frame_shape as reexported_shape


def test_frame_schema_dataframe_and_lazyframe() -> None:
    frame = pl.DataFrame({"a": [1], "b": ["x"]})
    assert frame_schema(frame) == {"a": pl.Int64, "b": pl.String}
    assert frame_schema(frame.lazy()) == {"a": pl.Int64, "b": pl.String}
    assert frame_schema(None) == {}
    assert reexported_schema is frame_schema


def test_frame_shape_does_not_collect_lazyframe() -> None:
    frame = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    assert frame_shape(frame) == (2, 2)
    assert frame_shape(frame.lazy()) == ("lazy", 2)
    assert reexported_shape is frame_shape
