"""``approve``: pin a reviewed workflow so it may run unattended."""

from __future__ import annotations

import os
import sys

from trigger_designer.cli.output import print_json
from trigger_designer.core.headless.approvals import make_entry, store_for
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.params import read_param_defs
from trigger_designer.core.headless.paths import resolve_workflow_path
from trigger_designer.core.headless.workflow_file import (
    file_nodes,
    op_counts,
    read_workflow,
)


def _resolved(raw: str, base: str) -> str:
    try:
        return resolve_workflow_path(raw, base_dir=base)
    except CliError:
        return raw


def review_block(doc) -> tuple[str, list[str], list[str]]:
    nodes = file_nodes(doc)
    reads = [_resolved(n.raw_path, doc.base_dir) for n in nodes if n.kind == "input"]
    writes = [_resolved(n.raw_path, doc.base_dir) for n in nodes if n.kind == "output"]
    lines = [f"workflow: {os.path.abspath(doc.path)}", f"sha256:   {doc.sha256}"]
    lines.append("operations:")
    lines += [f"  {op}: {n}" for op, n in op_counts(doc).items()]
    lines.append("reads:")
    lines += [f"  {p}" for p in reads] or ["  (none)"]
    lines.append("writes:")
    lines += [f"  {p}" for p in writes] or ["  (none)"]
    try:
        defs = read_param_defs(doc)
    except CliError:
        defs = []
    lines.append("parameters:")
    lines += [f"  {d.name} -> node {d.node_id}.{d.setting}" for d in defs] or [
        "  (none)"
    ]
    return "\n".join(lines), reads, writes


def execute(args, ctx) -> int:
    store = store_for(ctx.state)
    if args.list:
        items = store.list()
        if args.format == "json":
            print_json(items)
        elif not items:
            print("(no approvals)")
        else:
            for item in items:
                print(
                    f"{item.get('sha256', '')[:12]}  {item.get('approved_at')}  "
                    f"{item.get('approved_by')}  {item.get('path')}"
                )
        return 0
    if args.revoke:
        removed = store.revoke(args.revoke)
        if not removed and os.path.exists(args.revoke):
            doc = read_workflow(args.revoke)
            removed = store.revoke(doc.sha256)
        print(f"Revoked {removed} approval(s).")
        return int(ExitCode.OK if removed else ExitCode.INVALID)
    if not args.workflow:
        sys.stderr.write("approve: give a WORKFLOW, or use --list / --revoke\n")
        return int(ExitCode.USAGE)
    doc = read_workflow(args.workflow)
    text, reads, writes = review_block(doc)
    print(text)
    if not args.yes:
        if not sys.stdin or not sys.stdin.isatty():
            sys.stderr.write(
                "approve: not a terminal; review the block above and pass --yes to approve.\n"
            )
            return int(ExitCode.USAGE)
        answer = input("Approve? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Not approved.")
            return int(ExitCode.REFUSED)
    store.add(make_entry(doc, reads, writes, args.note))
    print("Approved.")
    return 0
