"""``validate``: static checks; ``--deep`` also loads the workflow like the editor."""

from __future__ import annotations

import os

from trigger_designer.cli.output import print_json
from trigger_designer.core.headless.events import route_stray_stdout
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.paths import resolve_workflow_path
from trigger_designer.core.headless.workflow_file import (
    Finding,
    file_nodes,
    read_workflow,
    static_validate,
)


def static_findings(doc, args) -> list[Finding]:
    findings = static_validate(doc)
    if getattr(args, "no_files", False):
        return findings
    for fn in file_nodes(doc):
        if fn.kind != "input" or not fn.raw_path:
            continue
        try:
            resolved = resolve_workflow_path(fn.raw_path, base_dir=doc.base_dir)
        except CliError as exc:
            findings.append(Finding("error", exc.td_code, exc.message, fn.node_id))
            continue
        if not os.path.exists(resolved) and "*" not in resolved:
            findings.append(
                Finding(
                    "warning",
                    "TD-IN-001",
                    f"input file not found: {resolved}",
                    fn.node_id,
                )
            )
    return findings


def execute(args, ctx) -> int:
    doc = read_workflow(args.workflow)
    if args.deep:
        from trigger_designer.core.headless.runner import deep_validate

        # The editor's node classes print to stdout; keep it for the report.
        with route_stray_stdout():
            findings = deep_validate(doc, args, ctx)
    else:
        findings = static_findings(doc, args)
    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warning"]
    failed = bool(errors) or (args.strict and bool(warnings))
    if args.format == "json":
        print_json({"ok": not failed, "findings": [f.to_dict() for f in findings]})
    else:
        for f in findings:
            print(f"{f.level.upper():7} {f.td_code}: {f.message}")
        print("OK" if not failed else "INVALID")
    return int(ExitCode.INVALID if failed else ExitCode.OK)
