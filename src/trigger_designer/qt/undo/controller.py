"""The undo timeline.

A :class:`~qtpy.QtGui.QUndoStack` per scene, wrapped so the rest of the app
never touches Qt's API directly. Owns the macro scope used to group a
compound operation (add a section *and* set its target column) into a single
undo step.

.. note::

   :class:`~qtpy.QtGui.QUndoStack` reports ``index()`` as the *number of
   applied commands*, not a position that can go negative: an empty stack and
   a fully-undone stack both report ``0``. So command ``i`` is applied exactly
   when ``i < index()``, and the newest command is ``count() - 1``. Every
   accessor here is written against that, because getting it wrong silently
   reports the wrong "current" entry rather than raising.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional

from qtpy.QtGui import QUndoStack

from trigger_designer.qt.undo.commands import SceneSnapshotCommand, UndoableEdit

#: How many undo steps to retain. The old list-based history capped at 32,
#: which a few minutes of typing could exhaust; 200 is generous for an editing
#: session while still bounding memory.
DEFAULT_UNDO_LIMIT = 200

#: Nesting depth beyond which macros are refused, to catch a begin without a
#: matching end rather than silently swallowing every later undo.
_MAX_MACRO_DEPTH = 8


class UndoController:
    """Owns the :class:`QUndoStack` for one scene's history."""

    def __init__(self, history: Any, limit: Optional[int] = DEFAULT_UNDO_LIMIT) -> None:
        self.history = history
        self.stack = QUndoStack()
        self.stack.setUndoLimit(-1 if limit is None else limit)
        self._macro_depth = 0

    # ------------------------------------------------------------------
    # Pushing
    # ------------------------------------------------------------------

    def push(self, edit: Any) -> bool:
        """Record ``edit`` on the timeline.

        :class:`QUndoStack` calls the command's ``redo()`` as it is pushed, so
        commands must be idempotent - and a caller that already applied the
        change does not need to.

        A mergeable edit arriving while the timeline is at its tip is folded
        into the tip rather than pushed, because Qt's own merge path deletes
        the command it is handed, which is unsafe for a Python subclass.

        :return: ``False`` when a restore is in progress (recording the change
            we are undoing would strand the user) or when ``edit`` was folded
            into the tip.
        """
        if getattr(self.history, "is_restoring_history", False):
            return False

        if self.is_at_tip():
            tip = self.tip_command()
            if (
                isinstance(tip, UndoableEdit)
                and isinstance(edit, UndoableEdit)
                and tip.can_merge_with(edit)
                and tip.absorb(edit)
            ):
                return False

        self.stack.push(edit)
        return True

    def top_command(self) -> Optional[Any]:
        """The applied entry an undo would revert, or ``None`` at the bottom."""
        index = self.stack.index() - 1
        if index < 0:
            return None
        return self.stack.command(index)

    def tip_command(self) -> Optional[Any]:
        """The newest entry on the stack, whether applied or not."""
        if self.stack.count() == 0:
            return None
        return self.stack.command(self.stack.count() - 1)

    def is_at_tip(self) -> bool:
        """``True`` when nothing is pending undo, i.e. the redo tail is empty.

        Coalescing is only legal here. After an undo the user is looking at a
        redo tail, and folding into it would rewrite steps they are about to
        redo.
        """
        return self.stack.index() == self.stack.count()

    def current_snapshot(self) -> Optional[dict]:
        """The scene stamp matching the state on screen right now.

        Walks back from the current position to the newest snapshot command
        still applied. Property commands above it are already reflected in the
        live scene, and the next snapshot will capture them, so they need no
        separate handling here.
        """
        applied = self.stack.index()
        for i in range(min(applied, self.stack.count()) - 1, -1, -1):
            command = self.stack.command(i)
            if isinstance(command, SceneSnapshotCommand):
                return command.current_stamp

        # Nothing applied: the scene sits at the bottom of the timeline.
        if self.stack.count():
            first = self.stack.command(0)
            if isinstance(first, SceneSnapshotCommand):
                return first.previous_stamp
        return None

    def coalesce_into_top(
        self,
        stamp: dict,
        merge: Optional[
            Callable[[Optional[dict], Optional[dict]], Optional[dict]]
        ] = None,
    ) -> bool:
        """Fold a newer stamp into the tip entry instead of pushing a new one.

        Mutating the tip command *is* the fold - unlike a hand-rolled list
        there is no "replace the last element" to perform.
        """
        if not self.is_at_tip():
            return False
        tip = self.tip_command()
        if not isinstance(tip, SceneSnapshotCommand):
            return False
        key = stamp.get("merge_key")
        if key is None or tip.merge_key != key:
            return False
        tip.coalesce(stamp, merge)
        return True

    # ------------------------------------------------------------------
    # Macros
    # ------------------------------------------------------------------

    def begin_macro(self, text: str) -> bool:
        """Group everything up to :meth:`end_macro` into one undo step."""
        if self._macro_depth >= _MAX_MACRO_DEPTH:
            return False
        if self._macro_depth == 0:
            self.stack.beginMacro(text)
        self._macro_depth += 1
        return True

    def end_macro(self) -> None:
        if self._macro_depth == 0:
            return
        self._macro_depth -= 1
        if self._macro_depth == 0:
            self.stack.endMacro()

    @property
    def in_macro(self) -> bool:
        return self._macro_depth > 0

    @contextmanager
    def macro(self, text: str) -> Iterator[bool]:
        """``with controller.macro("Renamed Field"): ...``

        Yields ``False`` when the macro was refused, so the body can skip work
        that would otherwise be orphaned inside a macro that never closes.
        """
        started = self.begin_macro(text)
        try:
            yield started
        finally:
            if started:
                self.end_macro()

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def undo(self) -> bool:
        if not self.stack.canUndo():
            return False
        self.stack.undo()
        self._after_travel()
        return True

    def redo(self) -> bool:
        if not self.stack.canRedo():
            return False
        self.stack.redo()
        self._after_travel()
        return True

    def _after_travel(self) -> None:
        """Common bookkeeping after any undo/redo.

        Fired here rather than inside each command so fine grained commands,
        which never touch the scene snapshot, still notify the Edit menu and
        the Config Dock.
        """
        history = self.history
        history.scene.has_been_modified = True
        for callback in history._history_modified_listeners:
            callback()
        for callback in history._history_restored_listeners:
            callback()

    def can_undo(self) -> bool:
        return self.stack.canUndo()

    def can_redo(self) -> bool:
        return self.stack.canRedo()

    def undo_text(self) -> str:
        top = self.top_command()
        return top.text() if top is not None else ""

    def redo_text(self) -> str:
        nxt = self.stack.index()
        if nxt >= self.stack.count():
            return ""
        return self.stack.command(nxt).text()

    def clear(self) -> None:
        # An unbalanced macro would otherwise leave the stack wedged.
        self._macro_depth = 0
        self.stack.clear()

    @property
    def count(self) -> int:
        return self.stack.count()

    @property
    def index(self) -> int:
        """Number of currently applied commands. See the module note."""
        return self.stack.index()
