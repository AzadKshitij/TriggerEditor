"""The GUI worker runs the same loop as ``run_nodes`` (parity)."""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy.QtWidgets import QApplication

from trigger_designer.core.ExecutionCheck.run_loop import run_nodes
from trigger_designer.qt.helpers.workflow_worker import WorkflowWorker

_APP = QApplication.instance() or QApplication([])


class N:
    def __init__(self, name: str, ok: bool = True) -> None:
        self.name = name
        self.ok = ok

    def __repr__(self) -> str:
        return self.name


class FakeExecutor:
    def execute_node(self, node):
        return SimpleNamespace(success=node.ok)


def _graph():
    a, b, c, d = N("a"), N("b", ok=False), N("c"), N("d")
    return [a, b, c, d], {b: [a], c: [a], d: [b, c]}


def _direct(nodes, upstream, continue_on_error):
    events: list[tuple] = []
    outcome = run_nodes(
        nodes,
        FakeExecutor(),
        continue_on_error=continue_on_error,
        upstream=upstream,
        on_node_started=lambda n: events.append(("start", n.name)),
        on_node_finished=lambda n, r: events.append(("finish", n.name, r.success)),
        on_node_errored=lambda n, e: events.append(("error", n.name)),
        on_node_skipped=lambda n, b: events.append(("skip", n.name, b and b.name)),
    )
    return outcome, events


def _worker(nodes, upstream, continue_on_error):
    events: list[tuple] = []
    worker = WorkflowWorker(
        nodes, FakeExecutor(), continue_on_error=continue_on_error, upstream=upstream
    )
    worker.nodeStarted.connect(lambda n: events.append(("start", n.name)))
    worker.nodeFinished.connect(
        lambda n, r: events.append(("finish", n.name, r.success))
    )
    worker.nodeErrored.connect(lambda n, e: events.append(("error", n.name)))
    worker.nodeSkipped.connect(
        lambda n, b: events.append(("skip", n.name, b and b.name))
    )
    finished: list[bool] = []
    worker.workflowFinished.connect(finished.append)
    worker.run()
    return worker, events, finished


def test_worker_matches_run_nodes_when_continuing() -> None:
    nodes, upstream = _graph()
    outcome, expected = _direct(nodes, upstream, True)
    worker, events, finished = _worker(nodes, upstream, True)
    assert events == expected
    assert worker.outcome == outcome
    assert worker.cancelled == outcome.cancelled
    assert finished == [False]


def test_worker_matches_run_nodes_when_stopping_at_first_failure() -> None:
    nodes, upstream = _graph()
    outcome, expected = _direct(nodes, upstream, False)
    worker, events, _ = _worker(nodes, upstream, False)
    assert events == expected
    assert worker.outcome == outcome


def test_worker_default_arguments_keep_old_behaviour() -> None:
    nodes = [N("a"), N("b", ok=False), N("c")]
    worker = WorkflowWorker(nodes, FakeExecutor())
    seen: list[str] = []
    worker.nodeStarted.connect(lambda n: seen.append(n.name))
    worker.run()
    assert seen == ["a", "b"]
    assert worker.cancelled is False


def test_cancel_before_run_skips_every_node() -> None:
    nodes = [N("a"), N("b")]
    worker = WorkflowWorker(nodes, FakeExecutor())
    skipped: list[tuple] = []
    worker.nodeSkipped.connect(lambda n, b: skipped.append((n.name, b)))
    finished: list[bool] = []
    worker.workflowFinished.connect(finished.append)
    worker.request_cancel()
    assert worker._cancel_requested is True
    worker.run()
    assert skipped == [("a", None), ("b", None)]
    assert worker.cancelled is True
    assert finished == [False]


def test_direct_upstream_reads_input_socket_edges() -> None:
    from trigger_designer.qt.helpers.workflow_execution_mixin import _direct_upstream

    class Sock:
        def __init__(self, node) -> None:
            self.node = node
            self.edges: list = []

    class Edge:
        def __init__(self, other) -> None:
            self.other = other

        def getOtherSocket(self, socket):
            return self.other

    parent, child = N("parent"), N("child")
    parent.inputs = []
    out_socket = Sock(parent)
    in_socket = Sock(child)
    in_socket.edges.append(Edge(out_socket))
    child.inputs = [in_socket]
    assert _direct_upstream([parent, child]) == {parent: [], child: [parent]}
