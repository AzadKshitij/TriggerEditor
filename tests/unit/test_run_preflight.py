"""Run pre-flight: cycle refusal, re-evaluation, before-run hooks, cleanup."""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from nodeeditor.node_graph import GraphCycleError
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.helpers import workflow_execution_mixin as mixin_module
from trigger_designer.qt.helpers.workflow_execution_mixin import WorkflowExecutionMixin

_APP = QApplication.instance() or QApplication([])


class Button:
    def __init__(self) -> None:
        self.enabled = True
        self.visible = True

    def setEnabled(self, value: bool) -> None:
        self.enabled = value

    def setVisible(self, value: bool) -> None:
        self.visible = value

    def setToolTip(self, _text: str) -> None:
        pass


class Gr:
    def __getattr__(self, _name):
        return lambda *a, **k: None


class Node:
    def __init__(self, title: str, invalid: bool = False) -> None:
        self.node_title = title
        self._invalid = invalid
        self.grNode = Gr()
        self.content = None
        self.dirty = False

    def markInvalid(self, value: bool = True) -> None:
        pass

    def isInvalid(self) -> bool:
        return self._invalid

    def markDirty(self, value: bool = True) -> None:
        self.dirty = value


class Host(WorkflowExecutionMixin):
    def __init__(self, nodes) -> None:
        self.init_workflow_execution()
        self.scene = SimpleNamespace(evaluator=None)
        self.nodes = nodes
        self.run_button = Button()
        self.cancel_button = Button()
        self.cancel_button.visible = False
        self.logged: list[str] = []
        self.order: list[str] = []

    def getAllNodes(self):
        return self.nodes

    def _log_to_dock(self, message: str) -> None:
        self.logged.append(message)


class Started(list):
    """Workers that were started; ``on_start`` callbacks fire in ``start``."""

    def __init__(self) -> None:
        super().__init__()
        self.on_start: list = []


@pytest.fixture()
def patched(monkeypatch):
    started = Started()

    class FakeWorker:
        def __init__(self, nodes, executor, **kwargs) -> None:
            self.kwargs = kwargs
            for name in (
                "nodeStarted",
                "nodeFinished",
                "nodeErrored",
                "nodeSkipped",
                "workflowFinished",
                "finished",
            ):
                setattr(self, name, SimpleNamespace(connect=lambda *_a: None))

        def deleteLater(self) -> None:
            pass

        def start(self) -> None:
            for callback in started.on_start:
                callback()
            started.append(self)

        def isRunning(self) -> bool:
            return False

    monkeypatch.setattr(mixin_module, "WorkflowWorker", FakeWorker)
    return started


def _sorted(monkeypatch, nodes) -> None:
    monkeypatch.setattr(mixin_module, "topological_order", lambda _scene: list(nodes))


def test_cycle_keeps_run_enabled_and_starts_nothing(monkeypatch, patched) -> None:
    host = Host([Node("a")])

    def boom(_scene):
        raise GraphCycleError("loop")

    monkeypatch.setattr(mixin_module, "topological_order", boom)
    monkeypatch.setattr(mixin_module, "select_cycle_edges", lambda *_a: None)
    monkeypatch.setattr(mixin_module, "cycle_message", lambda exc: "loop found")

    assert host.executeWorkflow() is False
    assert host.run_button.enabled and host.run_button.visible
    assert host._workflow_worker is None and patched == []
    assert "loop found" in host.logged


def test_preflight_exception_restores_run_button(monkeypatch, patched) -> None:
    host = Host([Node("a")])
    _sorted(monkeypatch, host.nodes)

    def boom(_nodes):
        raise RuntimeError("eval failed")

    host._reevaluate_for_run = boom
    assert host.executeWorkflow() is False
    assert host.run_button.enabled and host.run_button.visible
    assert host.cancel_button.visible is False
    assert host._workflow_worker is None and patched == []
    assert any("eval failed" in line for line in host.logged)


def test_started_run_swaps_run_for_cancel(monkeypatch, patched) -> None:
    host = Host([Node("a")])
    _sorted(monkeypatch, host.nodes)
    assert host.executeWorkflow() is True
    assert host.run_button.visible is False
    assert host.cancel_button.visible is True
    assert len(patched) == 1
    host._workflow_worker = None


def test_invalid_nodes_are_reported_not_hidden(monkeypatch, patched) -> None:
    good, bad = Node("Good"), Node("Broken", invalid=True)
    host = Host([good, bad])
    host.doEvalOutputs = lambda *_a, **_k: None
    host._reevaluate_for_run([good, bad])
    assert any("problems" in line and "Broken" in line for line in host.logged)
    assert good.dirty is True and bad.dirty is True  # all recomputed


def test_reevaluation_clears_deferred_pending_runs() -> None:
    cancelled: list[int] = []
    node = Node("File Input")
    node.content = SimpleNamespace(
        cancel_pending_evaluation=lambda: cancelled.append(1)
    )
    host = Host([node])
    host.doEvalOutputs = lambda *_a, **_k: None
    host._reevaluate_for_run([node])
    assert cancelled == [1]


def test_reevaluation_is_skipped_without_a_scene() -> None:
    host = Host([Node("a")])  # no doEvalOutputs: a unit-test double
    host._reevaluate_for_run(host.nodes)
    assert host.logged == []


def test_before_run_hooks_run_after_reevaluation_and_before_worker(
    monkeypatch, patched
) -> None:
    node = Node("a")
    node.content = SimpleNamespace(before_run=lambda: host.order.append("content"))
    host = Host([node])
    _sorted(monkeypatch, host.nodes)
    host.doEvalOutputs = lambda *_a, **_k: host.order.append("reeval")
    host.before_run_hooks = [lambda nodes: host.order.append("hook")]

    patched.on_start.append(lambda: host.order.append("worker"))

    assert host.executeWorkflow() is True
    assert host.order == ["reeval", "content", "hook", "worker"]
    host._workflow_worker = None
    # executeWorkflow builds a real NodeExecutor (one pooled thread) even with a
    # fake worker, and the fake worker never releases it.
    host._workflow_executor.shutdown()


def test_hook_exception_does_not_abort_run(monkeypatch, patched) -> None:
    node = Node("a")

    def bad() -> None:
        raise RuntimeError("hook")

    node.content = SimpleNamespace(before_run=bad)
    host = Host([node])
    _sorted(monkeypatch, host.nodes)
    host.before_run_hooks = [lambda nodes: (_ for _ in ()).throw(ValueError("x"))]
    assert host.executeWorkflow() is True
    assert len(patched) == 1
    host._workflow_worker = None


def test_worker_receives_policy_and_upstream(monkeypatch, patched) -> None:
    host = Host([Node("a")])
    _sorted(monkeypatch, host.nodes)
    host._run_policy = lambda: {"continue_on_error": True}
    host.executeWorkflow()
    assert patched[0].kwargs["continue_on_error"] is True
    assert patched[0].kwargs["upstream"] == {host.nodes[0]: []}
    host._workflow_worker = None
