"""Topology notifications mark the consumer without recomputing the producer."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode

APP = QApplication.instance() or QApplication([])


class CountingNode(TriggerNode):
    node_title = "Count"
    content_label = "edge_notification_count"

    def __init__(self, scene, *, inputs, outputs, key):
        self.computes = 0
        self.key = key
        super().__init__(scene, inputs=inputs, outputs=outputs)
        self.title = key

    def processInputs(self, input_values):
        self.computes += 1
        return input_values

    def get_code(self) -> str:
        return ""


def _edge(window, source_socket, target_socket):
    return window.scene.getEdgeClass()(window.scene, source_socket, target_socket)


def test_drag_end_evaluates_consumer_once_and_producer_not_at_all() -> None:
    window = TriggerSubWindow()
    try:
        first = CountingNode(window.scene, inputs=[], outputs=[1], key="first")
        second = CountingNode(window.scene, inputs=[], outputs=[1], key="second")
        join = CountingNode(window.scene, inputs=[1, 1], outputs=[1], key="join")
        _edge(window, first.outputs[0], join.inputs[0])
        window.doEvalOutputs()
        first.computes = second.computes = join.computes = 0

        new_edge = _edge(window, second.outputs[0], join.inputs[1])
        for socket in (second.outputs[0], join.inputs[1]):
            socket.node.onEdgeConnectionChanged(new_edge)
            if socket.is_input:
                socket.node.onInputChanged(socket)

        assert second.computes == 0
        assert join.computes == 1
    finally:
        window.close()


def test_outgoing_edge_does_not_dirty_or_evaluate_producer() -> None:
    window = TriggerSubWindow()
    try:
        source = CountingNode(window.scene, inputs=[], outputs=[1], key="source")
        target = CountingNode(window.scene, inputs=[1], outputs=[], key="target")
        window.doEvalOutputs()
        source.computes = 0

        edge = _edge(window, source.outputs[0], target.inputs[0])
        source.onEdgeConnectionChanged(edge)

        assert source.computes == 0
        assert not source.isDirty()
    finally:
        window.close()


def test_removal_notifies_consumer_without_evaluating_producer() -> None:
    window = TriggerSubWindow()
    try:
        source = CountingNode(window.scene, inputs=[], outputs=[1], key="source")
        target = CountingNode(window.scene, inputs=[1], outputs=[], key="target")
        edge = _edge(window, source.outputs[0], target.inputs[0])
        window.doEvalOutputs()
        source.computes = 0

        edge.remove()

        assert source.computes == 0
    finally:
        window.close()
