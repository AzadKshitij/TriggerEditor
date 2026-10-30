"""Runtime state services that a ``TriggerNode`` delegates to.

``NodeErrorState`` owns a node's structured errors: the per-source map, the
tooltip and badge projection, the Problems dock bridge and the knock-on clear.
``NodeEvaluator`` owns the evaluation pipeline: cache and re-entrancy checks,
progress reporting, input collection, the one failure transition and the one
invalidation method. Neither imports ``node_base``; the node is only a type.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger
from nodeeditor.utils import dumpException

from trigger_designer.core.errors import (
    ErrorContext,
    NodeError,
    make_error,
    translate_exception,
)

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


class NodeEvaluator:
    """The evaluation pipeline of one node.

    ``TriggerNode.eval`` and ``TriggerNode.evalImplementation`` delegate here.
    Subclasses that override ``evalImplementation`` (``union``, ``unknown``,
    the audit nodes) keep working: :meth:`evaluate` always calls the node's own
    ``evalImplementation``, and only the base one comes back to
    :meth:`run_base_implementation`.
    """

    def __init__(self, node: "TriggerNode") -> None:
        self.node = node

    # -- the public pipeline -------------------------------------------------

    def evaluate(self) -> Any:
        node = self.node
        scene = getattr(node, "scene", None)
        if scene is not None and getattr(scene, "_bulk_loading", False):
            # A node constructed mid-load has no file path or column config
            # yet, so a constructor-time eval would compute from empty inputs
            # and be recomputed anyway once deserialization finishes. Leave it
            # dirty; doEvalOutputs runs the single post-load pass.
            return node.value
        if node._evaluating:
            # A sibling branch pushed into this node while it was still
            # computing. The computation in progress will commit the complete
            # result and push again; recomputing here only repeats work.
            return node.value

        coordinator = getattr(scene, "evaluator", None)
        if coordinator is not None:
            coordinator.flush_now()  # a pending edge edit is newer than us

        if not node.isDirty() and not node.isInvalid():
            logger.debug(" _> returning cached {} value:", node.__class__.__name__)
            return node.value

        node.set_changes_pending(False)
        node._evaluating = True
        if scene is not None:
            scene._eval_depth = getattr(scene, "_eval_depth", 0) + 1
        try:
            self._report_progress(finished=False)
            return node.evalImplementation()
        except Exception as exc:  # noqa: BLE001 - every failure ends in fail()
            # A ValueError is an expected, user-visible failure: its consumers
            # must recompute. Anything else is a bug worth a traceback.
            expected = isinstance(exc, ValueError)
            self.fail(
                lambda exc=exc: translate_exception(exc, node=node, phase="live"),
                descendants=expected,
                refresh=False,
            )
            if not expected:
                dumpException(exc)
            return None
        finally:
            self._settle(scene)

    def run_base_implementation(self) -> Any:
        """Collect inputs, run ``processInputs`` and commit or fail."""
        node = self.node
        input_values = []
        for i in range(len(node.inputs)):
            input_node = node.getInput(i)
            if not input_node:
                if i in node.optional_inputs:
                    input_values.append(None)
                    continue
                return self.fail(
                    lambda i=i: make_error(
                        "TD-RUN-005",
                        ErrorContext.from_node(node, "live"),
                        input_number=i + 1,
                    )
                )

            val = input_node.eval()
            if val is None:
                return self.fail(
                    lambda input_node=input_node: self._upstream_failed(input_node)
                )

            input_values.append(val)

        result = node.processInputs(input_values)
        if result is None:
            return self.fail(self._invalid_operation, only_if_unset=True)
        return self.succeed(result)

    # -- state transitions -------------------------------------------------

    def fail(
        self,
        build_error: Callable[[], NodeError],
        *,
        only_if_unset: bool = False,
        descendants: bool = True,
        refresh: bool = True,
    ) -> None:
        """The one failure transition.

        Mark the node invalid, dirty what consumes it, record the error and
        refresh the open dock. ``only_if_unset`` keeps an error that
        ``processInputs`` already set; ``descendants`` and ``refresh`` are
        off only for an unexpected exception, which has always left both alone.
        """
        node = self.node
        node.markInvalid()
        if descendants:
            node.markDescendantsDirty()
        if not only_if_unset or node.current_error is None:
            node.set_error(build_error(), "live")
        if refresh:
            node._refresh_selected_node_config()

    def succeed(self, result: Any) -> Any:
        node = self.node
        node.value = result
        node.markInvalid(False)
        node.markDirty(False)
        node.clear_error("live")
        node.evalChildren()
        node._refresh_selected_node_config()
        return node.value

    def invalidate(self, evaluate: bool = True) -> None:
        """The one invalidation: dirty this node and its consumers.

        An edge change only invalidates (the package follows it with an input
        notification, which does the single evaluation); an input change
        evaluates as well.
        """
        node = self.node
        node.markDirty()
        node.markDescendantsDirty()
        if evaluate:
            node.eval()

    def on_edge_connection_changed(self, new_edge) -> None:
        # A connection changes the consumer's inputs, not the producer's value.
        # On removal both sockets are already cleared, so the input
        # notification does the consumer work and the producer stays untouched.
        node = self.node
        node.clear_error("run")
        end_socket = getattr(new_edge, "end_socket", None)
        if end_socket is None or node is not getattr(end_socket, "node", None):
            return
        self.invalidate(evaluate=False)

    def on_input_changed(self, socket=None) -> None:
        node = self.node
        content = getattr(node, "content", None)
        if getattr(content, "_suspend_node_evaluation", False):
            return

        node.clear_error("run")
        coordinator = getattr(node.scene, "evaluator", None)
        if coordinator is not None:
            # Edge notifications are deferred so drag-end, split and reroute
            # loops coalesce in one event turn. Content edits in a small scene
            # use the same ordered path (one notify per compute, cycle report).
            # In a large scene the topological pass costs more than the push
            # path, so keep the guard + push fallback measured in step 5.
            small_scene = len(getattr(node.scene, "nodes", ())) <= 32
            if socket is not None or small_scene:
                coordinator.request_evaluation(node, defer=socket is not None)
                return
        self.invalidate(evaluate=True)

    # -- error builders ----------------------------------------------------

    def _upstream_failed(self, input_node: Any) -> NodeError:
        upstream = ErrorContext.from_node(input_node, "live")
        return make_error(
            "TD-RUN-003",
            ErrorContext.from_node(self.node, "live"),
            culprit_label=upstream.node_label,
            culprit_node_id=getattr(input_node, "id", None),
            culprit_node_title=upstream.node_label,
        )

    def _invalid_operation(self) -> NodeError:
        message = self.node._node_tooltip() or "Invalid operation"
        return make_error(
            "TD-SYS-001",
            ErrorContext.from_node(self.node, "live"),
            message=message,
        )

    # -- progress and notification ------------------------------------------

    def _report_progress(self, finished: bool) -> None:
        """Notify the active progress dialog, if any (helpers/eval_progress.py).

        Called before and after a real recompute only - a cache hit returns
        before this - so the dialog can name the node about to run and repaint
        before a slow step blocks the thread. A listener must not break eval.
        """
        try:
            scene = getattr(self.node, "scene", None)
            callback = (
                getattr(scene, "_eval_progress_cb", None) if scene is not None else None
            )
            if callable(callback):
                callback(self.node, finished)
        except Exception:  # noqa: BLE001 - UI listener must not break eval
            logger.exception("Evaluation progress callback failed")

    def _settle(self, scene: Optional[Any]) -> None:
        node = self.node
        # Clear the guard and depth before notifying listeners: a listener
        # that calls eval() must see a settled node, not a reentrant one.
        node._evaluating = False
        if scene is not None:
            scene._eval_depth = max(0, getattr(scene, "_eval_depth", 1) - 1)
        self._report_progress(finished=True)
        # Scene-level notification so preview surfaces can follow a real
        # recompute; cached evaluations return before this. ``Scene`` is not a
        # QObject, so TriggerScene fans this out to its own listeners.
        try:
            notify = getattr(scene, "notifyNodeEvaluated", None)
            if callable(notify):
                notify(node)
        except Exception:  # noqa: BLE001 - UI listener must not break eval
            logger.exception("Node evaluated listener failed")
        if scene is not None and getattr(scene, "_eval_depth", 0) == 0:
            coordinator = getattr(scene, "evaluator", None)
            if coordinator is not None:
                coordinator.flush_now()
