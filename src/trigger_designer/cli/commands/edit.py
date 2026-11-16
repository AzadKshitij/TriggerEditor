"""``edit``: change a workflow without the editor window (AI plan, phase 2).

Every subcommand is a dry run unless ``--apply`` is given: it prints (or, with
``--json``, returns) the diff and writes nothing. ``--apply`` needs
``"edit": true`` in the data owner's agent policy, refuses when the file changed
since it was read, keeps the first ``.bak`` of the file, and writes atomically.
The file's hash changes, so a workflow that was approved to run has to be
approved again.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from trigger_designer.cli.output import print_json
from trigger_designer.cli.render import Out
from trigger_designer.core.authoring import (
    Editor,
    apply_patch,
    diff_workflows,
    new_workflow,
    render_lines,
)
from trigger_designer.core.authoring.model import BAD_EDIT, STALE_FILE, fail
from trigger_designer.core.authoring.patch import apply_one
from trigger_designer.core.authoring.validate import Raw
from trigger_designer.core.constants import WORKFLOW_SCHEMA_VERSION
from trigger_designer.core.headless.access_policy import load_policy, require_edit
from trigger_designer.core.headless.params import (
    dump_workflow,
    write_workflow_with_backup,
)
from trigger_designer.core.headless.workflow_file import (
    WorkflowDoc,
    read_workflow,
    static_validate,
)


def _json_value(text: str, what: str) -> Any:
    """JSON from the command line, or ``@file`` / ``-`` (standard input)."""
    try:
        if text == "-":
            text = sys.stdin.read()
        elif text.startswith("@"):
            text = Path(text[1:]).read_text(encoding="utf-8-sig")
        return json.loads(text)
    except OSError as exc:
        raise fail(BAD_EDIT, f"Cannot read {what}: {exc.strerror or exc}.") from None
    except ValueError as exc:
        raise fail(
            BAD_EDIT,
            f"{what} is not valid JSON ({exc}).",
            "On Windows put the JSON in a file and pass @file.json.",
        ) from None


def _settings(args) -> dict:
    out: dict = {}
    if getattr(args, "settings", None):
        value = _json_value(args.settings, "--settings")
        if not isinstance(value, dict):
            raise fail(BAD_EDIT, "--settings must be a JSON object.")
        out.update(value)
    for item in getattr(args, "set", None) or []:
        key, sep, raw = item.partition("=")
        if not sep or not key.strip():
            raise fail(BAD_EDIT, f"--set expects NAME=VALUE, not {item!r}.")
        out[key.strip()] = Raw(raw)
    return out


def _operations(args) -> list[tuple[str, dict]]:
    """The one edit (or the list of edits) the subcommand stands for."""
    cmd = args.edit_cmd
    if cmd == "add-node":
        return [
            (
                "add_node",
                {
                    "type": args.type,
                    "settings": _settings(args) or None,
                    "title": args.title,
                    "x": args.x,
                    "y": args.y,
                    "after": args.after,
                },
            )
        ]
    if cmd == "remove-node":
        return [("remove_node", {"node": args.node})]
    if cmd in ("connect", "disconnect"):
        return [
            (
                cmd,
                {
                    "from": args.source,
                    "output": args.output,
                    "to": args.target,
                    "input": args.input,
                },
            )
        ]
    if cmd == "set":
        return [("set", {"node": args.node, "settings": _settings(args)})]
    if cmd == "label":
        visible = True if args.show else False if args.hide else None
        return [("label", {"node": args.node, "text": args.text, "visible": visible})]
    if cmd == "layout":
        return [("layout", {})]
    raise KeyError(cmd)  # pragma: no cover - argparse rejects it first


def _check_editable(doc: WorkflowDoc) -> None:
    if doc.schema_version > WORKFLOW_SCHEMA_VERSION:
        raise fail(
            BAD_EDIT,
            f"{os.path.basename(doc.path)} was saved by a newer Trigger Designer "
            f"(schema {doc.schema_version}; this program edits up to "
            f"{WORKFLOW_SCHEMA_VERSION}).",
            "Update this program.",
        )


def _new_errors(before: WorkflowDoc, after: WorkflowDoc) -> list:
    known = {(f.td_code, f.message) for f in static_validate(before)}
    return [
        f
        for f in static_validate(after)
        if f.level == "error" and (f.td_code, f.message) not in known
    ]


def _stale(doc: WorkflowDoc) -> bool:
    try:
        return hashlib.sha256(Path(doc.path).read_bytes()).hexdigest() != doc.sha256
    except OSError:
        return True


def run_edit(args, operations: Any, *, patch: bool) -> dict:
    """Shared body: read, check, edit a copy, diff, and write only on --apply."""
    doc = read_workflow(args.workflow)
    expect = getattr(args, "expect_sha", None)
    if expect and expect.lower() != doc.sha256:
        raise fail(
            STALE_FILE,
            "The workflow is not the version you read (its sha256 differs).",
            "Read it again (`info` shows its sha256) and redo the edit.",
        )
    _check_editable(doc)
    policy = load_policy(args.workflow, getattr(args, "policy", None))
    if args.apply:
        require_edit(policy)
    editor = Editor(doc.data, base_dir=doc.base_dir, extra_paths=policy.paths)
    if patch:
        results = apply_patch(editor, operations)
    else:
        results = [
            {"edit": 1, "action": name, **apply_one(editor, name, fields)}
            for name, fields in operations
        ]
    after = dataclasses.replace(doc, data=editor.data)
    broken = _new_errors(doc, after)
    if broken:
        raise fail(
            BAD_EDIT, "The edit would leave the workflow invalid: " + broken[0].message
        )
    result = diff_workflows(doc.data, editor.data)
    new_bytes = dump_workflow(editor.data)
    applied, backup = False, None
    if args.apply and not result["empty"]:
        if _stale(doc):
            raise fail(
                STALE_FILE,
                "The workflow changed on disk while this edit was being prepared.",
                "Nothing was written. Read it again and redo the edit.",
            )
        backup = write_workflow_with_backup(doc.path, editor.data)
        applied = True
    return {
        "workflow": os.path.abspath(doc.path),
        "dry_run": not args.apply,
        "applied": applied,
        "changed": not result["empty"],
        "sha256_before": doc.sha256,
        "sha256_after": hashlib.sha256(new_bytes).hexdigest()
        if not result["empty"]
        else doc.sha256,
        "backup": backup,
        "results": results,
        "diff": result,
    }


def render_text(envelope: dict) -> None:
    out = Out()
    state = (
        "applied"
        if envelope["applied"]
        else "dry run, nothing written (add --apply to write)"
        if envelope["dry_run"]
        else "no changes"
    )
    out.heading(f"{os.path.basename(envelope['workflow'])}: {state}")
    for line in render_lines(envelope["diff"]):
        out.line(line)
    for item in envelope["results"]:
        if item["action"] == "add_node":
            out.line(f"new node id: {item['id']}  ({item['title']})")
    if envelope["backup"]:
        out.note(f"backup: {envelope['backup']}")


def run_new(args) -> dict:
    """Create an empty workflow. Never replaces a file that exists."""
    path = Path(args.workflow)
    if path.suffix.lower() != ".tds":
        raise fail(
            BAD_EDIT,
            f"A workflow file ends in .tds, not '{path.suffix}'.",
            "Name it like sales.tds so Trigger Designer can open it.",
        )
    if path.exists():
        raise fail(
            BAD_EDIT,
            f"{path.name} already exists; `new` never replaces a file.",
            "Edit it with the other `edit` commands, or choose another name.",
        )
    if not path.resolve().parent.is_dir():
        raise fail(
            BAD_EDIT,
            f"The folder {path.resolve().parent} does not exist.",
            "Create the folder first.",
        )
    policy = load_policy(args.workflow, getattr(args, "policy", None))
    if args.apply:
        require_edit(policy)
    data = new_workflow()
    payload = dump_workflow(data)
    created = False
    if args.apply:
        try:
            with open(path, "xb") as handle:
                handle.write(payload)
        except FileExistsError:
            raise fail(
                BAD_EDIT, f"{path.name} was created by someone else just now."
            ) from None
        created = True
    return {
        "workflow": os.path.abspath(path),
        "dry_run": not args.apply,
        "applied": created,
        "created": created,
        "changed": True,
        "sha256_before": None,
        "sha256_after": hashlib.sha256(payload).hexdigest(),
        "workflow_uuid": data["workflow_metadata"]["workflow_uuid"],
        "backup": None,
        "results": [],
        "diff": diff_workflows(data, data),
    }


def execute(args, ctx) -> int:
    if args.edit_cmd == "new":
        envelope = run_new(args)
        if args.format == "json":
            print_json(envelope)
        else:
            out = Out()
            name = os.path.basename(envelope["workflow"])
            if envelope["created"]:
                out.heading(f"{name}: created (empty workflow)")
            else:
                out.heading(f"{name}: dry run, nothing written (add --apply to create)")
        return 0
    if args.edit_cmd == "patch":
        operations = _json_value(args.edits, "the edit list")
        envelope = run_edit(args, operations, patch=True)
    else:
        envelope = run_edit(args, _operations(args), patch=False)
    if args.format == "json":
        print_json(envelope)
    else:
        render_text(envelope)
    return 0
