"""Scene history wired up to the Qt undo timeline.

:class:`TriggerSceneHistory` is a drop-in replacement for
:class:`nodeeditor.node_scene.SceneHistory` that keeps the same public
surface - ``storeHistory``, ``undo``, ``redo``, ``canUndo``, ``canRedo``, the
listener lists, ``is_restoring_history`` - so every existing call site keeps
working, but delegates the timeline to an
:class:`~trigger_designer.qt.undo.controller.UndoController`.

That buys three things over the list-of-snapshots it replaces:

* a real undo depth (200, not 32) and Qt-managed redo truncation,
* the Edit menu can show *what* will be undone,
* a fine grained command can sit on the timeline next to a snapshot command
  without either knowing about the other.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from nodeeditor.node_scene_history import SceneHistory

from trigger_designer.qt.undo.commands import SceneSnapshotCommand
from trigger_designer.qt.undo.controller import DEFAULT_UNDO_LIMIT, UndoController


class TriggerSceneHistory(SceneHistory):
    """Undo history for a :class:`~trigger_designer.qt.performance_scene.TriggerScene`."""

    def __init__(
        self,
        scene: Any,
        history_limit: Optional[int] = DEFAULT_UNDO_LIMIT,
    ) -> None:
        # SceneHistory.__init__ calls clear(), which needs self.controller to
        # already exist.
        self.controller = UndoController(self, limit=history_limit)
        self._baseline: Optional[dict] = None
        super().__init__(scene, history_limit=history_limit)

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------

    def clear(self) -> None:
        controller = getattr(self, "controller", None)
        if controller is not None:
            controller.clear()
        self._baseline = None
        self.undo_selection_has_changed = False

    def storeHistory(
        self,
        desc: str,
        setModified: bool = False,
        data: dict = None,
        callback: Optional[Callable[[], None]] = None,
        merge_key: Optional[str] = None,
        merge: Optional[
            Callable[[Optional[dict], Optional[dict]], Optional[dict]]
        ] = None,
    ) -> bool:
        """Record the current scene state as one undo step.

        Called *after* a change has been made, so the inverse is the
        previously recorded stamp. Callers that want a cheaper, more precise
        inverse should push a
        :class:`~trigger_designer.qt.undo.commands.PropertyChangeCommand`
        instead.

        :param merge_key: group consecutive stores under one key, so a burst
            of related edits becomes a single undo step.
        :param merge: combines the existing payload with the new one when a
            merge happens; see
            :func:`~trigger_designer.qt.undo.commands.keep_old_side`.
        :return: ``True`` if a new entry was pushed.
        """
        if self.is_restoring_history:
            return False

        if setModified:
            self.scene.has_been_modified = True

        stamp = self.createHistoryStamp(desc, data=data, merge_key=merge_key)

        if self.controller.coalesce_into_top(stamp, merge):
            self._fire_stored()
            return False

        if self._baseline is None:
            # The first stamp is the *baseline*: the state the document was
            # opened or created in. It is not itself an undo step, matching
            # the old `canUndo() == history_current_step > 0` semantics - you
            # cannot undo your way past the file you loaded. QUndoStack would
            # happily make it undoable, so it is held outside the stack.
            self._baseline = stamp
            self._fire_stored()
            return True

        # The stamp matching the current on-screen state becomes this
        # command's undo target. It has to be read *before* the push, since
        # pushing after an undo discards the redo tail.
        previous_stamp = self.controller.current_snapshot() or self._baseline

        self.controller.push(SceneSnapshotCommand(self, previous_stamp, stamp, desc))
        self._fire_stored()
        return True

    def _fire_stored(self) -> None:
        for cb in self._history_modified_listeners:
            cb()
        for cb in self._history_stored_listeners:
            cb()

    def _apply_stamp(self, stamp: dict, *, is_undo: bool) -> None:
        """Restore one stamp. Called by :class:`SceneSnapshotCommand`."""
        with self.restoring(is_undo=is_undo):
            self.restoreHistoryStamp(stamp)
            self._dispatch_stamp_data(stamp)

    def replace_scene(self, data: dict, text: str = "External Edit") -> bool:
        """Replace the whole scene with ``data`` as ONE undo step.

        The live state, unsaved GUI edits included, is the step's undo target,
        so undo returns to exactly what the user had before the file changed.

        :return: ``True`` if the step was recorded; ``False``, with nothing
            changed, while a restore is already running.
        :raises RuntimeError: if the new state cannot be applied. The live
            scene is put back and no step is recorded.
        """
        import copy

        from loguru import logger as global_logger

        if self.is_restoring_history:
            return False

        before = self.createHistoryStamp(text)  # the live state, unsaved edits too
        after = {
            "desc": text,
            "merge_key": None,
            "snapshot": copy.deepcopy(data),
            "selection": self.captureCurrentSelection(),
        }
        try:
            # Blocks "Selection Changed" stamps while the scene is rebuilt.
            with self.restoring(is_undo=False):
                # scene.deserialize reuses nodes by id.
                self.restoreHistoryStamp(after)
        except Exception as exc:
            global_logger.exception("External edit could not be applied: {}", exc)
            try:
                self._apply_stamp(before, is_undo=True)
                # The Config Dock may still show widgets the failed restore touched.
                for callback in list(self._history_restored_listeners):
                    callback()
            except Exception as rollback_exc:  # noqa: BLE001 - best effort, logged
                global_logger.exception(
                    "Could not restore the scene after a failed external edit: {}",
                    rollback_exc,
                )
            raise RuntimeError("External edit could not be applied") from exc

        # After the with-block: push() refuses while restoring. The command is
        # seeded, so the redo() that push() performs is a no-op.
        pushed = self.controller.push(SceneSnapshotCommand(self, before, after, text))
        self._fire_stored()
        # Includes TriggerSubWindow.onHistoryRestored: it force-rebuilds the
        # Config Dock and re-evaluates.
        for callback in list(self._history_restored_listeners):
            callback()
        return pushed

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def undo(self) -> bool:
        return self.controller.undo()

    def redo(self) -> bool:
        return self.controller.redo()

    def canUndo(self) -> bool:
        return self.controller.can_undo()

    def canRedo(self) -> bool:
        return self.controller.can_redo()

    def currentText(self) -> str:
        """Description of the step the next undo would revert."""
        return self.controller.undo_text()

    def nextText(self) -> str:
        """Description of the step the next redo would reapply."""
        return self.controller.redo_text()

    # ------------------------------------------------------------------
    # Convenience for node content
    # ------------------------------------------------------------------

    def push_edit(self, edit: Any, *, modified: bool = False) -> bool:
        """Record a fine grained command on the timeline.

        :param modified: flag the document dirty and refresh the listeners.
            Snapshots do that through :meth:`storeHistory`; a command whose
            change lives outside the node widgets has to say so itself.
        """
        pushed = self.controller.push(edit)
        if pushed and modified:
            self.mark_modified()
        return pushed

    def mark_modified(self) -> None:
        """Flag the document dirty without recording a snapshot."""
        self.scene.has_been_modified = True
        self._fire_stored()
