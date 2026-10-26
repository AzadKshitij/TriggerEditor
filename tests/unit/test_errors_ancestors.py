"""Error enrichment walks every upstream edge, not only the first one."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QApplication

from trigger_designer.core.errors import NodeError
from trigger_designer.qt.helpers.error_context import build_context, build_enrich_job
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.performance_scene import TriggerScene
from trigger_designer.qt.widgets.nodes.Join.union import TriggerNode_Union

APP = QApplication.instance() or QApplication([])


class FrameNode(TriggerNode):
    node_title = "Frame"

    def __init__(self, scene, *, inputs=(), outputs=(1,), key="frame"):
        self.key = key
        super().__init__(scene, inputs=list(inputs), outputs=list(outputs))

    def set_frame(self, frame) -> None:
        self.value = [{"data": frame, "variable_name": self.key}]


def _source(scene, key):
    node = FrameNode(scene, outputs=(1,), key=key)
    node.set_frame(pl.DataFrame({"branch": [key]}))
    return node


def _error(node) -> NodeError:
    return NodeError(
        code="TD-TYP-001",
        title="Bad value",
        node_id=node.id,
        node_label=node.title,
    )


def test_union_tree_reports_every_branch() -> None:
    scene = TriggerScene()
    sources = [_source(scene, key) for key in ("a", "b", "c")]
    union = TriggerNode_Union(scene)
    edges = [Edge(scene, source.outputs[0], union.inputs[0]) for source in sources]

    job = build_enrich_job(union, None, _error(union))

    assert {ancestor.node_id for ancestor in job.ancestors} == {
        source.id for source in sources
    }
    assert len(job.ancestors) == 3
    frames = job.inputs_of[union.id]
    assert len(frames) == 3
    assert all(
        actual.equals(source.value[0]["data"])
        for actual, source in zip(frames, sources, strict=True)
    )

    # The canvas read order, not merely connection order, drives the frames.
    union.setEdgeOrder([edges[2], edges[0], edges[1]])
    reordered = build_enrich_job(union, None, _error(union))
    frames = reordered.inputs_of[union.id]
    assert len(frames) == 3
    assert all(
        actual.equals(sources[index].value[0]["data"])
        for actual, index in zip(frames, (2, 0, 1), strict=True)
    )


def test_downstream_error_keeps_union_branch_frames() -> None:
    scene = TriggerScene()
    sources = [_source(scene, key) for key in ("a", "b", "c")]
    union = TriggerNode_Union(scene)
    for source in sources:
        Edge(scene, source.outputs[0], union.inputs[0])
    sink = FrameNode(scene, inputs=(1,), key="sink")
    Edge(scene, union.outputs[0], sink.inputs[0])

    job = build_enrich_job(sink, None, _error(sink))

    assert {ancestor.node_id for ancestor in job.ancestors} == {
        union.id,
        *(source.id for source in sources),
    }
    frames = job.inputs_of[union.id]
    assert len(frames) == 3
    assert all(
        actual.equals(source.value[0]["data"])
        for actual, source in zip(frames, sources, strict=True)
    )


def test_diamond_has_no_duplicate_ancestor() -> None:
    scene = TriggerScene()
    source = _source(scene, "a")
    left = FrameNode(scene, inputs=(1,), key="left")
    right = FrameNode(scene, inputs=(1,), key="right")
    sink = FrameNode(scene, inputs=(1, 1), key="sink")
    Edge(scene, source.outputs[0], left.inputs[0])
    Edge(scene, source.outputs[0], right.inputs[0])
    Edge(scene, left.outputs[0], sink.inputs[0])
    Edge(scene, right.outputs[0], sink.inputs[1])

    job = build_enrich_job(sink, None, _error(sink))
    ids = [ancestor.node_id for ancestor in job.ancestors]

    assert len(ids) == len(set(ids))
    assert set(ids) == {source.id, left.id, right.id}


def test_input_schema_falls_through_to_a_later_edge() -> None:
    scene = TriggerScene()
    empty = FrameNode(scene, outputs=(1,), key="empty")
    empty.value = [{"data": None, "variable_name": "empty"}]
    good = _source(scene, "good")
    sink = FrameNode(scene, inputs=(1, 1), key="sink")
    Edge(scene, empty.outputs[0], sink.inputs[0])
    Edge(scene, good.outputs[0], sink.inputs[1])

    context = build_context(sink)

    assert context.input_columns == ("branch",)
    assert context.input_dtypes == {"branch": "String"}
