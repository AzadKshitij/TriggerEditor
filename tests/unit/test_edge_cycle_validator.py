"""Cycle validation, load reporting, and Run handling."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.helpers.edge_validators import (
    CYCLE_MESSAGE,
    format_cycle,
    register_cycle_validator,
)
from trigger_designer.qt.node_base import TriggerNode

APP = QApplication.instance() or QApplication([])
register_cycle_validator()


class BasicNode(TriggerNode):
    node_title = "Basic"

    def __init__(self, scene, inputs, outputs, title):
        super().__init__(scene, inputs=inputs, outputs=outputs)
        self.title = title

    def processInputs(self, input_values):
        return input_values

    def get_code(self) -> str:
        return ""


def _node(window, title, inputs=(1,), outputs=(1,)):
    return BasicNode(window.scene, list(inputs), list(outputs), title)


def _connect(window, source, target):
    return window.scene.getEdgeClass()(
        window.scene, source.outputs[0], target.inputs[0]
    )


def _cycle(window):
    a = _node(window, "a")
    b = _node(window, "b")
    c = _node(window, "c")
    edges = [_connect(window, a, b), _connect(window, b, c), _connect(window, c, a)]
    return a, b, c, edges


def test_registration_is_idempotent() -> None:
    register_cycle_validator()
    register_cycle_validator()
    names = [
        getattr(validator, "__name__", "") for validator in Edge.getEdgeValidators()
    ]
    assert names.count("edge_cannot_create_a_cycle") == 1


def test_validator_rejects_back_edge() -> None:
    window = TriggerSubWindow()
    try:
        a = _node(window, "a")
        b = _node(window, "b")
        _connect(window, a, b)

        assert not Edge.validateEdge(b.outputs[0], a.inputs[0])
        assert Edge.validateEdge(a.outputs[0], b.inputs[0])
    finally:
        window.close()


def test_validator_allows_diamond() -> None:
    window = TriggerSubWindow()
    try:
        a = _node(window, "a")
        b = _node(window, "b")
        c = _node(window, "c")
        d = _node(window, "d")

        assert Edge.validateEdge(a.outputs[0], b.inputs[0])
        _connect(window, a, b)
        assert Edge.validateEdge(a.outputs[0], c.inputs[0])
        _connect(window, a, c)
        assert Edge.validateEdge(b.outputs[0], d.inputs[0])
        _connect(window, b, d)
        assert Edge.validateEdge(c.outputs[0], d.inputs[0])
        _connect(window, c, d)
    finally:
        window.close()


def test_validator_allows_reroute() -> None:
    window = TriggerSubWindow()
    try:
        a = _node(window, "a")
        b = _node(window, "b")
        c = _node(window, "c")
        _connect(window, a, b)

        # Rerouting may pass the fixed (input) end first; direction is not a
        # cycle, and an existing edge must not make the move look cyclic.
        assert Edge.validateEdge(b.inputs[0], c.outputs[0])
        assert Edge.validateEdge(b.inputs[0], a.outputs[0])
    finally:
        window.close()


def test_validator_handles_reversed_socket_order() -> None:
    window = TriggerSubWindow()
    try:
        a = _node(window, "a")
        b = _node(window, "b")
        _connect(window, a, b)

        # Drag from a's input to b's output: normalized to b -> a, which
        # closes the existing a -> b loop and must be rejected.
        assert not Edge.validateEdge(a.inputs[0], b.outputs[0])
    finally:
        window.close()


def test_format_cycle_uses_node_titles() -> None:
    window = TriggerSubWindow()
    try:
        _, _, _, edges = _cycle(window)
        assert format_cycle(edges) == "a -> b -> c -> a"
    finally:
        window.close()


def test_cycle_warning_on_load(monkeypatch) -> None:
    window = TriggerSubWindow()
    messages: list[str] = []
    monkeypatch.setattr(window, "logWarning", messages.append)
    try:
        _cycle(window)

        validation = window.validateLoadedWorkflow()
        assert any("cycle" in message.lower() for message in validation)
        assert any("a -> b -> c -> a" in message for message in validation)
        for message in validation:
            window.logWarning(message)

        # A legacy cyclic file still opens and evaluates in fallback order.
        window.doEvalOutputs()
        assert len(window.getAllNodes()) == 3
        cycle_messages = [message for message in messages if "cycle" in message.lower()]
        assert len(cycle_messages) == 1
    finally:
        window.close()


def test_run_on_cycle_reenables_button_and_selects_edges(monkeypatch) -> None:
    window = TriggerSubWindow()
    messages: list[str] = []
    monkeypatch.setattr(window, "_log_to_dock", messages.append)
    try:
        _, _, _, edges = _cycle(window)
        window.run_button.setEnabled(True)

        window.executeWorkflow()

        assert window.run_button.isEnabled()
        assert window._workflow_worker is None
        assert window.workflow_execution_count == 0
        assert messages
        assert CYCLE_MESSAGE in messages[0]
        assert all(edge.grEdge.isSelected() for edge in edges)
    finally:
        window.close()


def test_cycle_reported_once(monkeypatch) -> None:
    window = TriggerSubWindow()
    messages: list[str] = []
    monkeypatch.setattr(window, "logWarning", messages.append)
    try:
        _cycle(window)

        window.doEvalOutputs()
        window.doEvalOutputs()

        cycle_messages = [message for message in messages if "cycle" in message.lower()]
        assert len(cycle_messages) == 1
    finally:
        window.close()
