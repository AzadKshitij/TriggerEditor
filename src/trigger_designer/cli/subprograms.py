"""``tds mcp`` and ``tds open``: the two commands that are not workflow commands.

They are dispatched before the argument parser so that ``tds mcp`` hands every
option to the MCP server and the MCP package is imported only when it is used.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_mcp(argv: list[str]) -> int:
    from trigger_designer.agent.server import main as serve

    serve(argv)
    return 0


def editor_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).with_name("TriggerEditor.exe"))]
    return [sys.executable, "-m", "trigger_designer.main"]


def run_open(argv: list[str]) -> int:
    command = editor_command()
    if getattr(sys, "frozen", False) and not Path(command[0]).exists():
        print("The editor is not installed beside tds.", file=sys.stderr)
        return 2
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [*command, *argv],
        creationflags=flags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return 0


SUBPROGRAMS = {"mcp": run_mcp, "open": run_open}
