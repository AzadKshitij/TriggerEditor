"""``params list|add|remove``: run-time parameters stored in the workflow."""

from __future__ import annotations

import copy

from trigger_designer.cli.output import print_json
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.op_catalog import node_op
from trigger_designer.core.headless.params import (
    NAME_RE,
    PARAM_TARGETS,
    find_node,
    read_param_defs,
    write_workflow_with_backup,
)
from trigger_designer.core.headless.workflow_file import read_workflow


def _list(args, doc) -> int:
    defs = read_param_defs(doc)
    if args.format == "json":
        print_json([d.to_dict() for d in defs])
        return 0
    if not defs:
        print("(no parameters)")
        return 0
    for d in defs:
        flag = " [required]" if d.required else ""
        default = f" default={d.default!r}" if d.default is not None else ""
        print(f"{d.name:20} {d.type:9} node {d.node_id}.{d.setting}{default}{flag}")
    return 0


def _add(args, doc) -> int:
    if not NAME_RE.match(args.name):
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-006",
            f"Parameter name '{args.name}' is not valid.",
            "Use lower case letters, digits and _, starting with a letter.",
        )
    existing = read_param_defs(doc)
    if any(d.name == args.name for d in existing):
        raise CliError(
            ExitCode.INVALID, "TD-CLI-006", f"Parameter '{args.name}' already exists."
        )
    node = find_node(doc, args.node)
    op = node_op(node) or ""
    rule = PARAM_TARGETS.get((op, args.setting))
    if rule is None:
        allowed = ", ".join(sorted(f"{o}.{s}" for o, s in PARAM_TARGETS))
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-007",
            f"{op}.{args.setting} cannot be a parameter.",
            f"Supported settings: {allowed}.",
        )
    if args.type and args.type != rule.kind:
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-007",
            f"{op}.{args.setting} is a '{rule.kind}' setting, not '{args.type}'.",
        )
    data = copy.deepcopy(doc.data)
    meta = data.setdefault("workflow_metadata", {})
    params = meta.setdefault("parameters", [])
    params.append(
        {
            "name": args.name,
            "label": args.label or args.name.replace("_", " ").capitalize(),
            "type": rule.kind,
            "node_id": node["id"],
            "setting": args.setting,
            "default": args.default,
            "required": bool(args.required),
        }
    )
    bak = write_workflow_with_backup(doc.path, data)
    print(
        f"Added parameter '{args.name}' -> node {node['id']}.{args.setting}"
        + (f" (backup: {bak})" if bak else "")
    )
    return 0


def _remove(args, doc) -> int:
    defs = read_param_defs(doc)
    if not any(d.name == args.name for d in defs):
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-005",
            f"No parameter named '{args.name}'. Known: "
            f"{', '.join(d.name for d in defs) or '(none)'}.",
        )
    data = copy.deepcopy(doc.data)
    meta = data["workflow_metadata"]
    meta["parameters"] = [p for p in meta["parameters"] if p.get("name") != args.name]
    bak = write_workflow_with_backup(doc.path, data)
    print(f"Removed parameter '{args.name}'" + (f" (backup: {bak})" if bak else ""))
    return 0


def execute(args, ctx) -> int:
    doc = read_workflow(args.workflow)
    handler = {"list": _list, "add": _add, "remove": _remove}[args.params_cmd]
    return handler(args, doc)
