"""``schedule add|list|show|remove``: Windows Task Scheduler wrapper."""

from __future__ import annotations

import contextlib
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from trigger_designer.cli.output import print_json
from trigger_designer.core.headless import schedule as sched
from trigger_designer.core.headless.approvals import store_for
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.params import (
    apply_params,
    parse_cli_params,
    read_param_defs,
)
from trigger_designer.core.headless.paths import resolve_workflow_path
from trigger_designer.core.headless.state import ensure
from trigger_designer.core.headless.workflow_file import read_workflow


def _absolute_params(doc, raw: dict[str, str]) -> dict[str, str]:
    """Validate the values now and make path values absolute: a scheduled
    task starts in System32, not in the folder the user typed this in."""
    defs = read_param_defs(doc)
    apply_params(doc, defs, raw, cwd=os.getcwd())  # raises on bad names/values
    kinds = {d.name: d.type for d in defs}
    out = {}
    for name, value in raw.items():
        if kinds.get(name) in ("path_in", "path_out"):
            value = resolve_workflow_path(value, base_dir=os.getcwd())
        out[name] = value
    return out


def _live_rows() -> tuple[list[dict], str | None]:
    """The scheduler's own view; a failure only costs the live columns."""
    try:
        proc = sched._run_schtasks(sched.query_argv())
    except (OSError, subprocess.SubprocessError) as exc:
        return [], str(exc)
    if proc.returncode != 0:
        return [], (proc.stderr or proc.stdout or "").strip()
    return sched.parse_query_csv(proc.stdout or ""), None


def _add(args, ctx) -> int:
    sched.check_name(args.name)
    sched.ensure_windows()
    doc = read_workflow(args.workflow)
    if not store_for(ctx.state).is_approved(doc.sha256):
        raise CliError(
            ExitCode.REFUSED,
            "TD-CLI-008",
            "This workflow has not been approved, and scheduled runs always need approval.",
            f"Review it with `approve {args.workflow}` first.",
        )
    workflow = os.path.abspath(args.workflow)
    params = _absolute_params(doc, parse_cli_params(args.param))
    trigger = sched.parse_trigger(
        daily=args.daily,
        weekdays=args.weekdays,
        weekly=args.weekly,
        hourly=args.hourly,
        once=args.once,
    )
    folder = sched.schedules_dir(ctx.state)
    if (folder / f"{args.name}.json").exists() and not (args.force or args.print_only):
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-006",
            f"A schedule named '{args.name}' already exists.",
            "Use --force to replace it, or choose another name.",
        )
    logs = ensure(ctx.state, "logs")
    spec = sched.ScheduleSpec(
        name=args.name,
        workflow=workflow,
        workflow_sha256=doc.sha256,
        trigger=trigger,
        params=params,
        run_whether_logged_on=args.run_whether_logged_on,
        skip_missed=args.skip_missed,
        timeout_s=int(args.timeout),
        max_memory_mb=args.max_memory,
        state_dir=str(ctx.state),
        log_file=str(logs / f"{args.name}.jsonl"),
        xml_path=str(folder / f"{args.name}.xml"),
        created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    create = sched.create_argv(spec)
    print("command: " + subprocess.list2cmdline(sched.build_command(spec)))
    print("schtasks: " + subprocess.list2cmdline(create))
    if args.print_only:
        print(sched.build_task_xml(spec))
        return 0
    sched.save_spec(spec)
    proc = sched._run_schtasks(create)
    if proc.returncode != 0:
        for suffix in (".json", ".xml"):
            with contextlib.suppress(OSError):
                (folder / f"{args.name}{suffix}").unlink()
        raise sched.scheduler_error("/Create", proc)
    print(f"Scheduled '{args.name}' ({sched.TASK_FOLDER}\\{args.name}).")
    return 0


def _merge(defs: list[dict], live: list[dict]) -> list[dict]:
    by_name = {row["name"].lower(): row for row in live}
    merged = []
    for definition in defs:
        row = by_name.get(str(definition.get("name", "")).lower())
        merged.append({**definition, "live": row})
    return merged


def _list(args, ctx) -> int:
    sched.ensure_windows()
    live, problem = _live_rows()
    merged = _merge(sched.load_definitions(ctx.state), live)
    if args.format == "json":
        print_json({"schedules": merged, "scheduler_error": problem})
        return 0
    if problem:
        print(f"(could not query Windows: {problem})")
    if not merged:
        print("(no scheduled runs)")
    for item in merged:
        row = item["live"] or {}
        print(
            f"{item['name']:20} {sched.describe_trigger(item.get('trigger'))}  next: {row.get('next_run', '?')}  "
            f"status: {row.get('status', '?')}  last result: {row.get('last_result', '?')}"
        )
    return 0


def _show(args, ctx) -> int:
    sched.check_name(args.name)
    sched.ensure_windows()
    live, _problem = _live_rows()
    merged = _merge(
        [d for d in sched.load_definitions(ctx.state) if d.get("name") == args.name],
        live,
    )
    if not merged:
        raise CliError(
            ExitCode.INVALID, "TD-CLI-005", f"No scheduled run named '{args.name}'."
        )
    print_json(merged[0])
    return 0


def _remove(args, ctx) -> int:
    sched.check_name(args.name)
    sched.ensure_windows()
    proc = sched._run_schtasks(sched.delete_argv(args.name))
    if proc.returncode != 0:
        text = (proc.stderr or proc.stdout or "").strip()
        if "cannot find" in text.lower() or "does not exist" in text.lower():
            print(f"warning: the scheduler has no task '{args.name}' ({text})")
        else:
            raise sched.scheduler_error("/Delete", proc)
    folder = Path(ctx.state) / "schedules"
    for suffix in (".json", ".xml"):
        with contextlib.suppress(OSError):
            (folder / f"{args.name}{suffix}").unlink()
    print(f"Removed '{args.name}'.")
    return 0


def execute(args, ctx) -> int:
    handler = {"add": _add, "list": _list, "show": _show, "remove": _remove}[
        args.schedule_cmd
    ]
    return handler(args, ctx)
