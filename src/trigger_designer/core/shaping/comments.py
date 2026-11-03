"""Comment node logic: label rule and readers for saved/live comments (Qt-free).

A Comment never executes. Its text is ``settings["text"]``; the canvas label is
the first line cut to ``LABEL_MAX`` characters. The workpaper and the run log
read comments with ``comments_from_scene_dict`` / ``comments_from_nodes``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

COMMENT_OP = "report.comment"

#: Ops that never execute; the run log records them as "skipped".
NOT_EXECUTABLE_OPS = frozenset({COMMENT_OP})

DEFAULTS: dict[str, Any] = {"text": ""}

#: The floating canvas label is the first line of the note, cut to this length.
LABEL_MAX = 60

#: Generated code for a Comment: a no-op that the executor runs successfully.
CODE = "# Comment (not executed)\n"


@dataclass(frozen=True)
class CommentRecord:
    node_id: int
    text: str
    x: float
    y: float


def label_for(text: Any) -> str:
    """Canvas label for ``text``: first non-blank line, at most ``LABEL_MAX`` chars."""
    lines = str(text or "").strip().splitlines()
    return lines[0].strip()[:LABEL_MAX] if lines else ""


def _sorted(records: list[CommentRecord]) -> list[CommentRecord]:
    return sorted(records, key=lambda c: (c.y, c.x, c.node_id))  # reading order


def comments_from_scene_dict(scene: dict[str, Any]) -> list[CommentRecord]:
    """Comments in a ``TriggerScene.serialize()`` dict / loaded ``.tds`` (Qt-free)."""
    found = []
    for node in scene.get("nodes", []):
        if node.get("op") != COMMENT_OP:
            continue
        settings = (node.get("content") or {}).get("settings") or {}
        text = str(settings.get("text", "")).strip()
        if text:
            found.append(
                CommentRecord(
                    int(node["id"]),
                    text,
                    float(node.get("pos_x", 0.0)),
                    float(node.get("pos_y", 0.0)),
                )
            )
    return _sorted(found)


def comments_from_nodes(nodes: Iterable[Any]) -> list[CommentRecord]:
    """Same as ``comments_from_scene_dict`` for live nodes (duck-typed, no Qt import)."""
    found = []
    for node in nodes:
        try:
            op = f"{node.node_type.value}.{node.node_code.name.lower()}"
        except AttributeError:
            continue
        if op != COMMENT_OP:
            continue
        text = str(node.content.settings.get("text", "") or "").strip()
        if not text:
            continue
        pos = node.grNode.pos()
        found.append(CommentRecord(int(node.id), text, float(pos.x()), float(pos.y())))
    return _sorted(found)
