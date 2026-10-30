"""Regression tests for CLI defects found while documenting plan 08."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from tests.support.cli import cli_env, run_cli, synthetic_workflow, write_workflow

pytestmark = pytest.mark.e2e


def _wf(tmp_path, **kw):
    return write_workflow(tmp_path / "wf.tds", synthetic_workflow(**kw))


def test_approve_with_stdin_nul_exits_64_not_traceback(tmp_path):
    """C1: ``NUL`` reports isatty() true; input() then raises EOFError."""
    wf = _wf(tmp_path)
    with open(os.devnull, "rb") as nul:
        proc = subprocess.run(
            [sys.executable, "-m", "trigger_designer.cli", "approve", str(wf)],
            cwd=tmp_path,
            env=cli_env(tmp_path),
            stdin=nul,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=False,
        )
    assert proc.returncode == 64, proc.stderr
    assert "Traceback" not in proc.stderr
    assert "--yes" in proc.stderr


def test_info_survives_cp1252_stdout(tmp_path):
    """C2: a non-cp1252 path must not crash a cp1252 pipe."""
    wf = _wf(tmp_path, input_path="C:/данные/in.csv")
    env = {"PYTHONIOENCODING": "cp1252"}
    # run_cli forces utf-8 decoding; stdout bytes are cp1252 or replaced.
    proc = run_cli("info", wf, cwd=tmp_path, extra_env=env)
    assert proc.returncode == 0, proc.stderr
    assert "Traceback" not in proc.stderr


def _info_bytes(tmp_path, env_extra):
    wf = _wf(tmp_path, input_path="C:/данные/in.csv")
    env = cli_env(tmp_path)
    env.pop("PYTHONIOENCODING")
    env.pop("PYTHONUTF8", None)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "trigger_designer.cli", "info", str(wf)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        timeout=120,
        check=False,
    )


def test_piped_stdout_defaults_to_utf8(tmp_path):
    proc = _info_bytes(tmp_path, {})
    assert proc.returncode == 0, proc.stderr
    assert "данные".encode() in proc.stdout


def test_explicit_cp1252_pipe_replaces_unencodable(tmp_path):
    proc = _info_bytes(tmp_path, {"PYTHONIOENCODING": "cp1252"})
    assert proc.returncode == 0, proc.stderr
    assert b"Traceback" not in proc.stderr
    assert b"C:/??????/in.csv" in proc.stdout


# ------------------------------------------------------------------ C5 noise
def _formula(tmp_path):
    from tests.support.corpus import FILE_OUTPUT_CASES
    from tests.support.workflows import materialize

    case = {c.name: c for c in FILE_OUTPUT_CASES}["formula"]
    return materialize(case, tmp_path)


def _assert_quiet(stderr: str):
    assert "icon:" not in stderr
    assert "<class" not in stderr
    assert "QPixmap" not in stderr
    assert "\x1b[" not in stderr
    assert "Traceback" not in stderr


def test_run_stderr_has_no_editor_prints(tmp_path):
    m = _formula(tmp_path)
    proc = run_cli(
        "run", m.path, "--allow-unapproved", "--record-dir", tmp_path / "rec",
        cwd=tmp_path,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr[-1500:]
    _assert_quiet(proc.stderr)
    assert "run.finished" in proc.stderr


def test_deep_validate_stderr_is_clean_and_vv_shows_the_prints(tmp_path):
    m = _formula(tmp_path)
    proc = run_cli("validate", m.path, "--deep", cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr[-1500:]
    _assert_quiet(proc.stderr)
    assert proc.stderr.strip() == ""
    loud = run_cli("validate", m.path, "--deep", "-vv", cwd=tmp_path)
    assert loud.returncode == 0
    assert "icon:" in loud.stderr and "\x1b[" not in loud.stderr
