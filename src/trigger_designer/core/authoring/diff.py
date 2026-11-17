"""A node-level diff of two workflows (Qt-free): what a reviewer needs to see.

Nodes are matched by id. Reported: nodes added or removed, per-node changes
(title, label, position, each setting by dotted path) and connections added or
removed (as ``node.output -> node.input``). A workflow holds settings, never
data, so the diff never contains a cell value.
"""

from __future__ import annotations

from typing import Any

from trigger_designer.core.authoring.model import (
    describe,
    edges_of,
    nodes_of,
    socket_owner,
)

#: Moves smaller than this are not worth a line in a diff.
MOVE_EPSILON = 0.5
_SKIP = {"id", "inputs", "outputs", "content", "pos_x", "pos_y"}


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    """Dotted paths for nested objects; lists and scalars are compared whole."""
    if isinstance(value, dict) and value:
        out: dict[str, Any] = {}
        for key, item in value.items():
            out.update(_flatten(item, f"{prefix}.{key}" if prefix else str(key)))
        return out
    return {prefix: value}


def _node_changes(old: dict, new: dict) -> list[dict]:
    changes: list[dict] = []
    for key in sorted((set(old) | set(new)) - _SKIP):
        if old.get(key) != new.get(key):
            changes.append({"path": key, "from": old.get(key), "to": new.get(key)})
    ox, oy = old.get("pos_x", 0.0), old.get("pos_y", 0.0)
    nx, ny = new.get("pos_x", 0.0), new.get("pos_y", 0.0)
    if abs(ox - nx) > MOVE_EPSILON or abs(oy - ny) > MOVE_EPSILON:
        changes.append({"path": "position", "from": [ox, oy], "to": [nx, ny]})
    before = _flatten(old.get("content") or {})
    after = _flatten(new.get("content") or {})
    for path in sorted(set(before) | set(after)):
        if before.get(path, _MISSING) != after.get(path, _MISSING):
            changes.append(
                {
                    "path": f"content.{path}" if path else "content",
                    "from": before.get(path),
                    "to": after.get(path),
                }
            )
    return changes


_MISSING = object()


def _connections(data: dict) -> dict[tuple, dict]:
    owner = socket_owner(data)
    out: dict[tuple, dict] = {}
    for edge in edges_of(data):
        a, b = owner.get(edge.get("start")), owner.get(edge.get("end"))
        if a is None or b is None:
            continue
        key = (a[0].get("id"), a[2], b[0].get("id"), b[2])
        out[key] = {
            "from": {"node": key[0], "output": key[1]},
            "to": {"node": key[2], "input": key[3]},
        }
    return out


def diff_workflows(old: dict, new: dict) -> dict:
    """The differences from ``old`` to ``new`` as plain data."""
    old_nodes = {n.get("id"): n for n in nodes_of(old)}
    new_nodes = {n.get("id"): n for n in nodes_of(new)}
    added = [describe(new_nodes[i]) for i in new_nodes if i not in old_nodes]
    removed = [describe(old_nodes[i]) for i in old_nodes if i not in new_nodes]
    changed = []
    for node_id, node in new_nodes.items():
        if node_id not in old_nodes:
            continue
        changes = _node_changes(old_nodes[node_id], node)
        if changes:
            changed.append({**describe(node), "changes": changes})
    before, after = _connections(old), _connections(new)
    edges_added = [after[k] for k in after if k not in before]
    edges_removed = [before[k] for k in before if k not in after]
    empty = not (added or removed or changed or edges_added or edges_removed)
    return {
        "empty": empty,
        "summary": {
            "nodes_added": len(added),
            "nodes_removed": len(removed),
            "nodes_changed": len(changed),
            "connections_added": len(edges_added),
            "connections_removed": len(edges_removed),
        },
        "nodes": {"added": added, "removed": removed, "changed": changed},
        "connections": {"added": edges_added, "removed": edges_removed},
    }


def _short(value: Any, limit: int = 60) -> str:
    text = repr(value).replace("\n", "\\n")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _name(node: dict) -> str:
    """``Title "name"`` when the node has a name its author gave it."""
    label = node.get("label")
    return f'{node["title"]} "{label}"' if label else str(node["title"])


def render_lines(result: dict) -> list[str]:
    """The diff as plain lines for a terminal."""
    if result["empty"]:
        return ["(no differences)"]
    lines: list[str] = []
    for node in result["nodes"]["added"]:
        lines.append(f"+ node {node['id']} {_name(node)} ({node['op']})")
    for node in result["nodes"]["removed"]:
        lines.append(f"- node {node['id']} {_name(node)} ({node['op']})")
    for node in result["nodes"]["changed"]:
        lines.append(f"~ node {node['id']} {_name(node)} ({node['op']})")
        for change in node["changes"]:
            lines.append(
                f"    {change['path']}: {_short(change['from'])} -> {_short(change['to'])}"
            )
    for edge in result["connections"]["added"]:
        lines.append(f"+ {_edge(edge)}")
    for edge in result["connections"]["removed"]:
        lines.append(f"- {_edge(edge)}")
    return lines


def _edge(edge: dict) -> str:
    a, b = edge["from"], edge["to"]
    return f"connect {a['node']}.out{a['output']} -> {b['node']}.in{b['input']}"
