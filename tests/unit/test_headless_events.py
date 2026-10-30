"""Event stream, log files and the supervisor (plan 08 3.7, 3.9)."""

from __future__ import annotations

import io
import json
import re

import pytest

from trigger_designer.core.headless.events import Emitter, rotate
from trigger_designer.core.headless.exit_codes import ExitCode
from trigger_designer.core.headless.supervisor import Supervisor

TS = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z$")


def test_json_mode_lines_parse_with_common_keys():
    out = io.BytesIO()
    emitter = Emitter("json", stream=out, run_id="r1")
    emitter.emit("run.started", workflow="w\xe9.tds")
    emitter.emit("node.finished", level="ERROR", node_id=5, error={"code": "X"})
    lines = out.getvalue().decode("utf-8").splitlines()
    parsed = [json.loads(line) for line in lines]
    for item in parsed:
        assert {"ts", "level", "event", "run_id"} <= set(item)
        assert TS.match(item["ts"])
        assert item["run_id"] == "r1"
    assert parsed[0]["workflow"] == "w\xe9.tds"
    assert next(iter(parsed[0])) == "ts"


def test_text_mode_writes_only_to_stderr(capsys):
    emitter = Emitter("text", run_id="r")
    emitter.emit("node.started", title="Formula")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "node.started" in captured.err and "Formula" in captured.err


def test_quiet_text_mode_keeps_warnings_and_run_lines(capsys):
    emitter = Emitter("text", quiet=True)
    emitter.emit("node.started", title="x")
    emitter.emit("warning", level="WARNING", message="careful")
    emitter.emit("run.finished", status="ok")
    err = capsys.readouterr().err
    assert "node.started" not in err and "careful" in err and "run.finished" in err


def test_log_file_is_jsonl_appended(tmp_path):
    path = tmp_path / "logs" / "a.jsonl"
    for _ in range(2):
        emitter = Emitter("text", path, run_id="r")
        emitter.emit("x", k="✓")
        emitter.close()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2 and rows[0]["k"] == "✓"


def test_rotation_keeps_three_backups(tmp_path):
    path = tmp_path / "a.jsonl"
    for generation in range(5):
        path.write_text(f"gen{generation}" * 300)
        rotate(path, max_bytes=1000)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["a.jsonl.1", "a.jsonl.2", "a.jsonl.3"]
    assert (tmp_path / "a.jsonl.1").read_text().startswith("gen4")


def test_broken_pipe_does_not_raise(tmp_path):
    class Broken:
        def write(self, _data):
            raise BrokenPipeError

        def flush(self):
            raise BrokenPipeError

    log = tmp_path / "l.jsonl"
    emitter = Emitter("json", log, stream=Broken())
    emitter.emit("a")
    emitter.emit("b")
    emitter.close()
    assert len(log.read_text().splitlines()) == 2


# ----------------------------------------------------------------- supervisor
def _supervisor(**kw):
    events, forced, exits = [], [], []
    sup = Supervisor(
        deadline_s=kw.get("deadline_s"),
        max_memory_mb=kw.get("max_memory_mb"),
        cancel_grace_s=kw.get("grace", 10),
        emit=lambda event, **f: events.append((event, f)),
        on_force=lambda code, reason: forced.append((code, reason)),
        exit_fn=exits.append,
    )
    return sup, events, forced, exits


def test_cancel_sets_flag_and_emits_once():
    sup, events, _forced, exits = _supervisor()
    sup.request_cancel()
    assert sup.cancel.is_set()
    assert [e for e, _ in events] == ["run.cancelling"]
    assert not exits


def test_second_signal_forces_immediately():
    sup, events, forced, exits = _supervisor()
    sup.request_cancel()
    sup.request_cancel()
    assert exits == [130] and forced == [(ExitCode.CANCELLED, "cancel_forced")]
    assert "run.cancel_forced" in [e for e, _ in events]


def test_grace_expiry_forces_exit():
    sup, _events, _forced, exits = _supervisor(grace=0.0)
    sup.request_cancel()
    import time

    time.sleep(0.01)
    sup.check_once()
    assert exits == [130]


def test_timeout_forces_exit_4():
    sup, events, forced, exits = _supervisor(deadline_s=0.001)
    import time

    time.sleep(0.01)
    sup.check_once()
    assert exits == [4] and forced[0][1] == "timeout"
    assert "run.timeout" in [e for e, _ in events]


def test_memory_ceiling_forces_exit_5():
    sup, events, _forced, exits = _supervisor(max_memory_mb=1)
    sup.check_once()
    assert exits == [5]
    assert "run.memory_exceeded" in [e for e, _ in events]


def test_force_exit_runs_once():
    sup, _events, forced, exits = _supervisor()
    sup.force_exit(ExitCode.TIMEOUT, "timeout")
    sup.force_exit(ExitCode.MEMORY, "memory_exceeded")
    assert exits == [4] and len(forced) == 1


@pytest.mark.parametrize("ok", [True])
def test_no_limits_never_force(ok):
    sup, _e, _f, exits = _supervisor()
    sup.check_once()
    assert exits == []
