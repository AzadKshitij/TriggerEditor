"""How to start a helper CLI command from the MCP server.

From source that is ``python -m trigger_designer.cli``. In a packaged build
``sys.executable`` is ``tds.exe`` itself, which understands CLI commands, so
the helper is the same program.
"""

from __future__ import annotations

import sys


def cli_command(python: str | None = None) -> list[str]:
    if python is None and getattr(sys, "frozen", False):
        return [sys.executable]
    return [python or sys.executable, "-m", "trigger_designer.cli"]
