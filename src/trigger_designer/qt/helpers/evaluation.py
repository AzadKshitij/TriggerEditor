"""Ordered, coalesced evaluation for the live workflow canvas.

The inspector used to treat every change notification as "evaluate now". A
single drag could therefore compute the same node several times: once for the
producer, once for the consumer, once when the consumer's input socket was
notified, and again when an eager push reached a join. This coordinator keeps
one pending set per scene, expands it to the affected closure, and walks that
closure in dependency order exactly once.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import contextmanager
from typing import Any

from loguru import logger
from nodeeditor.node_graph import (
    GraphCycleError,
    descendants,
    topological_order,
)
from qtpy.QtCore import QTimer

from trigger_designer.qt.helpers.edge_validators import report_cycle_once

#: A pass should terminate long before this. A listener that keeps requesting
#: work is a bug; the cap keeps a Qt slot from freezing the application.
MAX_PASSES = 32


def has_blocked_required_input(node, blocked: set[Any]) -> bool:
    """Whether ``node`` has a required input that cannot feed a computation.

    ``Node.getInput(i)`` returns only ``edges[0]``. A Union or any other
    multi-edge socket can have a failed branch in a later edge, so every edge
    on every required input socket has to be inspected.
    """
    optional = getattr(node, "optional_inputs", None) or ()
    for index, socket in enumerate(getattr(node, "inputs", ())):
        if index in optional:
            continue
        edges = list(getattr(socket, "edges", ()) or ())
        if not edges:
            return True
        for edge in edges:
            other = edge.getOtherSocket(socket)
            upstream = getattr(other, "node", None)
            if upstream is None or upstream in blocked:
                return True
            is_invalid = getattr(upstream, "isInvalid", None)
            if callable(is_invalid) and is_invalid():
                return True
    return False


class EvaluationCoordinator:
    """Own the pending origins and run ordered evaluation passes for a scene."""

    def __init__(self, scene) -> None:
        self.scene = scene
        self._pending: set[Any] = set()
        self._flushing = False
        self._flush_scheduled = False
        self._generation = 0

    # -- pending work ---------------------------------------------------
    @property
    def pending(self) -> set[Any]:
        """A copy of the origins waiting for the next pass; for diagnostics."""
        return set(self._pending)

    def request_evaluation(self, origin, defer: bool = False) -> None:
        """Queue ``origin`` and flush now, or on the next event turn."""
        if origin is None or origin not in getattr(self.scene, "nodes", ()):
            return
        self._pending.add(origin)
        origin.markDirty()

        if (
            getattr(self.scene, "_bulk_loading", False)
            or self._flushing
            or getattr(self.scene, "_eval_depth", 0) > 0
        ):
            return
        if defer:
            self._schedule_flush()
            return
        self.flush_now()

    def flush_now(self) -> None:
        """Evaluate every pending origin and its descendants in order."""
        if (
            getattr(self.scene, "_bulk_loading", False)
            or self._flushing
            or getattr(self.scene, "_eval_depth", 0) > 0
        ):
            return

        self._flushing = True
        try:
            for _ in range(MAX_PASSES):
                if not self._pending:
                    break
                origins = set(self._pending)
                self._pending.clear()
                affected = self._affected(origins)
                if affected:
                    self._run_affected(
                        affected,
                        block_on_error=True,
                        mark_dirty=True,
                        report=None,
                    )
            if self._pending:
                logger.warning(
                    "Evaluation still has {} pending nodes after {} passes",
                    len(self._pending),
                    MAX_PASSES,
                )
        finally:
            self._flushing = False

    # -- full and targeted passes --------------------------------------
    def evaluate_all(self, report: Callable[[str], None] | None = None) -> None:
        """Evaluate every node once, as a load or undo restore needs."""
        if (
            getattr(self.scene, "_bulk_loading", False)
            or self._flushing
            or getattr(self.scene, "_eval_depth", 0) > 0
        ):
            return
        # The full pass covers anything that was deferred before it. Bumping
        # the generation keeps a timer scheduled by an older scene state from
        # running afterwards.
        self.reset_pending()
        self._flushing = True
        try:
            self._run_affected(
                set(getattr(self.scene, "nodes", ())),
                block_on_error=False,
                mark_dirty=True,
                report=report,
            )
        finally:
            self._flushing = False

    def evaluate_nodes(
        self,
        nodes: Iterable[Any],
        *,
        block_on_error: bool = False,
        report: Callable[[str], None] | None = None,
        mark_dirty: bool = True,
    ) -> None:
        """Evaluate the closure of ``nodes`` through the ordered path."""
        scene_nodes = set(getattr(self.scene, "nodes", ()))
        origins = {node for node in nodes if node is not None and node in scene_nodes}
        if not origins:
            return
        if (
            getattr(self.scene, "_bulk_loading", False)
            or self._flushing
            or getattr(self.scene, "_eval_depth", 0) > 0
        ):
            self._pending.update(origins)
            if mark_dirty:
                for node in origins:
                    node.markDirty()
            return

        self._flushing = True
        try:
            self._run_affected(
                self._affected(origins),
                block_on_error=block_on_error,
                mark_dirty=mark_dirty,
                report=report,
            )
        finally:
            self._flushing = False

    # -- lifecycle ------------------------------------------------------
    def reset_pending(self) -> None:
        """Drop queued work and invalidate any timer from the old state."""
        self._pending.clear()
        self._generation += 1
        self._flush_scheduled = False

    def begin_bulk_load(self) -> None:
        self.reset_pending()
        signatures = getattr(self.scene, "_reported_cycle_signatures", None)
        if signatures is not None:
            signatures.clear()

    def end_bulk_load(self) -> None:
        self.reset_pending()

    def close(self) -> None:
        self.reset_pending()

    # -- internals ------------------------------------------------------
    def _schedule_flush(self) -> None:
        if self._flush_scheduled:
            return
        self._flush_scheduled = True
        generation = self._generation

        def fire() -> None:
            if generation != self._generation:
                return
            self._flush_scheduled = False
            self.flush_now()

        QTimer.singleShot(0, fire)

    def _affected(self, origins: Iterable[Any]) -> set[Any]:
        scene = self.scene
        nodes = set(getattr(scene, "nodes", ()))
        affected: set[Any] = set()
        for origin in origins:
            if origin not in nodes:
                continue
            affected.add(origin)
            affected.update(descendants(scene, origin))
        return affected

    def _ordered(self, affected: set[Any], report) -> list[Any]:
        scene = self.scene
        try:
            return [node for node in topological_order(scene) if node in affected]
        except GraphCycleError as exc:
            self._report_cycle(exc, report)
            return [node for node in getattr(scene, "nodes", ()) if node in affected]

    def _report_cycle(self, exc: GraphCycleError, report) -> None:
        sink = report or getattr(self.scene, "cycle_reporter", None) or logger.warning
        try:
            report_cycle_once(self.scene, exc, sink)
        except Exception:  # noqa: BLE001 - reporting must not break evaluation
            logger.exception("Failed to report a workflow cycle")

    def _run_affected(
        self,
        affected: set[Any],
        *,
        block_on_error: bool,
        mark_dirty: bool,
        report,
    ) -> None:
        if not affected:
            return
        if mark_dirty:
            for node in affected:
                # Marking an already-dirty node again is a package call plus
                # an ``onMarkedDirty`` hook for no state change. A full pass
                # often starts with every node dirty; skip those calls.
                if not node.isDirty():
                    node.markDirty()

        ordered = self._ordered(affected, report)
        # ``scene.nodes`` is a list. Do not test membership inside the per-node
        # loop: that turns a 500-node full pass into 250k identity comparisons.
        scene_nodes = set(getattr(self.scene, "nodes", ()))
        with self.batch_evaluation():
            blocked: set[Any] = set()
            for node in ordered:
                if node not in scene_nodes:
                    continue
                if block_on_error and has_blocked_required_input(node, blocked):
                    continue
                value = node.eval()
                if block_on_error and (value is None or node.isInvalid()):
                    blocked.add(node)

    @contextmanager
    def batch_evaluation(self):
        """Suppress eager push for the duration of a flat ordered pass."""
        previous = getattr(self.scene, "_batch_evaluating", False)
        self.scene._batch_evaluating = True
        try:
            yield
        finally:
            self.scene._batch_evaluating = previous
