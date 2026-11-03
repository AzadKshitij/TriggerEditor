"""Qt-adjacent helpers of the headless session that need no window."""

from __future__ import annotations

import pytest

from trigger_designer.qt import headless


class _Content:
    def __init__(self, hook=None):
        if hook:
            self.before_run = hook


class _Node:
    def __init__(self, nid, title, content):
        self.id, self.node_title, self.content = nid, title, content


def _session(nodes):
    session = headless.HeadlessSession.__new__(headless.HeadlessSession)
    session.report = headless.LoadReport(ok=True, nodes=nodes)
    return session


def test_before_run_hooks_run_once_and_failures_are_warnings():
    calls, warnings = [], []

    def good():
        calls.append("good")

    def bad():
        raise RuntimeError("nope")

    nodes = [
        _Node(1, "A", _Content(good)),
        _Node(2, "B", _Content(bad)),
        _Node(3, "C", _Content()),
        _Node(4, "D", None),
    ]
    _session(nodes).before_run(
        lambda message, node_id=None: warnings.append((message, node_id))
    )
    assert calls == ["good"]
    assert len(warnings) == 1 and "before_run failed for B" in warnings[0][0]
    assert warnings[0][1] == 2


def test_test_hooks_are_inert_without_the_switch(monkeypatch):
    monkeypatch.delenv("TD_TEST_HOOKS", raising=False)
    monkeypatch.setenv("TD_TEST_FAIL_NODE", "A")
    node = _Node(1, "A", None)
    node.get_code = lambda: "x = 1\n"
    headless.apply_test_hooks(node)
    assert node.get_code() == "x = 1\n"


def test_test_hooks_replace_code_when_enabled(monkeypatch):
    monkeypatch.setenv("TD_TEST_HOOKS", "1")
    monkeypatch.setenv("TD_TEST_FAIL_NODE", "A")
    node = _Node(1, "A", None)
    headless.apply_test_hooks(node)
    assert "boom" in node.get_code()


def test_duration_parses_executor_timestamps():
    class R:
        started_at = "2026-10-30T10:00:00.000000Z"
        finished_at = "2026-10-30T10:00:01.500000Z"

    assert headless._duration(R()) == pytest.approx(1.5)
    assert headless._duration(object()) == 0.0
