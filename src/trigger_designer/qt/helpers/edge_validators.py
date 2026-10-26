"""Edge validators and cycle reporting for the workflow canvas."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from nodeeditor.node_edge import Edge
from nodeeditor.node_graph import GraphCycleError, descendants

#: The wording of TD-CLI-004, shown when a cyclic workflow cannot run.
CYCLE_MESSAGE = "The workflow has a cycle. Remove the connection that loops back."


def _normalise_output_input(start_socket, end_socket):
    """Return the data-flow ``(source, target)`` nodes, or ``(None, None)``.

    A drag may start on either socket. Existing validators own wrong-direction
    pairs, so only a genuine output -> input pair reaches the cycle check.
    """
    if start_socket is None or end_socket is None:
        return None, None
    if getattr(start_socket, "is_output", False) and getattr(
        end_socket, "is_input", False
    ):
        return start_socket.node, end_socket.node
    if getattr(start_socket, "is_input", False) and getattr(
        end_socket, "is_output", False
    ):
        return end_socket.node, start_socket.node
    return None, None


def edge_cannot_create_a_cycle(start_socket, end_socket) -> bool:
    """Reject an edge whose target already reaches its source.

    Validation runs before the new edge is inserted. ``descendants`` is
    cycle-safe, so a legacy cyclic scene can still be edited: adding a second
    edge that would close a new loop is rejected, while an existing edge can
    be rerouted without a false positive.
    """
    source, target = _normalise_output_input(start_socket, end_socket)
    if source is None or target is None:
        return True
    if source is target:
        return False
    scene = getattr(source, "scene", None)
    if scene is None or getattr(target, "scene", None) is not scene:
        return True
    return source not in descendants(scene, target)


def _cycles_from(value: Any) -> list[list[Any]]:
    """Normalise a ``GraphCycleError``, a cycle, or a list of cycles."""
    if value is None:
        return []
    if isinstance(value, GraphCycleError):
        return [list(cycle) for cycle in value.cycles]
    if hasattr(value, "cycles"):
        return [list(cycle) for cycle in value.cycles]
    edges = list(value)
    if not edges:
        return []
    if all(hasattr(edge, "start_socket") for edge in edges):
        return [edges]
    return [list(cycle) for cycle in edges if cycle]


def _node_label(node) -> str:
    if node is None:
        return "?"
    title = str(getattr(node, "title", "") or "").strip()
    if title:
        return title
    return str(getattr(type(node), "node_title", "") or type(node).__name__)


def _edge_nodes(edge) -> tuple[Any, Any]:
    start = getattr(edge, "start_socket", None)
    end = getattr(edge, "end_socket", None)
    if (
        start is not None
        and end is not None
        and getattr(start, "is_input", False)
        and getattr(end, "is_output", False)
    ):
        start, end = end, start
    return getattr(start, "node", None), getattr(end, "node", None)


def format_cycle(value: Any) -> str:
    """Format cycles as ``A -> B -> C -> A`` paths.

    ``value`` may be a :class:`GraphCycleError`, one list of edges, or a list
    of such lists. Multiple cycles are separated by semicolons.
    """
    paths: list[str] = []
    for cycle in _cycles_from(value):
        labels: list[str] = []
        for edge in cycle:
            source, target = _edge_nodes(edge)
            source_label = _node_label(source)
            target_label = _node_label(target)
            if not labels:
                labels.append(source_label)
            elif labels[-1] != source_label:
                # A caller may have supplied an unordered edge list. Keep the
                # path readable instead of hiding the discontinuity.
                labels.append(source_label)
            labels.append(target_label)
        if labels and labels[-1] != labels[0]:
            labels.append(labels[0])
        if labels:
            paths.append(" -> ".join(labels))
    return "; ".join(paths)


def cycle_message(value: Any) -> str:
    """Return the TD-CLI-004 wording plus the formatted loop, if known."""
    path = format_cycle(value)
    return f"{CYCLE_MESSAGE} {path}".rstrip()


def _cycle_signature(value: Any) -> tuple[tuple[int, ...], ...]:
    cycles = _cycles_from(value)
    return tuple(sorted(tuple(sorted(id(edge) for edge in cycle)) for cycle in cycles))


def mark_cycle_reported(scene, value: Any) -> None:
    """Remember a cycle signature so a repeated pass does not log it again."""
    signature = _cycle_signature(value)
    if not signature:
        return
    seen = getattr(scene, "_reported_cycle_signatures", None)
    if seen is None:
        seen = set()
        scene._reported_cycle_signatures = seen
    seen.add(signature)


def report_cycle_once(scene, value: Any, report) -> bool:
    """Report a cycle through ``report(message)`` once per scene signature.

    Returns ``True`` when a message was emitted.
    """
    signature = _cycle_signature(value)
    if not signature:
        return False
    seen = getattr(scene, "_reported_cycle_signatures", None)
    if seen is None:
        seen = set()
        scene._reported_cycle_signatures = seen
    if signature in seen:
        return False
    seen.add(signature)
    report(cycle_message(value))
    return True


def cycle_edges(value: Any) -> Iterable[Any]:
    """Yield every edge belonging to one or more cycles."""
    for cycle in _cycles_from(value):
        yield from cycle


def select_cycle_edges(scene, value: Any) -> None:
    """Select the edges of a cycle on the canvas, clearing other selection."""
    gr_scene = getattr(scene, "grScene", None)
    clear = getattr(scene, "clearSelection", None)
    if callable(clear):
        clear()
    elif gr_scene is not None:
        gr_scene.clearSelection()
    for edge in cycle_edges(value):
        gr_edge = getattr(edge, "grEdge", None)
        if gr_edge is not None:
            gr_edge.setSelected(True)


def register_cycle_validator() -> None:
    """Register the cycle validator once, even across test module reloads."""
    if any(
        getattr(validator, "__name__", "") == edge_cannot_create_a_cycle.__name__
        for validator in Edge.getEdgeValidators()
    ):
        return
    Edge.registerEdgeValidator(edge_cannot_create_a_cycle)
