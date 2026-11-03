"""Topological node-run loop shared by the GUI worker and any headless runner.

Qt-free on purpose (``threading``, ``dataclasses`` and ``typing`` only): the
GUI ``WorkflowWorker`` and a command-line runner must execute the *same* loop
so stop, continue, skip and cancel semantics cannot diverge.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LoopOutcome:
    """What a run did. ``success`` is False when anything failed, was skipped
    or the run was cancelled."""

    success: bool
    cancelled: bool
    executed: int
    failed: tuple
    skipped: tuple


def run_nodes(
    nodes: Sequence[Any],
    executor: Any,
    *,
    continue_on_error: bool = False,
    upstream: Mapping[Any, Sequence[Any]] | None = None,
    cancel: threading.Event | None = None,
    on_node_started: Callable[[Any], None] | None = None,
    on_node_finished: Callable[[Any, Any], None] | None = None,
    on_node_errored: Callable[[Any, BaseException], None] | None = None,
    on_node_skipped: Callable[[Any, Any | None], None] | None = None,
) -> LoopOutcome:
    """Execute ``nodes`` (already topologically ordered) one by one.

    * ``continue_on_error=False`` stops at the first failed node and sends no
      skip notifications for the rest. ``True`` carries on; a node whose
      direct upstream (``upstream[node]``) failed or was skipped is skipped
      itself (transitively, since skipped nodes count as blocked).
    * ``cancel`` is checked between nodes only: every remaining node gets
      ``on_node_skipped(node, None)``. A running node is never interrupted.
    * ``on_node_finished(node, result)`` fires for success and failure alike
      (read ``result.success``); ``on_node_errored(node, exc)`` fires only when
      ``execute_node`` itself raised an ``Exception``.
    * Exceptions raised by callbacks propagate. ``KeyboardInterrupt`` and
      ``SystemExit`` are never caught.
    """
    upstream = upstream or {}
    reset = getattr(executor, "reset_cancel", None)
    if callable(reset):
        reset()

    blocked: set = set()  # failed or skipped nodes (identity-hashable)
    failed: list = []
    skipped: list = []
    executed = 0
    cancelled = False
    ordered = list(nodes)

    for index, node in enumerate(ordered):
        if cancel is not None and cancel.is_set():
            cancelled = True
            for rest in ordered[index:]:
                skipped.append(rest)
                if on_node_skipped is not None:
                    on_node_skipped(rest, None)
            break

        blockers = [parent for parent in upstream.get(node, ()) if parent in blocked]
        if blockers:
            blocked.add(node)
            skipped.append(node)
            if on_node_skipped is not None:
                on_node_skipped(node, blockers[0])
            continue

        if on_node_started is not None:
            on_node_started(node)
        try:
            result = executor.execute_node(node)
        except Exception as exc:  # noqa: BLE001 - mirrors the old worker
            failed.append(node)
            blocked.add(node)
            if on_node_errored is not None:
                on_node_errored(node, exc)
            if not continue_on_error:
                break
            continue

        executed += 1
        if on_node_finished is not None:
            on_node_finished(node, result)
        if not getattr(result, "success", False):
            failed.append(node)
            blocked.add(node)
            if not continue_on_error:
                break

    success = not failed and not skipped and not cancelled
    return LoopOutcome(success, cancelled, executed, tuple(failed), tuple(skipped))
