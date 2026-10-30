"""Scene -> plain dicts for the workpaper (GUI thread only).

``collect_workflow(node)`` lists the nodes that produced the data of ``node``
(ancestors, dependencies first) and then every Comment node of the scene, as
plain dicts the Qt-free writer renders on the Workflow sheet. ``collect_sources``
lists the files those ancestors read. Neither touches file contents.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from trigger_designer.core.shaping.comments import comments_from_nodes
from trigger_designer.qt.helpers.audit_bridge import (
    _input_files,
    _op_of,
    snapshot_settings,
)

MAX_VALUE_CHARS = 600
_SKIP_VALUES = (None, "", [], {}, ())


def _label(key: str) -> str:
    return str(key).replace("_", " ").strip().capitalize()


def _value_text(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (dict, list, tuple)):
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError, ValueError:
            text = str(value)
    else:
        text = str(value)
    return text if len(text) <= MAX_VALUE_CHARS else text[: MAX_VALUE_CHARS - 3] + "..."


def describe_settings(node: Any) -> list[list[str]]:
    """``[[label, value], ...]`` of a node: its own hook, else its stored settings."""
    content = getattr(node, "content", None)
    hook = getattr(content, "describe_settings", None)
    if callable(hook):
        try:
            return [[str(a), _value_text(b)] for a, b in hook()]
        except Exception as exc:  # noqa: BLE001 - fall back to the generic listing
            logger.debug("workpaper: describe_settings failed: {}", exc)
    return [
        [_label(key), _value_text(value)]
        for key, value in snapshot_settings(content).items()
        if value not in _SKIP_VALUES
    ]


def _upstream(node: Any) -> list[Any]:
    found: list[Any] = []
    for index in range(len(getattr(node, "inputs", ()) or ())):
        try:
            found.extend(node.getInputs(index))
        except Exception:  # noqa: BLE001, S112 - unconnected or foreign socket
            continue
    return found


def ancestors(node: Any) -> list[Any]:
    """Nodes feeding ``node`` (not itself), dependencies before dependents."""
    order: list[Any] = []
    seen: set[int] = set()

    def visit(current: Any) -> None:
        for parent in _upstream(current):
            if id(parent) in seen:
                continue
            seen.add(id(parent))
            visit(parent)
            order.append(parent)

    seen.add(id(node))
    visit(node)
    return order


def _step(node: Any, number: int) -> dict:
    return {
        "step": number,
        "node_id": int(getattr(node, "id", 0) or 0),
        "title": str(getattr(node, "node_title", "") or ""),
        "label": str(getattr(node, "label_text", "") or "").strip() or None,
        "op": _op_of(node),
        "kind": "node",
        "settings": describe_settings(node),
        "inputs": [str(getattr(up, "node_title", "") or "") for up in _upstream(node)],
        "comment": None,
    }


def _comment_steps(scene: Any) -> list[dict]:
    steps = []
    for note in comments_from_nodes(list(getattr(scene, "nodes", ()) or ())):
        steps.append(
            {
                "step": None,
                "node_id": note.node_id,
                "title": "Comment",
                "label": None,
                "op": "report.comment",
                "kind": "comment",
                "settings": [],
                "inputs": [],
                "comment": note.text,
            }
        )
    return steps


def collect_workflow(node: Any) -> list[dict]:
    """Ancestors of ``node`` in run order, then every Comment node of the scene."""
    steps = [_step(parent, number) for number, parent in enumerate(ancestors(node), 1)]
    return steps + _comment_steps(getattr(node, "scene", None))


def collect_scene_workflow(
    scene: Any, order_ids: list[int] | None = None
) -> list[dict]:
    """Every executable node of ``scene`` (``order_ids`` first, as the run ordered
    them), then the Comment nodes. Used by the whole-run workpaper."""
    nodes = [
        n for n in getattr(scene, "nodes", ()) or () if _op_of(n) != "report.comment"
    ]
    rank = {node_id: i for i, node_id in enumerate(order_ids or [])}
    if order_ids:
        nodes = [n for n in nodes if getattr(n, "id", None) in rank]
        nodes.sort(key=lambda n: rank[n.id])
    steps = [_step(node, number) for number, node in enumerate(nodes, 1)]
    return steps + _comment_steps(scene)


def collect_sources(node: Any) -> list[dict]:
    """Files read by the ancestors of ``node`` (path, sheet), without hashing."""
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for parent in ancestors(node):
        for item in _input_files(parent, _op_of(parent)):
            key = (str(item.get("path") or ""), str(item.get("sheet") or ""))
            if key[0] and key not in seen:
                seen.add(key)
                found.append({"path": key[0], "sheet": item.get("sheet")})
    return found
