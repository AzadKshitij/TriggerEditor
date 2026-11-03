"""Edits reach the model at once; the node runs when the user leaves it.

A click in the Config Dock must repaint immediately, so the pipeline does not
run on every change. ``request_evaluation`` only marks the node's run as
pending (and shows the yellow "!" on the canvas); the dock flushes it through
``commit_pending_dock_edits`` when another node is selected, the canvas is
clicked, or the document is closed.
"""

from __future__ import annotations

from trigger_designer.qt.undo.protocol import is_syncing


class DeferredEvaluation:
    """Mixin for Config Dock content whose evaluation waits for the dock to close."""

    #: Set to False on a content class that must still evaluate on every edit.
    DEFER_EVALUATION = True

    _pending_evaluate = False
    _eval_generation = 0

    def request_evaluation(self) -> None:
        """Evaluate now, or mark the run pending when the class defers it."""
        if self.DEFER_EVALUATION:
            self._pending_evaluate = True
            self._show_changes_pending(True)
        else:
            self._pending_evaluate = False
            self.evaluate.emit()

    def _show_changes_pending(self, pending: bool) -> None:
        node = getattr(self, "node", None)
        setter = getattr(node, "set_changes_pending", None)
        if callable(setter):
            setter(pending)

    def _evaluate_pending(self) -> None:
        """Apply one deferred evaluation, if the node is in a safe state."""
        if not self._pending_evaluate:
            return
        if (
            is_syncing(self)
            or self.history.is_restoring_history
            or getattr(self, "_suspend_node_evaluation", False)
        ):
            return
        self._pending_evaluate = False
        self._show_changes_pending(False)
        self.evaluate.emit()

    def cancel_pending_evaluation(self) -> None:
        """Drop deferred work and invalidate any queued focus-out callback."""
        self._pending_evaluate = False
        self._eval_generation += 1
        self._show_changes_pending(False)

    def commit_pending_dock_edits(self, *, evaluate: bool = True) -> None:
        """Run the deferred evaluation when the dock is left.

        ``evaluate=False`` (Save, Run) keeps the pending run for later: the
        settings are already in the model, so nothing is lost by waiting.
        """
        if evaluate:
            self._evaluate_pending()
