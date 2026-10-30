"""``run_workflow_file`` as a library call: no window, no GUI entry point."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from tests.support.cli import cli_env
from tests.support.corpus import FILE_OUTPUT_CASES
from tests.support.workflows import materialize

pytestmark = pytest.mark.e2e

CASE = next(c for c in FILE_OUTPUT_CASES if c.name == "formula")

SCRIPT = """
import json, sys
from trigger_designer.core.headless.runner import run_workflow_file
out = run_workflow_file({path!r}, allow_unapproved=True, record_dir={rec!r}, no_hash=True)
second = run_workflow_file({path!r}, allow_unapproved=True, record_dir={rec!r})
from qtpy.QtGui import QGuiApplication
print(json.dumps({{
    "codes": [out.exit_code, second.exit_code],
    "status": out.status,
    "platform": QGuiApplication.platformName(),
    "main_imported": "trigger_designer.main" in sys.modules,
    "record": bool(out.record_path),
    "nodes_ok": out.nodes_ok,
}}))
"""


def test_no_window_is_created_and_two_runs_share_one_process(tmp_path):
    m = materialize(CASE, tmp_path)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            SCRIPT.format(path=str(m.path), rec=str(tmp_path / "rec")),
        ],
        cwd=tmp_path,
        env=cli_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    line = next(x for x in proc.stdout.splitlines() if x.startswith("{"))
    data = json.loads(line)
    assert data["codes"] == [0, 0] and data["status"] == "ok"
    assert data["platform"] == "offscreen"
    assert data["main_imported"] is False
    assert data["record"] and data["nodes_ok"] == 3
