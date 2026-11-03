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


#: Knobs that would let the caller's shell pick the CLI's Qt plugin set, style
#: or binding. The subprocess must behave like a plain ``trigger-designer-cli``
#: run from a clean shell, or a stray variable turns this suite red.
_FOREIGN_QT_ENV = (
    "QT_PLUGIN_PATH",
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    "QT_QPA_PLATFORMTHEME",
    "QT_QPA_GENERIC_PLUGINS",
    "QT_STYLE_OVERRIDE",
    "QT_API",
    "TRIGGER_CLI_QPA",
)


def cli_env(cwd: Path, extra_env: dict | None = None) -> dict:
    env = dict(os.environ)
    for name in _FOREIGN_QT_ENV:
        env.pop(name, None)
    for name in [key for key in env if key.startswith("TD_TEST_")]:
        env.pop(name, None)  # failure injection belongs to the test that asks
    env.pop("QT_QPA_PLATFORM", None)  # the CLI must set it itself
    env.update(
        {
            "PYTHONPATH": str(SRC),
            "PYTHONIOENCODING": "utf-8",
            "QT_API": "pyside6",
            "TRIGGER_DESIGNER_DATA_DIR": str(cwd / "data"),
            "TRIGGER_DESIGNER_STATE_DIR": str(cwd / "state"),
            **(extra_env or {}),
        }
    )
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
    from trigger_designer.cli.app import main

    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in (env or {})}
    os.environ.update({k: str(v) for k, v in (env or {}).items()})
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = int(main([str(a) for a in argv], hard_exit=False))
            except SystemExit as exc:
                code = int(exc.code or 0)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return InProc(code, out.getvalue(), err.getvalue())


# --------------------------------------------------------------- synthetic .tds
def synthetic_workflow(
    *,
    input_path: str = "in.csv",
    output_path: str = "out.csv",
    input_rel: str | None = None,
    filter_value: str | None = "x",
    filter_mode: str = "builder",
    extra_nodes: list | None = None,
) -> dict:
    """A small valid workflow dict: File Input -> Filter -> File Output."""
    input_content = {"filePath": input_path, "file_type": "csv", "selected_sheet": ""}
    if input_rel is not None:
        input_content["filePathRel"] = input_rel
    nodes = [
        {
            "id": 101,
            "op": "input.file_input",
            "title": "File Input",
            "inputs": [],
            "outputs": [{"id": 1011}],
            "content": input_content,
        },
        {
            "id": 102,
            "op": "preparation.filter",
            "title": "Filter",
            "inputs": [{"id": 1021}],
            "outputs": [{"id": 1022}],
            "content": {
                "settings": {"mode": filter_mode, "value": filter_value, "value2": ""}
            },
        },
        {
            "id": 103,
            "op": "input.file_output",
            "title": "File Output",
            "inputs": [{"id": 1031}],
            "outputs": [],
            "content": {"settings": {"filePath": output_path, "file_format": "csv"}},
        },
        *(extra_nodes or []),
    ]
    return {
        "workflow_metadata": {"schema_version": 2, "app_version": "0.1.0"},
        "nodes": nodes,
        "edges": [
            {"id": 9001, "start": 1011, "end": 1021},
            {"id": 9002, "start": 1022, "end": 1031},
        ],
    }


def write_workflow(path, data: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path
