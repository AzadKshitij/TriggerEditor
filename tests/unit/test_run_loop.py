"""The Qt-free run loop shared by the GUI worker and headless runners."""

from __future__ import annotations

import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from trigger_designer.core.ExecutionCheck.run_loop import LoopOutcome, run_nodes


class N:
    def __init__(self, name: str, ok: bool = True) -> None:
        self.name = name
        self.ok = ok

    def __repr__(self) -> str:
        return self.name


class FakeExecutor:
    def __init__(self) -> None:
        self.resets = 0

    def reset_cancel(self) -> None:
        self.resets += 1

    def execute_node(self, node):
        return SimpleNamespace(success=node.ok)


def drive(nodes, **kwargs):
    events: list[tuple] = []
    executor = kwargs.pop("executor", None) or FakeExecutor()
    outcome = run_nodes(
        nodes,
        executor,
        on_node_started=lambda n: events.append(("start", n.name, None)),
        on_node_finished=lambda n, r: events.append(("finish", n.name, r.success)),
        on_node_errored=lambda n, e: events.append(("error", n.name, str(e))),
        on_node_skipped=lambda n, b: events.append(("skip", n.name, b and b.name)),
        **kwargs,
    )
    return outcome, events


def test_all_ok() -> None:
    nodes = [N("a"), N("b"), N("c")]
    outcome, _ = drive(nodes)
    assert outcome == LoopOutcome(True, False, 3, (), ())


def test_stop_at_first_failure_has_no_skip_notifications() -> None:
    a, b, c = N("a"), N("b", ok=False), N("c")
    outcome, events = drive([a, b, c])
    assert events[-1] == ("finish", "b", False)
    assert not any(e[0] == "skip" for e in events)
    assert outcome.skipped == ()
    assert outcome.failed == (b,)
    assert outcome.success is False


def test_diamond_skips_only_dependents() -> None:
    a, b, c, d = N("a"), N("b", ok=False), N("c"), N("d")
    outcome, events = drive(
        [a, b, c, d],
        continue_on_error=True,
        upstream={b: [a], c: [a], d: [b, c]},
    )
    assert ("finish", "c", True) in events
    assert ("skip", "d", "b") in events
    assert outcome.failed == (b,) and outcome.skipped == (d,)
    assert outcome.success is False and outcome.executed == 3


def test_multi_output_failure_skips_both_branches() -> None:
    a, b, c = N("a", ok=False), N("b"), N("c")
    _, events = drive([a, b, c], continue_on_error=True, upstream={b: [a], c: [a]})
    assert ("skip", "b", "a") in events and ("skip", "c", "a") in events


def test_skipped_blocker_is_first_blocked_parent_in_input_order() -> None:
    a, b, d = N("a", ok=False), N("b", ok=False), N("d")
    _, events = drive([a, b, d], continue_on_error=True, upstream={d: [b, a]})
    assert ("skip", "d", "b") in events


def test_transitive_skip() -> None:
    a, b, c = N("a", ok=False), N("b"), N("c")
    _, events = drive([a, b, c], continue_on_error=True, upstream={b: [a], c: [b]})
    assert ("skip", "b", "a") in events
    assert ("skip", "c", "b") in events


def test_cancel_before_start_skips_everything() -> None:
    cancel = threading.Event()
    cancel.set()
    nodes = [N("a"), N("b")]
    outcome, events = drive(nodes, cancel=cancel)
    assert events == [("skip", "a", None), ("skip", "b", None)]
    assert outcome.cancelled is True and outcome.success is False
    assert outcome.executed == 0


def test_cancel_between_nodes() -> None:
    cancel = threading.Event()
    nodes = [N("a"), N("b"), N("c")]
    events: list[tuple] = []

    def finished(node, result) -> None:
        events.append(("finish", node.name))
        cancel.set()

    outcome = run_nodes(
        nodes,
        FakeExecutor(),
        cancel=cancel,
        on_node_finished=finished,
        on_node_skipped=lambda n, b: events.append(("skip", n.name, b)),
    )
    assert events == [("finish", "a"), ("skip", "b", None), ("skip", "c", None)]
    assert outcome.executed == 1 and outcome.cancelled is True


def test_errored_callback_when_execute_node_raises() -> None:
    class Boom:
        def execute_node(self, node):
            raise RuntimeError("boom")

    a = N("a")
    outcome, events = drive([a, N("b")], executor=Boom())
    assert events == [("start", "a", None), ("error", "a", "boom")]
    assert outcome.failed == (a,) and outcome.executed == 0


def test_callback_exception_propagates() -> None:
    def finished(node, result) -> None:
        raise RuntimeError("policy")

    with pytest.raises(RuntimeError, match="policy"):
        run_nodes([N("a")], FakeExecutor(), on_node_finished=finished)


def test_result_without_success_attribute_counts_as_failure() -> None:
    class Odd:
        def execute_node(self, node):
            return object()

    outcome = run_nodes([N("a")], Odd())
    assert outcome.success is False and len(outcome.failed) == 1


def test_executor_reset_cancel_is_called_once() -> None:
    executor = FakeExecutor()
    drive([N("a"), N("b")], executor=executor)
    assert executor.resets == 1


def test_keyboard_interrupt_is_not_swallowed() -> None:
    class Stop:
        def execute_node(self, node):
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_nodes([N("a")], Stop())


def test_module_is_qt_free() -> None:
    code = (
        "import sys, trigger_designer.core.ExecutionCheck.run_loop\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "('qtpy', 'PyQt6', 'PySide6', 'PyQt5', 'PySide2')]\n"
        "assert not bad, bad\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
