"""Dispatch: parse, build the context, run a command, map errors to exit codes."""

from __future__ import annotations

import sys
import traceback

from trigger_designer.cli.output import print_error
from trigger_designer.cli.parser import build_parser
from trigger_designer.core.headless.context import CliContext
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.state import state_dir


def load_command(name: str):
    """The module of a command. Spelled out as plain imports so that a frozen
    build (PyInstaller) finds every command without hidden-import lists."""
    if name == "run":
        from trigger_designer.cli.commands import run as module
    elif name == "validate":
        from trigger_designer.cli.commands import validate as module
    elif name == "info":
        from trigger_designer.cli.commands import info as module
    elif name == "approve":
        from trigger_designer.cli.commands import approve as module
    elif name == "verify-log":
        from trigger_designer.cli.commands import verify_log as module
    elif name == "params":
        from trigger_designer.cli.commands import params as module
    elif name == "paths":
        from trigger_designer.cli.commands import paths as module
    elif name == "schedule":
        from trigger_designer.cli.commands import schedule as module
    else:  # pragma: no cover - argparse already rejected unknown commands
        raise KeyError(name)
    return module


def make_context(args) -> CliContext:
    return CliContext(state=state_dir(getattr(args, "state_dir", None)))


def main(argv: list[str] | None = None, *, hard_exit: bool = True) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)  # SystemExit(64) on usage errors
    try:
        module = load_command(args.command)
        ctx = make_context(args)
        ctx.extra["hard_exit"] = hard_exit
        return int(module.execute(args, ctx))
    except CliError as exc:
        print_error(args, exc)
        return int(exc.code)
    except KeyboardInterrupt:
        return int(ExitCode.CANCELLED)
    except Exception:  # noqa: BLE001 - last line of defence
        traceback.print_exc(file=sys.stderr)
        return int(ExitCode.INTERNAL)
