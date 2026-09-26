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

    @property
    def history_stack(self) -> list:
        """Commands on the timeline. Read-only; kept for compatibility."""
        return [self.controller.stack.command(i) for i in range(self.controller.count)]

    @property
    def baseline_stamp(self) -> Optional[dict]:
        """The state the document was opened in. Not an undo step."""
        return self._baseline

    @property
    def history_current_step(self) -> int:
        """Index of the currently applied command, or ``-1`` at the bottom.

        Matches the old list-based meaning so the name still reads true, even
        though the controller underneath counts applied commands instead.
        """
        return self.controller.index - 1

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

    def push_edit(self, edit: Any) -> bool:
        """Record a fine grained command on the timeline."""
        return self.controller.push(edit)

    def macro(self, text: str):
        """``with history.macro("Renamed Field"): ...``"""
        return self.controller.macro(text)
