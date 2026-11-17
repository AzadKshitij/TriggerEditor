"""Shared pieces of the authoring functions (Qt-free): errors, ids, lookups.

Everything here works on the plain ``dict`` of a ``.tds`` file, the same shape
``core/headless/workflow_file.py`` reads, so no editor window is needed.

Ids: the editor numbers objects with ``id(obj)`` (memory addresses saved into
the file). A new object here takes ``highest id in the file + 1``; ids are
unique inside one file, which is all the loader needs.
"""

from __future__ import annotations

import difflib
from collections.abc import Iterator
from typing import Any

from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.node_spec import SOCKETS
from trigger_designer.core.headless.op_catalog import node_op

#: TD-CLI codes raised by the authoring layer.
INVALID_SETTING = "TD-CLI-022"
INVALID_CONNECTION = "TD-CLI-023"
PATH_NOT_ALLOWED = "TD-CLI-024"
SQL_REJECTED = "TD-CLI-025"
STALE_FILE = "TD-CLI-026"
BAD_EDIT = "TD-CLI-027"
NODE_NOT_FOUND = "TD-CLI-020"


def fail(
    code: str,
    message: str,
    hint: str = "",
    exit_code: ExitCode = ExitCode.INVALID,
) -> CliError:
    """Build (not raise) a structured error: ``raise fail(...)``."""
    return CliError(exit_code, code, message, hint)


def nodes_of(data: dict) -> list[dict]:
    return [n for n in data.get("nodes", []) if isinstance(n, dict)]


def edges_of(data: dict) -> list[dict]:
    return [e for e in data.get("edges", []) if isinstance(e, dict)]


def _ints(values) -> Iterator[int]:
    for value in values:
        if isinstance(value, int) and not isinstance(value, bool):
            yield value


def iter_ids(data: dict) -> Iterator[int]:
    """Every id in the file: scene, nodes, their sockets, edges, groups, comments."""
    yield from _ints([data.get("id")])
    for node in nodes_of(data):
        yield from _ints([node.get("id")])
        for key in ("inputs", "outputs"):
            yield from _ints(
                s.get("id") for s in node.get(key) or [] if isinstance(s, dict)
            )
    for key in ("edges", "groups", "comments"):
        yield from _ints(
            item.get("id") for item in data.get(key) or [] if isinstance(item, dict)
        )


class IdPool:
    """Hands out ids no object in the file already has."""

    def __init__(self, data: dict) -> None:
        self._next = max(iter_ids(data), default=0) + 1

    def take(self) -> int:
        value = self._next
        self._next += 1
        return value


def op_of(node: dict) -> str:
    """The node's op id, or a refusal: legacy nodes cannot be edited here."""
    op = node_op(node)
    if op is None or op not in SOCKETS:
        title = node.get("title") or node.get("id")
        raise fail(
            BAD_EDIT,
            f"Node '{title}' has no known node type, so it cannot be edited here.",
            "Open the workflow in Trigger Designer and save it once, then retry.",
        )
    return op


def describe(node: dict) -> dict:
    out = {
        "id": node.get("id"),
        "title": node.get("title"),
        "op": node_op(node),
    }
    label = str(node.get("label_text") or "").strip()
    if label:
        out["label"] = label
    return out


def resolve_node(data: dict, ref: Any, aliases: dict[str, int] | None = None) -> dict:
    """A node by alias (``ref`` given earlier in the same patch), numeric id,
    unique title, or unique op id. Anything unclear is an error, never a guess."""
    nodes = nodes_of(data)
    text = str(ref).strip()
    if aliases and text in aliases:
        ref = aliases[text]
        text = str(ref)
    if isinstance(ref, int) and not isinstance(ref, bool) or text.lstrip("-").isdigit():
        wanted = int(text)
        for node in nodes:
            if node.get("id") == wanted:
                return node
    for field in ("label_text", "title", "op"):
        matches = [n for n in nodes if str(n.get(field) or "").strip() == text]
        if field == "op":
            matches = [n for n in nodes if node_op(n) == text]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            ids = ", ".join(str(n.get("id")) for n in matches)
            raise fail(
                NODE_NOT_FOUND,
                f"'{text}' matches {len(matches)} nodes (ids {ids}).",
                "Use the node's numeric id (see `info`).",
            )
    titles = [
        str(n.get(field))
        for n in nodes
        for field in ("label_text", "title")
        if n.get(field)
    ]
    near = difflib.get_close_matches(text, titles, n=3, cutoff=0.5)
    hint = "Use the node's numeric id (see `info`)."
    if near:
        hint = "Did you mean: " + ", ".join(near) + "? " + hint
    raise fail(NODE_NOT_FOUND, f"No node '{text}'.", hint)


def output_index(node: dict, which: Any) -> int:
    """An output socket index from an int, a digit string or its name."""
    op = op_of(node)
    names = SOCKETS[op].outputs
    count = len(node.get("outputs") or [])
    if isinstance(which, bool):
        which = str(which)
    if isinstance(which, int) or str(which).strip().isdigit():
        index = int(which)
        if 0 <= index < count:
            return index
    else:
        key = str(which).strip().lower()
        for i, name in enumerate(names):
            if name.lower() == key:
                return i
    shown = ", ".join(f"{i} ({n})" for i, n in enumerate(names)) or "none"
    raise fail(
        INVALID_CONNECTION,
        f"'{node.get('title')}' has no output '{which}'.",
        f"Its outputs: {shown}.",
    )


def input_index(node: dict, which: Any) -> int:
    count = len(node.get("inputs") or [])
    text = str(which).strip()
    if not isinstance(which, bool) and text.isdigit() and int(text) < count:
        return int(text)
    raise fail(
        INVALID_CONNECTION,
        f"'{node.get('title')}' has no input '{which}'.",
        f"It has {count} input(s), numbered from 0." if count else "It has no inputs.",
    )


def socket_owner(data: dict) -> dict[int, tuple[dict, str, int]]:
    """Socket id -> (node, 'inputs' | 'outputs', index)."""
    owner: dict[int, tuple[dict, str, int]] = {}
    for node in nodes_of(data):
        for key in ("inputs", "outputs"):
            for i, sock in enumerate(node.get(key) or []):
                if isinstance(sock, dict) and "id" in sock:
                    owner[sock["id"]] = (node, key, sock.get("index", i))
    return owner
