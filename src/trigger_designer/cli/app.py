"""Dispatch: parse, build the context, run a command, map errors to exit codes."""

from __future__ import annotations

import importlib
import sys
import traceback

from trigger_designer.cli.output import print_error
from trigger_designer.cli.parser import COMMAND_MODULES, build_parser
from trigger_designer.core.headless.context import CliContext
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.state import state_dir


def make_context(args) -> CliContext:
    return CliContext(state=state_dir(getattr(args, "state_dir", None)))


def main(argv: list[str] | None = None, *, hard_exit: bool = True) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)  # SystemExit(64) on usage errors
    try:
        module = importlib.import_module(COMMAND_MODULES[args.command])
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
