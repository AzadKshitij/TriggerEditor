"""Headless command line (plan 08). Importing this package stays cheap."""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    from trigger_designer.cli.app import main as _main

    return _main(argv)
