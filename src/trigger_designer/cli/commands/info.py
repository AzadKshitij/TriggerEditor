"""``info``: what a workflow reads, writes and needs. Starts instantly."""

from __future__ import annotations

import os

from trigger_designer.cli.output import print_json
from trigger_designer.core.constants import VERSION
from trigger_designer.core.headless.paths import resolve_workflow_path
from trigger_designer.core.headless.workflow_file import (
    file_nodes,
    op_counts,
    read_workflow,
)


def _file_row(fn, base_dir: str) -> dict:
    row = {"node_id": fn.node_id, "title": fn.title, "saved_path": fn.raw_path}
    try:
        resolved = resolve_workflow_path(fn.raw_path, base_dir=base_dir)
    except Exception as exc:  # noqa: BLE001
        row.update(resolved=None, exists=False, size_bytes=None, problem=str(exc))
        return row
    exists = os.path.exists(resolved)
    row.update(
        resolved=resolved,
        exists=exists,
        size_bytes=os.path.getsize(resolved)
        if exists and os.path.isfile(resolved)
        else None,
    )
    return row


def collect(doc, ctx) -> dict:
    from trigger_designer.core.headless.approvals import approval_status

    base = doc.base_dir
    nodes = file_nodes(doc)
    meta = doc.metadata
    return {
        "path": os.path.abspath(doc.path),
        "sha256": doc.sha256,
        "size_bytes": len(doc.raw),
        "encoding": doc.encoding,
        "schema_version": doc.schema_version,
        "app_version": meta.get("app_version"),
        "saved_at": meta.get("saved_at"),
        "this_app_version": VERSION,
        "node_count": len(doc.nodes),
        "ops": op_counts(doc),
        "reads": [_file_row(n, base) for n in nodes if n.kind == "input"],
        "writes": [_file_row(n, base) for n in nodes if n.kind == "output"],
        "parameters": meta.get("parameters") or [],
        "approval": approval_status(ctx.state, doc),
    }


def render_text(info: dict) -> str:
    out = [
        f"workflow:   {info['path']}",
        f"sha256:     {info['sha256']}",
        f"size:       {info['size_bytes']} bytes, encoding {info['encoding']}",
        "schema:     {} (saved by app {}, {})".format(
            info["schema_version"], info["app_version"], info["saved_at"]
        ),
        f"approved:   {info['approval']['text']}",
        f"nodes:      {info['node_count']}",
    ]
    out += [f"  {op}: {n}" for op, n in info["ops"].items()]
    for label, rows in (("reads", info["reads"]), ("writes", info["writes"])):
        out.append(f"{label}:")
        if not rows:
            out.append("  (none)")
        for row in rows:
            if label == "writes":
                state = "exists, will be replaced" if row["exists"] else "new"
            else:
                state = "exists" if row["exists"] else "MISSING"
            out.append(f"  [{row['node_id']}] {row['saved_path']}")
            out.append(f"       -> {row['resolved']} ({state})")
    out.append("parameters:")
    params = info["parameters"]
    if not params:
        out.append("  (none)")
    for param in params:
        out.append(
            f"  {param.get('name')} ({param.get('type')}) -> node "
            f"{param.get('node_id')}.{param.get('setting')}"
            + (" [required]" if param.get("required") else "")
        )
    return "\n".join(out)


def execute(args, ctx) -> int:
    doc = read_workflow(args.workflow)
    info = collect(doc, ctx)
    if args.format == "json":
        print_json(info)
    else:
        print(render_text(info))
    return 0
