"""Batch graph evaluation avoids duplicate cascades without affecting live edits."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode

APP = QApplication.instance() or QApplication([])


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene):
        super().__init__(scene, inputs=[], outputs=[3])


class Sink(TriggerNode):
    node_title = "Sink"

    def __init__(self, scene):
        self.calls = 0
        super().__init__(scene, inputs=[1], outputs=[])

    def processInputs(self, input_values):
        self.calls += 1
        return input_values


def test_batch_evaluates_once_then_live_edits_propagate() -> None:
    window = TriggerSubWindow()
    source = Source(window.scene)
    sink = Sink(window.scene)
    Edge(window.scene, source.outputs[0], sink.inputs[0])
    source.markDirty(True)
    sink.markDirty(True)

    window.doEvalOutputs()
    assert sink.calls == 1
    assert not window.scene._batch_evaluating

    source.onInputChanged()
    assert sink.calls == 2
    window.close()


def test_batch_flag_restored_on_failure(monkeypatch) -> None:
    window = TriggerSubWindow()
    node = Source(window.scene)

    def fail():
        raise RuntimeError("failed graph walk")

    monkeypatch.setattr(node, "eval", fail)
    with pytest.raises(RuntimeError, match="failed graph walk"):
        window.doEvalOutputs()
    assert not window.scene._batch_evaluating
    window.close()
