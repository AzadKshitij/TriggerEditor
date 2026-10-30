"""The per-workflow run lock (plan 08 S5)."""

from __future__ import annotations

import json
import os

import pytest

from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.locks import RunLock, lock_path


def test_second_acquire_is_busy(tmp_path):
    path = tmp_path / "x.lock"
    first = RunLock(path, "run1")
    first.acquire()
    with pytest.raises(CliError) as exc:
        RunLock(path, "run2").acquire()
    assert exc.value.code == ExitCode.BUSY and exc.value.td_code == "TD-CLI-012"
    first.release()
    assert not path.exists()
    RunLock(path, "run3").acquire()


def test_stale_lock_is_taken_over_and_leftovers_swept(tmp_path):
    path = tmp_path / "x.lock"
    staged = tmp_path / ".o.tdtmp-1.csv"
    staged.write_text("partial")
    final = tmp_path / "o.csv"
    backup = tmp_path / ".o.tdbak-1.csv"
    backup.write_text("previous output")  # killed between the two commit phases
    path.write_text(
        json.dumps(
            {
                "pid": 2**22 + 7,
                "create_time": 1.0,
                "staged": [
                    {"final": str(final), "staged": str(staged), "backup": str(backup)}
                ],
            }
        )
    )
    RunLock(path, "new").acquire()
    assert not staged.exists()
    assert final.read_text() == "previous output"  # restored, not lost
    assert not backup.exists()


def test_alive_pid_with_other_create_time_is_stale(tmp_path):
    path = tmp_path / "x.lock"
    path.write_text(
        json.dumps({"pid": os.getpid(), "create_time": 12345.0, "staged": []})
    )
    RunLock(path, "n").acquire()


def test_note_staged_is_persisted_and_swept_by_next_run(tmp_path):
    path = tmp_path / "x.lock"
    lock = RunLock(path, "a")
    lock.acquire()
    leftover = tmp_path / ".t.tdtmp-1.csv"
    leftover.write_text("x")
    lock.note_staged([{"final": str(tmp_path / "t.csv"), "staged": str(leftover)}])
    assert json.loads(path.read_text())["staged"][0]["staged"] == str(leftover)
    # pretend the owner died
    info = json.loads(path.read_text())
    info["pid"] = 2**22 + 9
    path.write_text(json.dumps(info))
    RunLock(path, "b").acquire()
    assert not leftover.exists()


def test_lock_name_is_stable_and_case_insensitive_on_nt(tmp_path):
    a = lock_path(tmp_path, str(tmp_path / "wf.tds"))
    assert a == lock_path(tmp_path, str(tmp_path / "wf.tds"))
    assert a != lock_path(tmp_path, str(tmp_path / "other.tds"))
    if os.name == "nt":
        assert a == lock_path(tmp_path, str(tmp_path / "WF.TDS"))
