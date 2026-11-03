"""Printing helpers shared by the commands (Qt-free)."""

from __future__ import annotations

import sys
from typing import Any

from trigger_designer.core.headless.exit_codes import CliError


def dumps(obj: Any) -> str:
    import orjson

    return orjson.dumps(
        obj, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS
    ).decode("utf-8")


def print_json(obj: Any, stream=None) -> None:
    out = stream or sys.stdout
    out.write(dumps(obj) + "\n")
    out.flush()


def wants_json(args) -> bool:
    return (
        getattr(args, "format", None) == "json"
        or getattr(args, "log_format", None) == "json"
    )


def print_error(args, exc: CliError) -> None:
    if getattr(args, "format", None) == "json":
        print_json({"error": exc.to_dict()})
        return
    sys.stderr.write(f"error [{exc.td_code}]: {exc.message}\n")
    if exc.hint:
        sys.stderr.write(f"  hint: {exc.hint}\n")
