"""Edges are stored output -> input even when the drag started on an input."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nodeeditor.node_edge import Edge
from nodeeditor.node_graph import descendants, topological_order
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode

APP = QApplication.instance() or QApplication([])


class BasicNode(TriggerNode):
    node_title = "Basic"

    def __init__(self, scene, inputs, outputs, title):
        super().__init__(scene, inputs=inputs, outputs=outputs)
        self.title = title

    def processInputs(self, input_values):
        return input_values

    def get_code(self) -> str:
        return ""


def test_trigger_edge_normalises_reversed_construction() -> None:
    window = TriggerSubWindow()
    try:
        source = BasicNode(window.scene, [], [1], "A")
        target = BasicNode(window.scene, [1], [1], "B")

        edge = window.scene.getEdgeClass()(
            window.scene, target.inputs[0], source.outputs[0]
        )

        assert edge.start_socket is source.outputs[0]
        assert edge.end_socket is target.inputs[0]
        assert target in descendants(window.scene, source)
        order = topological_order(window.scene)
        assert order.index(source) < order.index(target)
    finally:
        window.close()


def test_loaded_reversed_edge_is_removed_with_both_titles(monkeypatch) -> None:
    window = TriggerSubWindow()
    messages: list[str] = []
    monkeypatch.setattr(window, "logWarning", messages.append)
    try:
        source = BasicNode(window.scene, [], [1], "Source A")
        target = BasicNode(window.scene, [1], [1], "Target B")
        # Load paths restore the serialized socket order directly; emulate a
        # legacy file that stored input -> output.
        Edge(window.scene, target.inputs[0], source.outputs[0])
        assert len(window.scene.edges) == 1

        window.validateConnections()

        assert window.scene.edges == []
        assert len(messages) == 1
        assert "Source A" in messages[0]
        assert "Target B" in messages[0]
    finally:
        window.close()
