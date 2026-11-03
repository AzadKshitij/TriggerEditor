"""``paths``: saved file paths, resolved; optionally made relative."""

from __future__ import annotations

import copy
import os

from trigger_designer.cli.output import print_json
from trigger_designer.core.headless.exit_codes import CliError
from trigger_designer.core.headless.op_catalog import known_op, node_op
from trigger_designer.core.headless.params import (
    get_setting,
    set_setting,
    write_workflow_with_backup,
)
from trigger_designer.core.headless.paths import relativize, resolve_workflow_path
from trigger_designer.core.headless.workflow_file import (
    file_nodes,
    read_workflow,
    split_path_lines,
)


def _rows(doc) -> list[dict]:
    rows = []
    for fn in file_nodes(doc):
        row = {
            "node_id": fn.node_id,
            "kind": fn.kind,
            "title": fn.title,
            "saved": fn.raw_path,
            "resolved": None,
            "exists": False,
            "relative": None,
        }
        try:
            resolved = resolve_workflow_path(fn.raw_path, base_dir=doc.base_dir)
            row["resolved"] = resolved
            row["exists"] = os.path.exists(resolved)
            row["relative"] = relativize(resolved, doc.base_dir)
        except CliError as exc:
            row["problem"] = exc.message
        rows.append(row)
    return rows


def relativize_workflow(data: dict, base_dir: str) -> list[dict]:
    """Rewrite paths under ``base_dir`` to relative ones, in place.

    File Input keeps ``filePath`` and ``filePathRel`` consistent (both hold the
    relative path, which the editor resolves against the workflow folder).
    Returns one row per rewritten path.
    """
    changed = []
    for node in data.get("nodes", []):
        content = node.get("content") if isinstance(node, dict) else None
        if not isinstance(content, dict):
            continue
        op = node_op(node) or ""
        title = str(node.get("title") or "")
        if op == "input.file_input" or (not op and title == "File Input"):
            keys, is_input = ("filePath",), True
        else:
            info = known_op(op)
            keys = info.output_keys if info else ()
            if not keys and (
                op == "input.file_output" or (not op and title == "File Output")
            ):
                keys = ("filePath",)
            is_input = False
        info = known_op(op)
        for key in info.list_keys if info else ():
            raw_text = get_setting(content, key)
            lines = split_path_lines(raw_text)
            new_lines = []
            for raw in lines:
                new = raw
                try:
                    resolved = resolve_workflow_path(raw, base_dir=base_dir)
                    rel = relativize(resolved, base_dir)
                    new = rel if rel else raw
                except CliError:
                    pass
                if new != raw:
                    changed.append({"node_id": node.get("id"), "from": raw, "to": new})
                new_lines.append(new)
            if new_lines != lines:
                set_setting(content, key, "\n".join(new_lines))
        for key in keys:
            raw = get_setting(content, key)
            if not raw:
                continue
            try:
                resolved = resolve_workflow_path(raw, base_dir=base_dir)
            except CliError:
                continue
            rel = relativize(resolved, base_dir)
            if rel is None or rel == raw:
                continue
            set_setting(content, key, rel)
            if is_input:
                content["filePathRel"] = rel
            changed.append({"node_id": node.get("id"), "from": raw, "to": rel})
    return changed


def execute(args, ctx) -> int:
    doc = read_workflow(args.workflow)
    rows = _rows(doc)
    changes: list[dict] = []
    written = None
    if args.relativize:
        data = copy.deepcopy(doc.data)
        changes = relativize_workflow(data, doc.base_dir)
        if args.write and changes:
            written = write_workflow_with_backup(doc.path, data)
    if args.format == "json":
        print_json({"paths": rows, "relativize": changes, "backup": written})
        return 0
    for row in rows:
        state = "exists" if row["exists"] else "MISSING"
        print(f"[{row['node_id']}] {row['kind']:6} {row['saved']}")
        print(f"        -> {row['resolved']} ({state})")
    if args.relativize:
        print(f"relative paths ({'written' if args.write else 'preview'}):")
        if not changes:
            print("  (nothing to change)")
        for change in changes:
            print(f"  [{change['node_id']}] {change['from']} -> {change['to']}")
        if written:
            print(f"backup: {written}")
    return 0
