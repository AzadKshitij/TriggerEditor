"""Helpers for CLI tests: real subprocess runs and in-process calls."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"


def cli_env(cwd: Path, extra_env: dict | None = None) -> dict:
    env = {
        **os.environ,
        "PYTHONPATH": str(SRC),
        "PYTHONIOENCODING": "utf-8",
        "TRIGGER_DESIGNER_DATA_DIR": str(cwd / "data"),
        "TRIGGER_DESIGNER_STATE_DIR": str(cwd / "state"),
        **(extra_env or {}),
    }
    env.pop("QT_QPA_PLATFORM", None)  # the CLI must set it itself
    return env


def run_cli(*args, cwd, extra_env=None, timeout=180, input=None):
    """``python -m trigger_designer.cli ...`` in a real subprocess."""
    cwd = Path(cwd)
    cwd.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, "-m", "trigger_designer.cli", *map(str, args)],
        cwd=cwd,
        env=cli_env(cwd, extra_env),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        input=input,
        check=False,
    )


def spawn_cli(*args, cwd, extra_env=None, new_group=False):
    """A running CLI process (stdout/stderr piped) for signal and lock tests."""
    cwd = Path(cwd)
    cwd.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if new_group and os.name == "nt" else 0
    return subprocess.Popen(
        [sys.executable, "-m", "trigger_designer.cli", *map(str, args)],
        cwd=cwd,
        env=cli_env(cwd, extra_env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        creationflags=flags,
    )


def events(proc) -> list[dict]:
    """Every non-empty stdout line must be a JSON object."""
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


@dataclass
class InProc:
    code: int
    stdout: str
    stderr: str

    def json(self):
        return json.loads(self.stdout)


def call_main(argv, *, env: dict | None = None) -> InProc:
    """Run ``main(argv)`` in this process, capturing stdout/stderr and exit code."""
    from trigger_designer.cli import main

    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in (env or {})}
    os.environ.update({k: str(v) for k, v in (env or {}).items()})
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = int(main([str(a) for a in argv]))
            except SystemExit as exc:
                code = int(exc.code or 0)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return InProc(code, out.getvalue(), err.getvalue())
