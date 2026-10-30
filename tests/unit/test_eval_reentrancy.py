"""A dirty node pushed by two branches must compute only once."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode

APP = QApplication.instance() or QApplication([])


class CounterNode(TriggerNode):
    node_title = "Counter"

    def __init__(self, scene, inputs, outputs):
        self.calls = 0
        super().__init__(scene, inputs=inputs, outputs=outputs)

    def processInputs(self, input_values):
        self.calls += 1
        return input_values

    def get_code(self) -> str:
        return ""


def _edge(scene, source, target):
    return scene.getEdgeClass()(scene, source, target)


def _diamond(scene, branches: int, stages: int):
    source = CounterNode(scene, [], [1])
    previous = source
    joins = []
    for _ in range(stages):
        branch_nodes = []
        for _ in range(branches):
            branch = CounterNode(scene, [1], [1])
            _edge(scene, previous.outputs[0], branch.inputs[0])
            branch_nodes.append(branch)
        join = CounterNode(scene, [1] * branches, [1])
        for index, branch in enumerate(branch_nodes):
            _edge(scene, branch.outputs[0], join.inputs[index])
        joins.append(join)
        previous = join
    return source, joins


def _settle_and_reset(window: TriggerSubWindow) -> None:
    window.doEvalOutputs()
    for node in window.scene.nodes:
        if isinstance(node, CounterNode):
            node.calls = 0


def test_diamond_join_computes_once() -> None:
    for branches in (2, 4):
        window = TriggerSubWindow()
        try:
            source, joins = _diamond(window.scene, branches, 1)
            _settle_and_reset(window)

            source.onInputChanged()

            assert all(node.calls == 1 for node in window.scene.nodes), (
                branches,
                {node: node.calls for node in window.scene.nodes},
            )
            assert joins[0].calls == 1
        finally:
            window.close()


def test_two_stage_diamond_each_join_once() -> None:
    window = TriggerSubWindow()
    try:
        source, joins = _diamond(window.scene, 2, 2)
        _settle_and_reset(window)

        source.onInputChanged()

        assert [join.calls for join in joins] == [1, 1]
        assert all(node.calls == 1 for node in window.scene.nodes)
    finally:
        window.close()


class RaisingNode(TriggerNode):
    node_title = "Raising"

    def __init__(self, scene):
        self.attempts = 0
        super().__init__(scene, inputs=[], outputs=[])

    def processInputs(self, input_values):
        self.attempts += 1
        raise RuntimeError("boom")

    def get_code(self) -> str:
        return ""


def test_guard_cleared_after_exception(monkeypatch) -> None:
    from trigger_designer.qt import node_runtime

    monkeypatch.setattr(node_runtime, "dumpException", lambda exc: None)
    window = TriggerSubWindow()
    try:
        node = RaisingNode(window.scene)
        node.eval()
        assert node.attempts == 1
        assert node._evaluating is False

        node.eval()
        assert node.attempts == 2
        assert node._evaluating is False
    finally:
        window.close()


class SelfPullingNode(TriggerNode):
    node_title = "SelfPulling"

    def __init__(self, scene):
        self.calls = 0
        super().__init__(scene, inputs=[], outputs=[])

    def processInputs(self, input_values):
        self.calls += 1
        # A push or listener that calls back into the node mid-compute must
        # return the in-progress value, not start a second processInputs.
        self.eval()
        return input_values

    def get_code(self) -> str:
        return ""


def test_reentrant_push_does_not_recompute() -> None:
    window = TriggerSubWindow()
    try:
        node = SelfPullingNode(window.scene)
        node.onInputChanged()
        assert node.calls == 1
        assert node._evaluating is False
    finally:
        window.close()


def test_listener_exception_does_not_escape(monkeypatch) -> None:
    window = TriggerSubWindow()
    try:
        node = CounterNode(window.scene, [], [])

        def raising_listener(evaluated):
            raise RuntimeError("preview listener failed")

        monkeypatch.setattr(window.scene, "notifyNodeEvaluated", raising_listener)
        node.onInputChanged()
        assert node.calls == 1
        assert node._evaluating is False
    finally:
        window.close()
