"""Precise recovery for incomplete multi-input collectors."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.performance_scene import (
    TriggerScene,
    settle_multi_input_nodes,
)
from trigger_designer.qt.widgets.nodes.Join.union import TriggerNode_Union

APP = QApplication.instance() or QApplication([])


class CountingSource(TriggerNode):
    node_title = "SettleSource"

    def __init__(self, scene, *, key: str, value: int) -> None:
        self.computes = 0
        self.key = key
        self._value = value
        super().__init__(scene, inputs=[], outputs=[1])

    def evalImplementation(self):
        self.computes += 1
        self.markDirty(False)
        self.markInvalid(False)
        self.value = [
            {
                "data": pl.DataFrame({"v": [self._value]}),
                "variable_name": self.key,
            }
        ]
        return self.value


def _union_with_two_sources():
    scene = TriggerScene()
    left = CountingSource(scene, key="left", value=1)
    right = CountingSource(scene, key="right", value=2)
    union = TriggerNode_Union(scene)
    for source in (left, right):
        Edge(scene, source.outputs[0], union.inputs[0])
    union.eval()
    left.computes = 0
    right.computes = 0
    return scene, union, left, right


def test_incomplete_collector_retries_once() -> None:
    scene, union, _left, _right = _union_with_two_sources()
    assert len(union.content.input_frames) == 2

    # Simulate a first pass that missed one edge's frame.
    union.content.input_frames = union.content.input_frames[:1]
    calls = []
    original = union.evalImplementation

    def spy():
        calls.append(1)
        return original()

    union.evalImplementation = spy
    settle_multi_input_nodes(scene)

    assert calls == [1]
    assert len(union.content.input_frames) == 2

    # A complete collector is a cache hit and must not run again.
    settle_multi_input_nodes(scene)
    assert calls == [1]


def test_settle_does_not_evaluate_unrelated_branches() -> None:
    scene, union, _left, _right = _union_with_two_sources()
    union.content.input_frames = union.content.input_frames[:1]
    independent = CountingSource(scene, key="independent", value=99)
    independent.markDirty(True)

    settle_multi_input_nodes(scene)

    assert independent.computes == 0
    assert independent.isDirty()


def test_still_incomplete_collector_warns_without_looping() -> None:
    scene, union, _left, _right = _union_with_two_sources()
    union.content.input_frames = union.content.input_frames[:1]
    calls = []

    def broken():
        calls.append(1)

    union.evalImplementation = broken
    with patch("trigger_designer.qt.performance_scene.logger.warning") as warning:
        settle_multi_input_nodes(scene)

    assert calls == [1]
    warning.assert_called_once()
