"""Canvas comments: the one Qt-free reader of a workflow's notes.

A canvas comment (sticky note) is not a node. It sits in the scene's top-level
``"comments"`` list, has no sockets and never runs; the JSON shape is documented
in ``nodeeditor.node_comment``. This module reads comments from a saved scene
dict (``.tds`` content) or from a live scene (duck-typed, so no Qt import). The
workpaper's Workflow sheet is built from these readers.

Workflows saved before canvas comments existed kept each note as a
``report.comment`` node. :func:`migrate_legacy_comment_nodes` turns those into
canvas comments. Every loader runs it before any node is built, so nothing
downstream ever sees the removed node.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from trigger_designer.core.headless.op_catalog import node_op

if TYPE_CHECKING:
    from trigger_designer.core.authoring.model import IdPool

#: The op id the removed Comment node was saved under. The migration matches it,
#: and the workpaper snapshot labels note steps with it. No reader keys on that
#: label: the Workflow sheet branches on ``kind``.
LEGACY_COMMENT_OP = "report.comment"

#: Serialization version written for a canvas comment. Must equal
#: ``nodeeditor.node_comment.COMMENT_SERIALIZATION_VERSION``. A unit test checks
#: it, because this module cannot import the Qt-side library module.
CANVAS_COMMENT_VERSION = 1

#: Size and stacking given to a migrated note. Must equal the library's
#: ``Comment.DEFAULT_WIDTH``, ``DEFAULT_HEIGHT`` and ``DEFAULT_Z_VALUE``.
MIGRATED_WIDTH = 220.0
MIGRATED_HEIGHT = 100.0
MIGRATED_Z = 1.0


@dataclass(frozen=True)
class CommentRecord:
    """One non-blank canvas comment: its id, its text and its scene position."""

    comment_id: int
    text: str
    x: float
    y: float


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except TypeError, ValueError:
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value) if not isinstance(value, bool) else default
    except TypeError, ValueError:
        return default


def _is_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _dicts(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _reading_order(records: list[CommentRecord]) -> list[CommentRecord]:
    return sorted(records, key=lambda c: (c.y, c.x, c.comment_id))


def comments_from_scene_dict(scene: dict[str, Any]) -> list[CommentRecord]:
    """The non-blank comments of a saved scene dict, in reading order."""
    found = []
    for item in _dicts(scene.get("comments")):
        text = str(item.get("text") or "").strip()
        if text:
            found.append(
                CommentRecord(
                    _int(item.get("id")),
                    text,
                    _float(item.get("x")),
                    _float(item.get("y")),
                )
            )
    return _reading_order(found)


def comments_from_scene(scene: Any) -> list[CommentRecord]:
    """The non-blank comments of a live scene, in reading order.

    Duck-typed: each entry of ``scene.comments`` needs ``text()``, ``pos()`` and
    ``id``, so this reader never imports Qt.
    """
    found = []
    for note in list(getattr(scene, "comments", None) or []):
        text = str(note.text() or "").strip()
        if text:
            pos = note.pos()
            found.append(
                CommentRecord(_int(note.id), text, float(pos.x()), float(pos.y()))
            )
    return _reading_order(found)


def migrate_legacy_comment_nodes(scene: dict[str, Any]) -> dict[str, Any]:
    """``scene`` with each legacy ``report.comment`` node moved to ``comments``.

    Pure: the input is never mutated. The result is a new top-level dict. Its
    ``nodes``, ``edges`` and ``comments`` lists are new whenever something
    changed, and every other value is shared with the input. A migrated note
    keeps its text and position and takes a fresh id that no object in the file
    has. A legacy note with no text is dropped, and so is any edge that touched
    its sockets. Idempotent: a scene without legacy nodes comes back unchanged.
    """
    # Imported here, not at module level: core.authoring's package init loads
    # the workflow loader, which imports this module, so a top-level import
    # would be circular.
    from trigger_designer.core.authoring.model import IdPool

    out = dict(scene)
    nodes = scene.get("nodes")
    if not isinstance(nodes, list):
        return out
    legacy = [
        index
        for index, node in enumerate(nodes)
        if isinstance(node, dict) and node_op(node) == LEGACY_COMMENT_OP
    ]
    if not legacy:
        return out

    pool = IdPool(scene)
    notes: list[dict[str, Any]] = []
    gone_sockets: set[int] = set()
    for index in legacy:
        node = nodes[index]
        for key in ("inputs", "outputs"):
            for socket in _dicts(node.get(key)):
                if _is_id(socket.get("id")):
                    gone_sockets.add(socket["id"])
        note = _legacy_note(node, pool)
        if note is not None:
            notes.append(note)

    legacy_set = set(legacy)
    out["nodes"] = [n for i, n in enumerate(nodes) if i not in legacy_set]
    if isinstance(scene.get("edges"), list):
        out["edges"] = [e for e in scene["edges"] if not _touches(e, gone_sockets)]
    existing = scene.get("comments")
    out["comments"] = [*(existing if isinstance(existing, list) else []), *notes]
    return out


def _legacy_note(node: dict[str, Any], pool: IdPool) -> dict[str, Any] | None:
    content = node.get("content")
    settings = content.get("settings") if isinstance(content, dict) else None
    text = settings.get("text") if isinstance(settings, dict) else None
    if not str(text or "").strip():
        return None
    return {
        "id": pool.take(),
        "type": "Comment",
        "version": CANVAS_COMMENT_VERSION,
        "text": str(text),
        "x": _float(node.get("pos_x")),
        "y": _float(node.get("pos_y")),
        "w": MIGRATED_WIDTH,
        "h": MIGRATED_HEIGHT,
        "z": MIGRATED_Z,
    }


def _touches(edge: Any, sockets: set[int]) -> bool:
    if not isinstance(edge, dict):
        return False
    return any(
        _is_id(edge.get(end)) and edge[end] in sockets for end in ("start", "end")
    )
