"""Pure edits of a workflow's JSON (Qt-free): the authoring API.

An :class:`Editor` owns a private copy of the workflow dict. Each method applies
one edit or raises a structured :class:`~trigger_designer.core.headless.exit_codes.CliError`
and leaves nothing half-done for the caller to clean up: the caller keeps the
original and only writes ``editor.data`` after every edit succeeded, so a patch
is all or nothing.
"""

from __future__ import annotations

import copy
import difflib
import math
import os
from collections import defaultdict, deque
from typing import Any

from trigger_designer.core.authoring import templates
from trigger_designer.core.authoring.model import (
    BAD_EDIT,
    INVALID_CONNECTION,
    IdPool,
    describe,
    edges_of,
    fail,
    input_index,
    nodes_of,
    op_of,
    output_index,
    resolve_node,
    socket_owner,
)
from trigger_designer.core.authoring.validate import (
    MAX_LABEL_CHARS,
    MAX_TITLE_CHARS,
    _inside,
    check_settings,
    coerce_raw,
)
from trigger_designer.core.headless.node_spec import SETTINGS_SOURCES, SOCKETS
from trigger_designer.core.headless.op_catalog import OPS
from trigger_designer.core.headless.workflow_file import find_cycle

ROW, COL = 200.0, 300.0
MAX_NODES = 2000


def _number(value: Any, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise fail(BAD_EDIT, f"{name} must be a number.")
    return float(value)


class Editor:
    """One batch of edits over a copy of ``data``."""

    def __init__(
        self,
        data: dict,
        *,
        base_dir: str,
        extra_paths: tuple[str, ...] = (),
    ) -> None:
        self.data = copy.deepcopy(data)
        self.base_dir = base_dir
        self.extra_paths = extra_paths
        self.pool = IdPool(self.data)
        #: patch-local names for nodes created earlier in the same batch.
        self.aliases: dict[str, int] = {}

    # ------------------------------------------------------------- lookups
    def node(self, ref: Any) -> dict:
        return resolve_node(self.data, ref, self.aliases)

    def _holder(self, node: dict) -> dict:
        """Where this node keeps its settings (``content.settings`` or ``content``)."""
        content = node.setdefault("content", {})
        source = SETTINGS_SOURCES.get(op_of(node))
        if source is not None and source.location != "settings":
            return content
        holder = content.setdefault("settings", {})
        return holder

    def _free_position(self, x: float, y: float) -> tuple[float, float]:
        taken = [
            (n.get("pos_x", 0.0), n.get("pos_y", 0.0)) for n in nodes_of(self.data)
        ]
        while any(
            abs(px - x) < COL * 0.8 and abs(py - y) < ROW * 0.8 for px, py in taken
        ):
            x += COL
        return x, y

    # ------------------------------------------------------------ add node
    def add_node(
        self,
        op: str,
        *,
        settings: dict | None = None,
        title: str | None = None,
        x: Any = None,
        y: Any = None,
        after: Any = None,
        ref: str | None = None,
    ) -> dict:
        if op not in SOCKETS or op not in OPS:
            near = difflib.get_close_matches(str(op), list(SOCKETS), n=3, cutoff=0.5)
            hint = "Run `ops` to list every node type."
            if near:
                hint = "Did you mean: " + ", ".join(near) + "? " + hint
            raise fail("TD-CLI-003", f"Unknown node type '{op}'.", hint)
        if len(nodes_of(self.data)) >= MAX_NODES:
            raise fail(BAD_EDIT, f"A workflow can have at most {MAX_NODES} nodes.")
        if title is not None and (
            not isinstance(title, str)
            or not title.strip()
            or len(title) > MAX_TITLE_CHARS
        ):
            raise fail(
                BAD_EDIT, f"A title is text of 1 to {MAX_TITLE_CHARS} characters."
            )
        if ref is not None:
            self._check_alias(ref)
        if (x is None) != (y is None):
            raise fail(BAD_EDIT, "Give both x and y, or neither.")
        if settings:
            settings = coerce_raw(op, settings)
            check_settings(
                op, settings, base_dir=self.base_dir, extra_paths=self.extra_paths
            )
        if x is not None:
            px, py = _number(x, "x"), _number(y, "y")
        elif after is not None:
            above = self.node(after)
            px, py = self._free_position(
                float(above.get("pos_x", 0.0)), float(above.get("pos_y", 0.0)) + ROW
            )
        else:
            nodes = nodes_of(self.data)
            if nodes:
                px = min(float(n.get("pos_x", 0.0)) for n in nodes)
                py = max(float(n.get("pos_y", 0.0)) for n in nodes) + ROW
                px, py = self._free_position(px, py)
            else:
                px, py = 0.0, 0.0
        sockets = SOCKETS[op]
        node_id = self.pool.take()
        ids = [self.pool.take() for _ in range(sockets.inputs + len(sockets.outputs))]
        node = templates.new_node(op, node_id, ids, px, py)
        if title:
            # The editor always shows a node's own type name as its title and
            # ignores a different one saved in the file, so a name the caller
            # chose is stored as the label drawn under the node.
            node["label_text"] = title.strip()
            node["label_visible"] = True
        if settings:
            settings = self._complete_paths(op, settings)
            self._holder(node).update(copy.deepcopy(settings))
            self._sync_stored_paths(node, settings)
        self.data.setdefault("nodes", []).append(node)
        if ref is not None:
            self.aliases[ref] = node_id
        return describe(node)

    def _complete_paths(self, op: str, settings: dict) -> dict:
        """File settings as complete paths.

        A relative path means different things to different callers (the
        command line reads it from the workflow's folder, the editor from the
        folder it was started in), so it is stored in full. ``check_settings``
        has already kept it inside the allowed folders.
        """
        info = OPS[op]
        keys = {*info.input_keys, *info.output_keys}
        out = dict(settings)
        for key in keys & out.keys():
            value = out[key]
            if isinstance(value, str) and value.strip():
                out[key] = os.path.normpath(os.path.join(self.base_dir, value.strip()))
        return out

    def output_folders(self) -> dict[str, list[str]]:
        """Folders of this workflow's file outputs that do not exist yet.

        ``creatable`` are inside the allowed folders (the edit may make them);
        ``blocked`` are not (it will not).
        """
        creatable: list[str] = []
        blocked: list[str] = []
        roots = (self.base_dir, *self.extra_paths)
        for node in nodes_of(self.data):
            info = OPS.get(str(node.get("op") or ""))
            if info is None:
                continue
            holder = self._holder(node)
            for key in info.output_keys:
                value = holder.get(key)
                if not isinstance(value, str) or not value.strip():
                    continue
                path = os.path.normpath(os.path.join(self.base_dir, value.strip()))
                folder = os.path.dirname(path)
                if os.path.isdir(folder) or folder in creatable or folder in blocked:
                    continue
                inside = any(_inside(folder, root) for root in roots)
                (creatable if inside else blocked).append(folder)
        return {"creatable": creatable, "blocked": blocked}

    def _sync_stored_paths(self, node: dict, settings: dict) -> None:
        """Keep a File Input's ``filePathRel`` as the editor does.

        The editor resolves a File Input through ``filePathRel`` (relative to the
        workflow's folder) and only falls back to ``filePath``. A path set
        without it would read as 'Missing input file' in the editor.
        """
        if node.get("op") != "input.file_input" or "filePath" not in settings:
            return
        content = node["content"]
        value = str(content.get("filePath") or "")
        if not value:
            content["filePathRel"] = ""
            return
        from trigger_designer.core.inputs import to_stored_paths

        absolute = os.path.normpath(os.path.join(self.base_dir, value))
        content["filePathRel"] = to_stored_paths(absolute, self.base_dir)[1]

    def _check_alias(self, ref: str) -> None:
        if not isinstance(ref, str) or not ref.isidentifier():
            raise fail(
                BAD_EDIT,
                f"A ref is a short name such as 'f1', not {ref!r}.",
                "Use letters, digits and _, not starting with a digit.",
            )
        if ref in self.aliases:
            raise fail(BAD_EDIT, f"The ref '{ref}' is already used in this batch.")

    # --------------------------------------------------------- remove node
    def remove_node(self, ref: Any) -> dict:
        node = self.node(ref)
        node_id = node.get("id")
        params = [
            p.get("name")
            for p in (self.data.get("workflow_metadata") or {}).get("parameters") or []
            if isinstance(p, dict) and p.get("node_id") == node_id
        ]
        if params:
            raise fail(
                BAD_EDIT,
                f"'{node.get('title')}' is used by the parameter(s) "
                f"{', '.join(map(str, params))}.",
                "Remove the parameter first (`params remove`).",
            )
        own = {
            s["id"]
            for key in ("inputs", "outputs")
            for s in node.get(key) or []
            if isinstance(s, dict) and "id" in s
        }
        gone = [
            e
            for e in edges_of(self.data)
            if e.get("start") in own or e.get("end") in own
        ]
        touched = {e["end"] for e in gone if e.get("end") not in own}
        self.data["edges"] = [e for e in edges_of(self.data) if e not in gone]
        self.data["nodes"] = [n for n in nodes_of(self.data) if n is not node]
        for group in self.data.get("groups") or []:
            if isinstance(group, dict) and isinstance(group.get("children"), list):
                group["children"] = [c for c in group["children"] if c != node_id]
        self._reindex(touched)
        self.aliases = {k: v for k, v in self.aliases.items() if v != node_id}
        return {"removed": describe(node), "removed_edges": len(gone)}

    # ----------------------------------------------------------- connecting
    def _edge_between(self, start: int, end: int) -> dict | None:
        for edge in edges_of(self.data):
            if edge.get("start") == start and edge.get("end") == end:
                return edge
        return None

    def _ends(self, src: Any, output: Any, dst: Any, inp: Any):
        a, b = self.node(src), self.node(dst)
        oi, ii = output_index(a, output), input_index(b, inp)
        out_sock = a["outputs"][oi]
        in_sock = b["inputs"][ii]
        return a, b, oi, ii, out_sock, in_sock

    def connect(self, src: Any, output: Any, dst: Any, inp: Any = 0) -> dict:
        a, b, oi, ii, out_sock, in_sock = self._ends(src, output, dst, inp)
        if a is b:
            raise fail(INVALID_CONNECTION, f"'{a.get('title')}' cannot feed itself.")
        if self._edge_between(out_sock["id"], in_sock["id"]) is not None:
            raise fail(
                INVALID_CONNECTION,
                f"'{a.get('title')}' output {oi} is already connected to "
                f"'{b.get('title')}' input {ii}.",
            )
        existing = [e for e in edges_of(self.data) if e.get("end") == in_sock["id"]]
        multi = bool(in_sock.get("multi_edges"))
        if existing and not multi:
            raise fail(
                INVALID_CONNECTION,
                f"'{b.get('title')}' input {ii} already has a connection.",
                "Disconnect it first, or use another input.",
            )
        edge = templates.new_edge(
            self.pool.take(),
            out_sock["id"],
            in_sock["id"],
            label=f"#{len(existing) + 1}" if multi else "",
            input_index=len(existing) if multi else 0,
        )
        self.data.setdefault("edges", []).append(edge)
        if find_cycle(self.data):
            self.data["edges"].remove(edge)
            raise fail(
                INVALID_CONNECTION,
                f"Connecting '{a.get('title')}' to '{b.get('title')}' would make a "
                "loop: a node would depend on its own output.",
            )
        return {
            "edge": edge["id"],
            "from": {"node": a["id"], "output": oi},
            "to": {"node": b["id"], "input": ii},
        }

    def disconnect(self, src: Any, output: Any, dst: Any, inp: Any = 0) -> dict:
        a, b, oi, ii, out_sock, in_sock = self._ends(src, output, dst, inp)
        edge = self._edge_between(out_sock["id"], in_sock["id"])
        if edge is None:
            raise fail(
                INVALID_CONNECTION,
                f"'{a.get('title')}' output {oi} is not connected to "
                f"'{b.get('title')}' input {ii}.",
            )
        self.data["edges"].remove(edge)
        self._reindex({in_sock["id"]})
        return {
            "edge": edge["id"],
            "from": {"node": a["id"], "output": oi},
            "to": {"node": b["id"], "input": ii},
        }

    def _reindex(self, end_ids: set[int]) -> None:
        """Keep the order and ``#n`` labels of a multi-input socket gap-free."""
        owner = socket_owner(self.data)
        for end in end_ids:
            found = owner.get(end)
            if found is None:
                continue
            node, kind, index = found
            socket = node[kind][index] if index < len(node[kind]) else {}
            if not socket.get("multi_edges"):
                continue
            edges = sorted(
                (e for e in edges_of(self.data) if e.get("end") == end),
                key=lambda e: e.get("input_index", 0),
            )
            for position, edge in enumerate(edges):
                edge["input_index"] = position
                edge["label"] = f"#{position + 1}"

    # --------------------------------------------------------------- values
    def set_settings(self, ref: Any, settings: dict) -> dict:
        node = self.node(ref)
        op = op_of(node)
        if "op" not in node:
            raise fail(
                BAD_EDIT,
                f"'{node.get('title')}' is saved in the old file format, so its "
                "settings cannot be edited here.",
                "Open the workflow in Trigger Designer and save it once, then retry.",
            )
        if not isinstance(settings, dict) or not settings:
            raise fail(BAD_EDIT, "Give at least one setting as name: value.")
        settings = coerce_raw(op, settings)
        check_settings(
            op, settings, base_dir=self.base_dir, extra_paths=self.extra_paths
        )
        settings = self._complete_paths(op, settings)
        holder = self._holder(node)
        changed = []
        for key, value in settings.items():
            if holder.get(key) != value:
                holder[key] = copy.deepcopy(value)
                changed.append(key)
        self._sync_stored_paths(node, settings)
        return {"node": describe(node), "changed": changed}

    def set_label(self, ref: Any, text: Any, visible: Any = None) -> dict:
        node = self.node(ref)
        if not isinstance(text, str) or len(text) > MAX_LABEL_CHARS:
            raise fail(
                BAD_EDIT,
                f"A label is text of up to {MAX_LABEL_CHARS} characters.",
            )
        node["label_text"] = text.strip()
        if visible is not None:
            if not isinstance(visible, bool):
                raise fail(BAD_EDIT, "visible must be true or false.")
            node["label_visible"] = visible
        return {"node": describe(node), "label": node["label_text"]}

    # --------------------------------------------------------------- layout
    def auto_layout(self) -> dict:
        """Place connected nodes in rows by depth, top to bottom."""
        if self.data.get("groups"):
            raise fail(
                BAD_EDIT,
                "This workflow has groups; a layout would move nodes out of them.",
                "Arrange the nodes in Trigger Designer instead.",
            )
        nodes = [n for n in nodes_of(self.data) if n.get("inputs") or n.get("outputs")]
        if not nodes:
            return {"moved": 0}
        owner = socket_owner(self.data)
        index = {id(n): i for i, n in enumerate(nodes)}
        succ: dict[int, set[int]] = defaultdict(set)
        indeg = dict.fromkeys(range(len(nodes)), 0)
        for edge in edges_of(self.data):
            a, b = owner.get(edge.get("start")), owner.get(edge.get("end"))
            if a is None or b is None:
                continue
            i, j = index.get(id(a[0])), index.get(id(b[0]))
            if i is None or j is None or j in succ[i]:
                continue
            succ[i].add(j)
            indeg[j] += 1
        depth = dict.fromkeys(indeg, 0)
        queue = deque(i for i, d in indeg.items() if d == 0)
        while queue:
            i = queue.popleft()
            for j in succ[i]:
                depth[j] = max(depth[j], depth[i] + 1)
                indeg[j] -= 1
                if indeg[j] == 0:
                    queue.append(j)
        layers: dict[int, list[dict]] = defaultdict(list)
        for i, node in enumerate(nodes):
            layers[depth[i]].append(node)
        origin_x = min(float(n.get("pos_x", 0.0)) for n in nodes)
        origin_y = min(float(n.get("pos_y", 0.0)) for n in nodes)
        moved = 0
        for level in sorted(layers):
            row = sorted(
                layers[level], key=lambda n: (n.get("pos_x", 0.0), n.get("id"))
            )
            for col, node in enumerate(row):
                x, y = origin_x + col * COL, origin_y + level * ROW
                if (node.get("pos_x"), node.get("pos_y")) != (x, y):
                    node["pos_x"], node["pos_y"] = x, y
                    moved += 1
        return {"moved": moved}
