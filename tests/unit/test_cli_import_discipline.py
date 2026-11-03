"""The read-only commands never import Qt, Polars, DuckDB or the GUI entry point."""

from __future__ import annotations

import subprocess
import sys

import pytest

from tests.support.cli import cli_env

_CHECK = (
    "import sys\n"
    "from trigger_designer.cli import main\n"
    "try:\n"
    "    rc = main({argv!r})\n"
    "except SystemExit as exc:\n"
    "    rc = exc.code\n"
    "bad = [m for m in sys.modules if m.split('.')[0] in {banned!r}]\n"
    "assert not bad, bad[:8]\n"
    "assert 'trigger_designer.main' not in sys.modules\n"
    "print('RC', rc)\n"
)

QT_FREE = ("PyQt6", "qtpy", "polars", "duckdb")

CASES = [
    (["--version"], QT_FREE),
    (["--help"], QT_FREE),
    (["run", "--help"], QT_FREE),
    (["info", "{wf}"], QT_FREE),
    (["validate", "{wf}"], QT_FREE),
    (["approve", "--list"], QT_FREE),
    (["params", "list", "{wf}"], QT_FREE),
    (["paths", "{wf}"], QT_FREE),
    (["schedule", "list"], QT_FREE),
    (["verify-log"], ("PyQt6", "qtpy")),
]


@pytest.mark.parametrize(
    "argv,banned", CASES, ids=lambda v: " ".join(v) if isinstance(v, list) else ""
)
def test_command_stays_light(argv, banned, tmp_path):
    wf = tmp_path / "wf.tds"
    wf.write_text(
        '{"workflow_metadata": {"schema_version": 2}, "nodes": [], "edges": []}',
        encoding="utf-8",
    )
    argv = [a.replace("{wf}", str(wf)) for a in argv]
    proc = subprocess.run(
        [sys.executable, "-c", _CHECK.format(argv=argv, banned=banned)],
        cwd=tmp_path,
        env=cli_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "RC" in proc.stdout
