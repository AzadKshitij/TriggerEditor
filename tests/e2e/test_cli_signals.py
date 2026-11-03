"""Cancel, timeout and memory limits of ``trigger-designer-cli run`` (plan 08 3.7)."""

from __future__ import annotations

import json
import os
import signal
import time

import pytest

from tests.support.cli import run_cli, spawn_cli
from tests.support.corpus import FILE_OUTPUT_CASES
from tests.support.workflows import materialize

pytestmark = pytest.mark.e2e

CASE = next(c for c in FILE_OUTPUT_CASES if c.name == "formula")
HOOKS = {"TD_TEST_HOOKS": "1"}
SEND = signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT


def _start(tmp_path, *extra, sleep: str, env=None):
    m = materialize(CASE, tmp_path)
    proc = spawn_cli(
        "run",
        m.path,
        "--allow-unapproved",
        "--log-format",
        "json",
        "--record-dir",
        tmp_path / "rec",
        *extra,
        cwd=tmp_path,
        extra_env={**HOOKS, "TD_TEST_SLEEP_BEFORE_NODE": sleep, **(env or {})},
        new_group=True,
    )
    return m, proc


def _read_until(proc, event: str, title: str, seen: list) -> None:
    for line in proc.stdout:
        row = json.loads(line)
        seen.append(row)
        if row["event"] == event and row.get("title") == title:
            return
    raise AssertionError(
        f"never saw {event} for {title}; stderr={proc.stderr.read()[-800:]}"
    )


def _finish(proc, seen: list, timeout=60) -> list:
    out, _err = proc.communicate(timeout=timeout)
    seen.extend(json.loads(line) for line in out.splitlines() if line.strip())
    return seen


def _records(tmp_path):
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in (tmp_path / "rec").glob("*.json")
        if p.name != "hash_cache.json"
    ]


def test_ctrl_break_force_exits_130(tmp_path):
    m, proc = _start(tmp_path, "--cancel-grace", "2", sleep="Formula:30")
    seen: list = []
    try:
        _read_until(proc, "node.started", "Formula", seen)
        t0 = time.monotonic()
        proc.send_signal(SEND)
        _finish(proc, seen, timeout=30)
        elapsed = time.monotonic() - t0
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 130
    assert elapsed < 15
    names = [r["event"] for r in seen]
    assert "run.cancelling" in names and "run.cancel_forced" in names
    assert names.index("run.cancelling") < names.index("run.cancel_forced")
    records = _records(tmp_path)
    assert len(records) == 1 and records[0]["status"] == "cancelled"
    assert list(m.out_dir.iterdir()) == []


def test_ctrl_break_graceful_between_nodes(tmp_path):
    m, proc = _start(tmp_path, sleep="Formula:3")
    seen: list = []
    try:
        _read_until(proc, "node.started", "Formula", seen)
        time.sleep(0.5)
        proc.send_signal(SEND)
        _finish(proc, seen, timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 130
    names = [r["event"] for r in seen]
    assert "run.cancel_forced" not in names
    finished = [r["title"] for r in seen if r["event"] == "node.finished"]
    assert finished == ["File Input", "Formula"]
    assert any(r["event"] == "node.skipped" for r in seen)
    assert list(m.out_dir.iterdir()) == []  # nothing committed
    assert _records(tmp_path)[0]["status"] == "cancelled"


def test_second_signal_forces_immediately(tmp_path):
    _m, proc = _start(tmp_path, sleep="Formula:30")
    seen: list = []
    try:
        _read_until(proc, "node.started", "Formula", seen)
        proc.send_signal(SEND)
        time.sleep(0.4)
        t0 = time.monotonic()
        proc.send_signal(SEND)
        _finish(proc, seen, timeout=30)
        elapsed = time.monotonic() - t0
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 130
    assert elapsed < 8
    assert any(r["event"] == "run.cancel_forced" for r in seen)


def test_timeout_exit_4(tmp_path):
    m = materialize(CASE, tmp_path)
    t0 = time.monotonic()
    proc = run_cli(
        "run",
        m.path,
        "--allow-unapproved",
        "--log-format",
        "json",
        "--record-dir",
        tmp_path / "rec",
        "--timeout",
        "6",
        cwd=tmp_path,
        extra_env={**HOOKS, "TD_TEST_SLEEP_BEFORE_NODE": "Formula:30"},
        timeout=60,
    )
    assert proc.returncode == 4, proc.stderr[-800:]
    assert time.monotonic() - t0 < 40
    rows = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert any(r["event"] == "run.timeout" for r in rows)
    done = rows[-1]
    assert done["event"] == "run.finished" and done["exit_code"] == 4
    record = _records(tmp_path)[0]
    assert record["status"] == "failed"
    failed = [n for n in record["nodes"] if n["status"] == "failed"]
    assert failed and failed[0]["error"]["code"] == "TD-RUN-001"
    assert list(m.out_dir.iterdir()) == []


def test_max_memory_exit_5_and_generous_limit_passes(tmp_path):
    m = materialize(CASE, tmp_path)
    low = run_cli(
        "run",
        m.path,
        "--allow-unapproved",
        "--log-format",
        "json",
        "--record-dir",
        tmp_path / "rec",
        "--max-memory",
        "64",
        cwd=tmp_path,
        extra_env={**HOOKS, "TD_TEST_SLEEP_BEFORE_NODE": "Formula:30"},
        timeout=90,
    )
    assert low.returncode == 5, low.stderr[-800:]
    rows = [json.loads(line) for line in low.stdout.splitlines() if line.strip()]
    assert any(r["event"] == "run.memory_exceeded" for r in rows)
    assert list(m.out_dir.iterdir()) == []
    high = run_cli(
        "run",
        m.path,
        "--allow-unapproved",
        "--log-format",
        "json",
        "--record-dir",
        tmp_path / "rec2",
        "--max-memory",
        "8192",
        cwd=tmp_path,
    )
    assert high.returncode == 0, high.stderr[-800:]
