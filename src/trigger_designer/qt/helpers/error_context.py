"""Qt-side context and enrichment jobs for the error translator."""

from __future__ import annotations

from typing import Any

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


def _frames_into(node) -> tuple[Any, ...]:
    frames: list[Any] = []
    for index in range(len(getattr(node, "inputs", ()) or ())):
        try:
            upstream = node.getInput(index)
            if upstream is None:
                continue
            socket_index = node.getSocketValue(upstream.outputs, node)
            entry = upstream.value[socket_index]
            data = entry.get("data") if isinstance(entry, dict) else None
            if data is not None:
                frames.append(data)
        except Exception:  # noqa: BLE001, S112 - context is best effort
            continue
    return tuple(frames)


def _input_schema(node) -> tuple[tuple[str, ...], dict[str, str]]:
    try:
        from trigger_designer.qt.node_base import frame_schema

        frame = None
        for index in range(len(getattr(node, "inputs", ()) or ())):
            upstream = node.getInput(index)
            if upstream is None:
                continue
            socket_index = node.getSocketValue(upstream.outputs, node)
            entry = upstream.value[socket_index]
            frame = entry.get("data") if isinstance(entry, dict) else None
            if frame is not None:
                break
        if frame is None:
            return (), {}
        schema = frame_schema(frame)
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

    ancestors: list[tuple[int, Ancestor]] = []
    seen: set[int] = {getattr(node, "id", id(node))}
    queue: list[tuple[Any, int]] = [(node, 0)]
    inputs_of: dict[int, tuple[Any, ...]] = {}
    while queue:
        current, depth = queue.pop(0)
        current_id = getattr(current, "id", None)
        if current_id is not None:
            inputs_of[current_id] = _frames_into(current)
        for index in range(len(getattr(current, "inputs", ()) or ())):
            try:
                upstream = current.getInput(index)
            except Exception:  # noqa: BLE001
                upstream = None
            if upstream is None:
                continue
            upstream_id = getattr(upstream, "id", id(upstream))
            if upstream_id in seen:
                continue
            seen.add(upstream_id)
            ancestors.append((depth + 1, Ancestor(upstream_id, _first_frame(upstream))))
            queue.append((upstream, depth + 1))

    ancestors.sort(key=lambda item: item[0], reverse=True)
    prefs = get_preferences()
    return EnrichJob(
        error=error,
        ancestors=tuple(item for _depth, item in ancestors),
        inputs_of=inputs_of,
        labels=labels,
        titles=titles,
        ops=ops,
        attribute=True,
        locate=bool(prefs.get("errors/locate_rows", True)),
        row_cap=int(prefs.get("errors/locate_row_cap", 5_000_000) or 5_000_000),
        redact=bool(prefs.get("errors/redact_values", False)),
    )
