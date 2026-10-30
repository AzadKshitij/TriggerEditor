"""Runtime state services that a ``TriggerNode`` delegates to.

``NodeErrorState`` owns a node's structured errors: the per-source map, the
tooltip and badge projection, the Problems dock bridge and the knock-on clear.
It never imports ``node_base``; the node is only a type here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from trigger_designer.core.errors import NodeError

if TYPE_CHECKING:
    from trigger_designer.qt.node_base import TriggerNode


class NodeErrorState:
    """Errors for one node, keyed by source (``"live"`` or ``"run"``)."""

    def __init__(self, node: "TriggerNode") -> None:
        self.node = node
        self.by_source: dict[str, NodeError] = {}
        #: Edits that have not run yet (the yellow "!").
        self.changes_pending = False

    @property
    def current(self) -> NodeError | None:
        """The error to show: a run error outranks a live one."""
        return self.by_source.get("run") or self.by_source.get("live")

    def set(self, error: NodeError, source: str = "live") -> None:
        old = self.by_source.get(source)
        self.by_source[source] = error
        self.apply()
        if old is None or old.fingerprint != error.fingerprint:
            self.log_new(error)
        problems = self.problems_store()
        if problems is not None and not (error.knock_on and source == "live"):
            problems.upsert(error, source)

    def clear(
        self, source: str | None = None, *, _seen: set[int] | None = None
    ) -> None:
        seen = set() if _seen is None else _seen
        if id(self.node) in seen:
            return
        seen.add(id(self.node))
        if source is None:
            removed = list(self.by_source)
            self.by_source.clear()
        else:
            removed = [source] if self.by_source.pop(source, None) is not None else []
        self.apply()
        problems = self.problems_store()
        if problems is not None:
            for item in removed:
                problems.remove(self.node.id, item)
        if source in (None, "run"):
            for child in self.node.getChildrenNodes():
                current = getattr(child, "current_error", None)
                if current is not None and current.knock_on:
                    child.clear_error("run", _seen=seen)

    def set_changes_pending(self, pending: bool) -> None:
        """Show (or clear) the yellow "!" for edits that have not run yet."""
        if pending == self.changes_pending:
            return
        self.changes_pending = pending
        self.apply()

    def apply(self) -> None:
        """Project the current error onto the node's tooltip and badge."""
        error = self.current
        if error:
            tooltip, badge = error.render_tooltip(), error.severity
        elif self.changes_pending:
            tooltip = "Changes pending - the node runs when you click away"
            badge = "pending"
        else:
            tooltip, badge = "", ""
        self.node._set_node_tooltip(tooltip)
        gr = getattr(self.node, "grNode", None)
        if gr is not None:
            try:
                gr.set_error_badge(badge)
            except RuntimeError:
                pass

    def problems_store(self):
        scene = self.node.scene
        try:
            view = scene.getView() if hasattr(scene, "getView") else None
        except IndexError, RuntimeError, AttributeError:
            view = None
        owner = view.parentWidget() if view is not None else None
        while owner is not None and not hasattr(owner, "problems"):
            owner = owner.parentWidget()
        return getattr(owner, "problems", None)

    def log_new(self, error: NodeError) -> None:
        try:
            logger.error(error.render_text(include_technical=True))
        except Exception:  # noqa: BLE001, S110 - logging must never break eval
            pass
        try:
            from trigger_designer.qt.helpers import global_logger

            global_logger.error(error.render_summary())
        except Exception:  # noqa: BLE001, S110 - dock may not exist in tests
            pass
