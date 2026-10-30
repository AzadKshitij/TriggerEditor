"""``run``: execute a workflow headless."""

from __future__ import annotations

import contextlib
import os
import sys

from trigger_designer.core.headless.events import Emitter, capture_stdout_channel
from trigger_designer.core.headless.plan import RunOptions


def _summary_block(outcome) -> str | None:
    if outcome.status == "ok" or not outcome.errors:
        return None
    first = outcome.errors[0]
    where = f"node '{first.get('node')}'" if first.get("node") else "the run"
    hint = f" - {first['hint']}" if first.get("hint") else ""
    return f"FAILED at {where} [{first.get('code')}] {first.get('title')}{hint}"


def execute(args, ctx) -> int:
    from trigger_designer.core.headless.runner import run_with_options

    hard = bool(ctx.extra.get("hard_exit", True))
    opts = RunOptions.from_args(args)
    opts.capture_logs = hard
    # A hard exit means this process is the CLI: keep the real stdout for our
    # JSON lines and send everything else to stderr (plan 08 X9).
    stream = capture_stdout_channel() if hard else None
    emitter = Emitter(args.log_format, args.log_file, stream=stream, quiet=args.quiet)
    ctx.emitter = emitter
    outcome = run_with_options(args.workflow, opts, ctx, install_signals=hard)
    block = _summary_block(outcome)
    if block and args.log_format == "text":
        sys.stderr.write(block + "\n")
    emitter.close()
    if hard:
        with contextlib.suppress(Exception):
            sys.stderr.flush()
        os._exit(outcome.exit_code)
    return outcome.exit_code
