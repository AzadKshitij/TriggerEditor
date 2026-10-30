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
