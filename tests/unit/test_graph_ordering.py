"""Dependency ordering comes from nodeeditor.node_graph, not a private sort."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest
from nodeeditor.node_graph import GraphCycleError, topological_order
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode

APP = QApplication.instance() or QApplication([])

ORDER: list[str] = []


class OrderNode(TriggerNode):
    node_title = "Order"

    def __init__(self, scene, inputs, outputs, title):
        super().__init__(scene, inputs=inputs, outputs=outputs)
        self.title = title

    def processInputs(self, input_values):
        ORDER.append(self.title)
        return input_values

    def get_code(self) -> str:
        return ""


def _edge(scene, source, target):
    return scene.getEdgeClass()(scene, source, target)


def test_dag_evaluates_in_dependency_order() -> None:
    ORDER.clear()
    window = TriggerSubWindow()
    try:
        source = OrderNode(window.scene, [], [1], "source")
        branch = OrderNode(window.scene, [], [1], "branch")
        sink = OrderNode(window.scene, [1, 1], [], "sink")
        _edge(window.scene, source.outputs[0], sink.inputs[0])
        _edge(window.scene, branch.outputs[0], sink.inputs[1])

        window.doEvalOutputs()

        assert ORDER.index("source") < ORDER.index("sink")
        assert ORDER.index("branch") < ORDER.index("sink")
        assert ORDER.count("sink") == 1
    finally:
        window.close()


def test_independent_nodes_keep_creation_order() -> None:
    window = TriggerSubWindow()
    try:
        nodes = [
            OrderNode(window.scene, [], [1], name)
            for name in ("first", "second", "third")
        ]

        assert topological_order(window.scene) == nodes
    finally:
        window.close()


def test_cycle_raises_graph_cycle_error_with_edges() -> None:
    window = TriggerSubWindow()
    try:
        a = OrderNode(window.scene, [1], [1], "a")
        b = OrderNode(window.scene, [1], [1], "b")
        c = OrderNode(window.scene, [1], [1], "c")
        edges = [
            _edge(window.scene, a.outputs[0], b.inputs[0]),
            _edge(window.scene, b.outputs[0], c.inputs[0]),
            _edge(window.scene, c.outputs[0], a.inputs[0]),
        ]

        with pytest.raises(GraphCycleError) as caught:
            topological_order(window.scene)

        assert len(caught.value.cycles) == 1
        assert set(map(id, caught.value.cycles[0])) == set(map(id, edges))
    finally:
        window.close()


def test_do_eval_outputs_on_cycle_finishes_and_logs(monkeypatch) -> None:
    window = TriggerSubWindow()
    messages: list[str] = []
    monkeypatch.setattr(window, "logWarning", messages.append)
    try:
        a = OrderNode(window.scene, [1], [1], "a")
        b = OrderNode(window.scene, [1], [1], "b")
        c = OrderNode(window.scene, [1], [1], "c")
        _edge(window.scene, a.outputs[0], b.inputs[0])
        _edge(window.scene, b.outputs[0], c.inputs[0])
        _edge(window.scene, c.outputs[0], a.inputs[0])

        window.doEvalOutputs()

        assert messages
        assert "cycle" in messages[0].lower()
    finally:
        window.close()


def test_execute_workflow_on_cycle_reenables_run_button() -> None:
    window = TriggerSubWindow()
    try:
        a = OrderNode(window.scene, [1], [1], "a")
        b = OrderNode(window.scene, [1], [1], "b")
        c = OrderNode(window.scene, [1], [1], "c")
        _edge(window.scene, a.outputs[0], b.inputs[0])
        _edge(window.scene, b.outputs[0], c.inputs[0])
        _edge(window.scene, c.outputs[0], a.inputs[0])
        window.run_button.setEnabled(True)

        window.executeWorkflow()

        assert window.run_button.isEnabled()
        assert window._workflow_worker is None
        assert window.workflow_execution_count == 0
    finally:
        window.close()
