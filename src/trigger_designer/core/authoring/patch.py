"""Apply a list of edits as one all-or-nothing batch (Qt-free).

An edit list is JSON, so a tool can build a whole sub-graph in one call. A node
created in the batch can be named with ``ref`` and used by the edits after it,
because its id is not known in advance::

    [
      {"op": "add_node", "type": "preparation.filter", "ref": "f",
       "settings": {"column": "Amount", "operation": ">", "value": "10000"}},
      {"op": "connect", "from": "Input", "output": 0, "to": "f", "input": 0}
    ]

Operations: ``add_node``, ``remove_node``, ``connect``, ``disconnect``, ``set``,
``label``, ``layout``. Fields are closed: an unknown field is an error, not
ignored. The first failing edit stops the batch; nothing is kept.
"""

from __future__ import annotations

from typing import Any

from trigger_designer.core.authoring.edits import Editor
from trigger_designer.core.authoring.model import BAD_EDIT, fail
from trigger_designer.core.headless.exit_codes import CliError

MAX_OPERATIONS = 500

#: operation -> (required fields, optional fields)
OPERATIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "add_node": (("type",), ("ref", "settings", "title", "x", "y", "after")),
    "remove_node": (("node",), ()),
    "connect": (("from", "to"), ("output", "input")),
    "disconnect": (("from", "to"), ("output", "input")),
    "set": (("node", "settings"), ()),
    "label": (("node", "text"), ("visible",)),
    "layout": ((), ()),
}


def _check_shape(index: int, item: Any) -> tuple[str, dict]:
    where = f"edit {index + 1}"
    if not isinstance(item, dict):
        raise fail(
            BAD_EDIT, f'{where} must be an object such as {{"op": "connect", ...}}.'
        )
    name = item.get("op")
    if name not in OPERATIONS:
        raise fail(
            BAD_EDIT,
            f"{where}: unknown operation {name!r}.",
            "Operations: " + ", ".join(OPERATIONS) + ".",
        )
    required, optional = OPERATIONS[name]
    fields = {k: v for k, v in item.items() if k != "op"}
    missing = [k for k in required if k not in fields]
    if missing:
        raise fail(BAD_EDIT, f"{where} ({name}) needs: {', '.join(missing)}.")
    unknown = [k for k in fields if k not in (*required, *optional)]
    if unknown:
        raise fail(
            BAD_EDIT,
            f"{where} ({name}) has unknown field(s): {', '.join(unknown)}.",
            "Allowed: " + ", ".join((*required, *optional)) + ".",
        )
    return name, fields


def apply_one(editor: Editor, name: str, f: dict) -> dict:
    if name == "add_node":
        return editor.add_node(
            f["type"],
            settings=f.get("settings"),
            title=f.get("title"),
            x=f.get("x"),
            y=f.get("y"),
            after=f.get("after"),
            ref=f.get("ref"),
        )
    if name == "remove_node":
        return editor.remove_node(f["node"])
    if name == "connect":
        return editor.connect(f["from"], f.get("output", 0), f["to"], f.get("input", 0))
    if name == "disconnect":
        return editor.disconnect(
            f["from"], f.get("output", 0), f["to"], f.get("input", 0)
        )
    if name == "set":
        return editor.set_settings(f["node"], f["settings"])
    if name == "label":
        return editor.set_label(f["node"], f["text"], f.get("visible"))
    return editor.auto_layout()


def apply_patch(editor: Editor, operations: Any) -> list[dict]:
    """Run ``operations`` on ``editor``. One result per edit; any failure is
    re-raised naming the edit, and the caller discards the editor."""
    if isinstance(operations, dict) and "operations" in operations:
        operations = operations["operations"]
    if not isinstance(operations, list):
        raise fail(BAD_EDIT, "The edit list must be a JSON list of edits.")
    if not operations:
        raise fail(BAD_EDIT, "The edit list is empty.")
    if len(operations) > MAX_OPERATIONS:
        raise fail(BAD_EDIT, f"At most {MAX_OPERATIONS} edits at a time.")
    results: list[dict] = []
    for index, item in enumerate(operations):
        name, fields = _check_shape(index, item)
        try:
            outcome = apply_one(editor, name, fields)
        except CliError as exc:
            raise CliError(
                exc.code,
                exc.td_code,
                f"edit {index + 1} ({name}): {exc.message}",
                exc.hint,
            ) from None
        results.append({"edit": index + 1, "action": name, **outcome})
    return results
