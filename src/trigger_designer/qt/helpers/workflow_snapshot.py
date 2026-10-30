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


def collect_workflow(node: Any) -> list[dict]:
    steps: list[dict] = []
    for number, parent in enumerate(ancestors(node), start=1):
        steps.append(
            {
                "step": number,
                "node_id": int(getattr(parent, "id", 0) or 0),
                "title": str(getattr(parent, "node_title", "") or ""),
                "label": str(getattr(parent, "label_text", "") or "").strip() or None,
                "op": _op_of(parent),
                "kind": "node",
                "settings": describe_settings(parent),
                "inputs": [
                    str(getattr(up, "node_title", "") or "") for up in _upstream(parent)
                ],
                "comment": None,
            }
        )
    scene = getattr(node, "scene", None)
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
