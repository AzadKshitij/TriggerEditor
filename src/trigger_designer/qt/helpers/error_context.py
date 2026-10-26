"""Qt-side context and enrichment jobs for the error translator."""

from __future__ import annotations

from typing import Any

from nodeeditor.node_graph import ancestors as graph_ancestors

from trigger_designer.core.errors import (
    Ancestor,
    EnrichJob,
    ErrorContext,
    NodeError,
    normalise_path,
)


def _node_identity(node) -> tuple[str, str, str | None]:
    title = getattr(type(node), "node_title", None) or getattr(node, "node_title", "")
    label = str(getattr(node, "label_text", "") or "").strip()
    node_label = f"{title} '{label}'" if title and label else (title or "")
    op = None
    try:
        op = f"{node.node_type.value}.{node.node_code.name.lower()}"
    except Exception:  # noqa: BLE001, S110
        pass
    return title or "", node_label, op


def _first_frame(node) -> Any:
    value = getattr(node, "value", None)
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, dict) and entry.get("data") is not None:
                return entry["data"]
    return None


def _input_edges(node) -> list[tuple[Any, Any]]:
    """Every incoming edge, in the node's own read order when it has one.

    ``Node.getInput(index)`` returns only the first edge on a socket. A Union
    (or any other multi-input node) can have several edges on one socket, so
    walk every edge and preserve ``getOrderedEdges()`` order for collectors.
    Remaining sockets are appended in input-index order.
    """
    pairs: list[tuple[Any, Any]] = []
    seen: set[int] = set()
    sockets = list(getattr(node, "inputs", ()) or ())

    ordered_getter = getattr(node, "getOrderedEdges", None)
    if callable(ordered_getter):
        try:
            ordered = list(ordered_getter() or ())
        except Exception:  # noqa: BLE001 - context is best effort
            ordered = []
        for edge in ordered:
            for socket in sockets:
                if edge not in (getattr(socket, "edges", ()) or ()):
                    continue
                if id(edge) not in seen:
                    pairs.append((socket, edge))
                    seen.add(id(edge))
                break

    for socket in sockets:
        try:
            edges = list(socket.orderedEdges())
        except (AttributeError, RuntimeError, TypeError):
            edges = list(getattr(socket, "edges", ()) or ())
        for edge in edges:
            if id(edge) in seen:
                continue
            pairs.append((socket, edge))
            seen.add(id(edge))
    return pairs


def _edge_frame(socket, edge) -> Any:
    """Return the upstream frame connected to ``socket`` through ``edge``."""
    try:
        upstream_socket = edge.getOtherSocket(socket)
    except (AttributeError, RuntimeError):
        return None
    upstream = getattr(upstream_socket, "node", None)
    if upstream_socket is None or upstream is None:
        return None
    value = getattr(upstream, "value", None)
    index = getattr(upstream_socket, "index", None)
    if not isinstance(index, int):
        return _first_frame(upstream)
    try:
        entry = value[index]
    except (IndexError, KeyError, TypeError):
        return None
    return entry.get("data") if isinstance(entry, dict) else None


def _frames_into(node) -> tuple[Any, ...]:
    frames: list[Any] = []
    for socket, edge in _input_edges(node):
        data = _edge_frame(socket, edge)
        if data is not None:
            frames.append(data)
    return tuple(frames)


def _input_schema(node) -> tuple[tuple[str, ...], dict[str, str]]:
    try:
        from trigger_designer.qt.node_base import frame_schema

        frames = _frames_into(node)
        if not frames:
            return (), {}
        schema = frame_schema(frames[0])
        return tuple(schema), {name: str(dtype) for name, dtype in schema.items()}
    except Exception:  # noqa: BLE001
        return (), {}


def build_context(node, window=None, phase: str = "run") -> ErrorContext:
    ctx = ErrorContext.from_node(node, phase)
    scene = getattr(node, "scene", None)
    nodes = list(getattr(scene, "nodes", ()) or ())
    if window is not None:
        nodes = list(getattr(window.scene, "nodes", nodes) or nodes)

    for item in nodes:
        _title, label, op = _node_identity(item)
        node_id = getattr(item, "id", None)
        if node_id is None:
            continue
        ctx.node_labels[node_id] = label
        if op:
            ctx.op = ctx.op or op
        content = getattr(item, "content", None)
        if op and op.endswith("file_input"):
            path = getattr(content, "filePath", None)
            if path:
                ctx.input_paths[normalise_path(path)] = node_id
        if op and op.endswith("file_output"):
            path = getattr(content, "filePath", None)
            if path:
                ctx.output_paths[normalise_path(path)] = node_id
        values = [getattr(item, "value", None), getattr(item, "param", None)]
        for entry in values:
            if isinstance(entry, list):
                for output in entry:
                    if isinstance(output, dict):
                        var = output.get("variable_name")
                        if var:
                            ctx.variable_owners[str(var)] = node_id
        if content is not None:
            for name in dir(content):
                if name == "variable_name" or name.endswith("_variable_name"):
                    try:
                        var = getattr(content, name)
                    except Exception:  # noqa: BLE001, S112
                        continue
                    if isinstance(var, str) and var:
                        ctx.variable_owners[var] = node_id

    columns, dtypes = _input_schema(node)
    ctx.input_columns = columns
    ctx.input_dtypes = dtypes
    content = getattr(node, "content", None)
    getter = getattr(content, "referenced_columns", None)
    if callable(getter):
        try:
            ctx.referenced_columns = tuple(getter() or ())
        except Exception:  # noqa: BLE001
            ctx.referenced_columns = ()
    ctx.date_format = getattr(content, "date_format", None)
    return ctx


def build_enrich_job(
    node,
    window,
    error: NodeError,
    phase: str = "run",
) -> EnrichJob:
    from trigger_designer.qt.preferences import get_preferences

    scene = getattr(node, "scene", None)
    nodes = list(getattr(scene, "nodes", ()) or ())
    labels: dict[int, str] = {}
    titles: dict[int, str] = {}
    ops: dict[int, str] = {}
    for item in nodes:
        title, label, op = _node_identity(item)
        node_id = getattr(item, "id", None)
        if node_id is None:
            continue
        labels[node_id] = label
        titles[node_id] = title
        if op:
            ops[node_id] = op

    inputs_of: dict[int, tuple[Any, ...]] = {}
    target_id = getattr(node, "id", None)
    if target_id is None:
        target_id = id(node)
    inputs_of[target_id] = _frames_into(node)

    ancestors: list[Ancestor] = []
    upstream_nodes = list(graph_ancestors(scene, node)) if scene is not None else []
    # graph_ancestors is nearest-first, breadth-first and deduplicated. Reverse
    # it so attribution still tests the farthest cause before the nearest one.
    for _depth, upstream in enumerate(reversed(upstream_nodes), start=1):
        upstream_id = getattr(upstream, "id", None)
        if upstream_id is None:
            upstream_id = id(upstream)
        inputs_of[upstream_id] = _frames_into(upstream)
        ancestors.append(Ancestor(upstream_id, _first_frame(upstream)))

    prefs = get_preferences()
    return EnrichJob(
        error=error,
        ancestors=tuple(ancestors),
        inputs_of=inputs_of,
        labels=labels,
        titles=titles,
        ops=ops,
        attribute=True,
        locate=bool(prefs.get("errors/locate_rows", True)),
        row_cap=int(prefs.get("errors/locate_row_cap", 5_000_000) or 5_000_000),
        redact=bool(prefs.get("errors/redact_values", False)),
    )
