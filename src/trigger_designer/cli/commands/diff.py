"""``diff``: what differs between two workflows, node by node (no data read)."""

from __future__ import annotations

import os

from trigger_designer.cli.output import print_json
from trigger_designer.cli.render import Out
from trigger_designer.core.authoring import diff_workflows, render_lines
from trigger_designer.core.headless.workflow_file import read_workflow


def execute(args, ctx) -> int:
    old, new = read_workflow(args.old), read_workflow(args.new)
    result = diff_workflows(old.data, new.data)
    envelope = {
        "old": {"path": os.path.abspath(old.path), "sha256": old.sha256},
        "new": {"path": os.path.abspath(new.path), "sha256": new.sha256},
        **result,
    }
    if args.format == "json":
        print_json(envelope)
    else:
        out = Out()
        out.heading(f"{os.path.basename(old.path)} -> {os.path.basename(new.path)}")
        for line in render_lines(result):
            out.line(line)
    return 0
