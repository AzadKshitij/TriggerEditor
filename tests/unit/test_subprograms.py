"""``tds mcp`` / ``tds open`` and how a frozen build starts its helper."""

from __future__ import annotations

import subprocess
import sys

import pytest

from trigger_designer.agent.launcher import cli_command
from trigger_designer.cli import app, subprograms


def test_helper_from_source_is_python_dash_m() -> None:
    assert cli_command() == [sys.executable, "-m", "trigger_designer.cli"]
    assert cli_command("py") == ["py", "-m", "trigger_designer.cli"]


def test_helper_when_frozen_is_the_program_itself(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert cli_command() == [sys.executable]


def test_mcp_is_dispatched_before_the_parser_with_its_own_options(
    monkeypatch,
) -> None:
    seen: list[list[str]] = []
    monkeypatch.setitem(app.SUBPROGRAMS, "mcp", lambda argv: seen.append(argv) or 0)
    assert app.main(["mcp", "--workspace", "D", "--policy", "P"]) == 0
    assert seen == [["--workspace", "D", "--policy", "P"]]


def test_open_starts_the_editor_detached_with_the_files(monkeypatch) -> None:
    started: list[list[str]] = []
    monkeypatch.setattr(
        subprocess, "Popen", lambda cmd, **kw: started.append(cmd) or None
    )
    assert subprograms.run_open(["a.tds"]) == 0
    assert started[0][-1] == "a.tds"
    assert started[0][:3] == [sys.executable, "-m", "trigger_designer.main"]


def test_open_without_an_editor_beside_tds_says_so(
    monkeypatch, capsys, tmp_path
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "tds.exe"))
    assert subprograms.run_open([]) == 2
    assert "not installed" in capsys.readouterr().err


def test_mcp_is_not_imported_by_other_commands() -> None:
    code = (
        "import sys; from trigger_designer.cli import main; "
        "main(['--version'], hard_exit=False) if False else None; "
        "import trigger_designer.cli.app; "
        "print('mcp' in sys.modules)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"


@pytest.mark.parametrize("name", ["mcp", "open"])
def test_subprogram_names_do_not_clash_with_commands(name) -> None:
    from trigger_designer.cli.parser import build_parser

    sub = next(
        a
        for a in build_parser()._actions
        if getattr(a, "choices", None) and "run" in a.choices
    )
    assert name not in sub.choices
