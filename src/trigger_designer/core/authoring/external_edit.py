"""What changed in a ``.tds`` file that an external tool rewrote (Qt-free).

AI plan, phase 4. The editor keeps a workflow open. When an agent rewrites the
file on disk, the editor calls :func:`analyse_external_edit` with the bytes it
last read (``base``) and the bytes now on disk (``new``), and gets an
:class:`ExternalChange` with one of four statuses:

* ``unchanged``: the same bytes. Nothing else is parsed or computed.
* ``metadata_only``: other bytes, but the same nodes and connections (layout
  of the file, groups, comments or workflow metadata differ).
* ``changed``: nodes or connections differ. ``touched`` marks the nodes to
  highlight, ``removed`` lists the nodes that are gone, ``lines`` is the review
  list and ``summary`` the banner sentence.
* ``invalid``: the file must not be loaded in place. ``problems`` says why: it
  cannot be read yet, it is not a valid workflow, a newer program saved it, or
  a node changed its type (the editor reloads in place only when every node
  keeps its type).

A damaged file does not raise: the agent may still be writing it.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from trigger_designer.core.authoring.blank import new_workflow
from trigger_designer.core.authoring.diff import diff_workflows, render_lines
from trigger_designer.core.authoring.model import nodes_of
from trigger_designer.core.constants import WORKFLOW_SCHEMA_VERSION
from trigger_designer.core.headless.exit_codes import CliError
from trigger_designer.core.headless.op_catalog import node_op
from trigger_designer.core.headless.workflow_file import (
    WorkflowDoc,
    parse_workflow_bytes,
    static_validate,
)

STATUS_UNCHANGED = "unchanged"
STATUS_METADATA_ONLY = "metadata_only"
STATUS_CHANGED = "changed"
STATUS_INVALID = "invalid"

#: How a node in ``ExternalChange.touched`` changed. When several apply, the
#: first in this order wins: a node that was added and gained a connection is
#: "added", a changed node that lost a connection is "changed".
TOUCH_ADDED = "added"
TOUCH_CHANGED = "changed"
TOUCH_CONNECTED = "connected"
TOUCH_PRECEDENCE = (TOUCH_ADDED, TOUCH_CHANGED, TOUCH_CONNECTED)

#: The parts of the change summary, in banner order: the key in the diff's
#: ``summary``, the singular noun, the plural noun and the verb.
SUMMARY_PARTS = (
    ("nodes_added", "node", "nodes", "added"),
    ("nodes_changed", "node", "nodes", "changed"),
    ("nodes_removed", "node", "nodes", "removed"),
    ("connections_added", "connection", "connections", "added"),
    ("connections_removed", "connection", "connections", "removed"),
    ("comments_added", "comment", "comments", "added"),
    ("comments_changed", "comment", "comments", "changed"),
    ("comments_removed", "comment", "comments", "removed"),
)

_BANNER = "The file was changed outside Trigger Designer"
SUMMARY_CHANGED = "Changed outside Trigger Designer: {details}"
SUMMARY_METADATA_ONLY = _BANNER + " (no node changes)"
SUMMARY_UNREADABLE = _BANNER + " but cannot be read yet: {problem}"
SUMMARY_NOT_VALID = _BANNER + " but is not a valid workflow: {problem}"
SUMMARY_NOT_IN_PLACE = _BANNER + " but cannot be reloaded in place: {problem}"

PROBLEM_EMPTY = "{name} is empty"
PROBLEM_NEWER = (
    "{name} was saved by a newer Trigger Designer (schema {found}); "
    "this program reads up to schema {known}"
)
PROBLEM_UNEXPECTED = "{name} could not be checked ({error})"
PROBLEM_TYPE_CHANGED = (
    "A node changed its type ({title}: {old} -> {new}); "
    "close and reopen the file to load it."
)
#: Used in messages when the caller gave no path, and for a node with no type.
UNNAMED_FILE = "the file"
NO_TYPE = "none"


@dataclass(frozen=True)
class ExternalChange:
    status: str  # "unchanged" | "metadata_only" | "changed" | "invalid"
    sha256: str  # sha256 hex of the NEW bytes
    data: dict | None  # the parsed new workflow (None when unchanged or invalid)
    diff: dict | None  # diff_workflows(base, new) (None when unchanged or invalid)
    touched: dict[int, str]  # node id -> "added" | "changed" | "connected"
    removed: tuple[dict, ...]  # {"id", "title", "op", "label"?} of the nodes gone
    summary: str  # one sentence for a banner, "" when unchanged
    lines: tuple[str, ...]  # render_lines(diff) for a review list, () when nothing
    problems: tuple[str, ...]  # why status == "invalid", else ()


def analyse_external_edit(base: bytes, new: bytes, path: str = "") -> ExternalChange:
    """Compare the bytes the editor last read with the file now on disk.

    ``path`` only names the file in the messages.
    """
    digest = hashlib.sha256(new).hexdigest()
    if digest == hashlib.sha256(base).hexdigest():
        return ExternalChange(
            status=STATUS_UNCHANGED,
            sha256=digest,
            data=None,
            diff=None,
            touched={},
            removed=(),
            summary="",
            lines=(),
            problems=(),
        )
    file_name = os.path.basename(path)
    try:
        return _compare(base, new, digest, file_name)
    except Exception as exc:  # noqa: BLE001 - a half-written file must never crash the editor
        problem = PROBLEM_UNEXPECTED.format(
            name=file_name or UNNAMED_FILE, error=_error_text(exc)
        )
        return _unreadable(digest, problem)


def _compare(base: bytes, new: bytes, digest: str, file_name: str) -> ExternalChange:
    name = file_name or UNNAMED_FILE
    if not new.strip():
        return _unreadable(digest, PROBLEM_EMPTY.format(name=name))
    try:
        doc = parse_workflow_bytes(new, file_name)
    except CliError as exc:
        return _unreadable(digest, _reason(exc.message))
    if doc.schema_version > WORKFLOW_SCHEMA_VERSION:
        problem = PROBLEM_NEWER.format(
            name=name, found=doc.schema_version, known=WORKFLOW_SCHEMA_VERSION
        )
        return _unreadable(digest, problem)

    before = _base_workflow(base, file_name)
    known = {(f.td_code, f.message) for f in static_validate(before)}
    errors = [
        _one_line(f.message)
        for f in static_validate(doc)
        if f.level == "error" and (f.td_code, f.message) not in known
    ]
    if errors:
        return _not_valid(digest, errors)

    old_nodes = {node.get("id"): node for node in nodes_of(before.data)}
    new_nodes = {node.get("id"): node for node in nodes_of(doc.data)}
    retyped = _retyped(old_nodes, new_nodes)
    if retyped:
        return _not_in_place(digest, retyped)

    diff = diff_workflows(before.data, doc.data)
    if diff["empty"]:
        return ExternalChange(
            status=STATUS_METADATA_ONLY,
            sha256=digest,
            data=doc.data,
            diff=diff,
            touched={},
            removed=(),
            summary=SUMMARY_METADATA_ONLY,
            lines=(),
            problems=(),
        )
    return ExternalChange(
        status=STATUS_CHANGED,
        sha256=digest,
        data=doc.data,
        diff=diff,
        touched=_touched(diff, set(new_nodes)),
        removed=tuple(dict(node) for node in diff["nodes"]["removed"]),
        summary=SUMMARY_CHANGED.format(details=_details(diff["summary"])),
        lines=tuple(render_lines(diff)),
        problems=(),
    )


def _base_workflow(base: bytes, file_name: str) -> WorkflowDoc:
    """The base as a workflow. A base that cannot be read counts as an empty
    workflow, so every node of the new file reads as added."""
    try:
        return parse_workflow_bytes(base, file_name)
    except Exception:  # noqa: BLE001 - an unreadable base counts as an empty one
        return parse_workflow_bytes(json.dumps(new_workflow()).encode("utf-8"))


def _retyped(old: dict, new: dict) -> list[str]:
    """Nodes that keep their id but change their type. The editor cannot reload
    those in place."""
    problems: list[str] = []
    for node_id, node in new.items():
        if node_id not in old:
            continue
        before, now = node_op(old[node_id]), node_op(node)
        if before != now:
            title = node.get("title") or old[node_id].get("title") or node_id
            problem = PROBLEM_TYPE_CHANGED.format(
                title=title, old=before or NO_TYPE, new=now or NO_TYPE
            )
            problems.append(_one_line(problem))
    return problems


def _touched(diff: dict, new_ids: set[Any]) -> dict[int, str]:
    """Node id -> how it changed, for the nodes still in the file. A removed
    node is never touched."""
    marks: list[tuple[Any, str]] = [
        (node["id"], TOUCH_ADDED) for node in diff["nodes"]["added"]
    ]
    marks += [(node["id"], TOUCH_CHANGED) for node in diff["nodes"]["changed"]]
    for edge in (*diff["connections"]["added"], *diff["connections"]["removed"]):
        marks.append((edge["from"]["node"], TOUCH_CONNECTED))
        marks.append((edge["to"]["node"], TOUCH_CONNECTED))
    touched: dict[int, str] = {}
    for node_id, kind in marks:
        if node_id not in new_ids:
            continue
        held = touched.get(node_id)
        if held is None or TOUCH_PRECEDENCE.index(kind) < TOUCH_PRECEDENCE.index(held):
            touched[node_id] = kind
    return touched


def _details(counts: dict) -> str:
    """'2 nodes added, 1 connection removed'. A zero count is left out."""
    parts = []
    for key, singular, plural, verb in SUMMARY_PARTS:
        count = counts.get(key, 0)
        if count:
            parts.append(f"{count} {singular if count == 1 else plural} {verb}")
    return ", ".join(parts)


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def _reason(message: str) -> str:
    """A message on one line, without the full stop it ends with."""
    return _one_line(message).rstrip(".")


def _error_text(exc: Exception) -> str:
    detail = _one_line(str(exc))
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


def _invalid(digest: str, problems: tuple[str, ...], summary: str) -> ExternalChange:
    return ExternalChange(
        status=STATUS_INVALID,
        sha256=digest,
        data=None,
        diff=None,
        touched={},
        removed=(),
        summary=summary,
        lines=(),
        problems=problems,
    )


def _unreadable(digest: str, problem: str) -> ExternalChange:
    return _invalid(digest, (problem,), SUMMARY_UNREADABLE.format(problem=problem))


def _not_valid(digest: str, problems: list[str]) -> ExternalChange:
    summary = SUMMARY_NOT_VALID.format(problem=problems[0])
    return _invalid(digest, tuple(problems), summary)


def _not_in_place(digest: str, problems: list[str]) -> ExternalChange:
    summary = SUMMARY_NOT_IN_PLACE.format(problem=problems[0])
    return _invalid(digest, tuple(problems), summary)
