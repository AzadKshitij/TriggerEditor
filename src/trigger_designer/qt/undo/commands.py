"""Undo commands.

Every entry on the timeline is one of these. Two families:

* **Fine grained** - :class:`PropertyChangeCommand` and
  :class:`ListStructureCommand` know how to put a single node's settings back
  and how to refresh that node's widgets, without deserializing the scene.
* **Snapshot** - :class:`SceneSnapshotCommand` wraps a whole-scene capture for
  operations that have no fine grained inverse yet.

Both are :class:`~qtpy.QtGui.QUndoCommand` subclasses, so the timeline,
traversal and labels come from Qt rather than hand-rolled bookkeeping.
"""

from __future__ import annotations

import copy
from collections.abc import MutableMapping
from typing import Any, Callable, Iterable, Optional, Sequence

from loguru import logger as global_logger
from qtpy.QtGui import QUndoCommand

from trigger_designer.qt.undo.protocol import sync_from_model


def _deepcopy(value: Any) -> Any:
    """Snapshot a value defensively.

    Handed-in state is often the live object (a node's ``changes`` dict is the
    real one, not a copy). Copying at construction is what stops a later
    mutation from rewriting history that has already been recorded.
    """
    try:
        return copy.deepcopy(value)
    except Exception:
        return value


def keep_old_side(
    existing: Optional[dict],
    new: Optional[dict],
) -> Optional[dict]:
    """Merge payloads for a coalesced store, preserving the original "before".

    A burst of keystrokes must undo back to where the burst *started*, not to
    the previous keystroke. So when several stores collapse into one entry we
    keep the first entry's ``old*`` keys and take the newest everything else.

    :return: the payload to store.
    """
    if not isinstance(existing, dict) or not isinstance(new, dict):
        return new
    merged = dict(new)
    for key, value in existing.items():
        if key.startswith("old"):
            merged[key] = value
    return merged


def set_in(target: Any, path: Sequence[str], value: Any) -> None:
    """Assign ``value`` at a dotted ``path`` on ``target``.

    The container decides how a segment resolves, so a path may cross from an
    attribute into dict keys without the caller special-casing it::

        ("settings", "dtype")          -> content.settings["dtype"] = value
        ("rows",)                      -> content.rows = value
        ("changes", "rename_mapping")  -> content.changes["rename_mapping"] = value

    .. note::

       This runs inside ``redo()``, which :class:`~qtpy.QtGui.QUndoStack`
       calls from C++ during ``push``. A command's apply must therefore be
       idempotent and must not raise.
    """
    if not path:
        raise ValueError("path must name at least one attribute")
    head, *rest = path

    if isinstance(target, MutableMapping):
        if not rest:
            target[head] = value
            return
        set_in(target[head], rest, value)
        return

    if not rest:
        setattr(target, head, value)
        return
    set_in(getattr(target, head), rest, value)


def get_in(target: Any, path: Sequence[str], default: Any = None) -> Any:
    """Read the value at a dotted ``path`` on ``target``. See :func:`set_in`."""
    if not path:
        return target
    head, *rest = path
    try:
        child = (
            target[head]
            if isinstance(target, MutableMapping)
            else getattr(target, head)
        )
    except (AttributeError, KeyError, TypeError):
        return default
    if child is None:
        return default
    return get_in(child, rest, default)


class UndoableEdit(QUndoCommand):
    """Base class for every timeline entry.

    Adds the two things nodes need and Qt does not give us: a stable
    ``merge_key`` so a burst of related edits collapses into one undo step,
    and the guarantee that captured state is detached from the live model.

    .. note::

       :class:`~qtpy.QtGui.QUndoStack` calls ``redo()`` on a command as it is
       pushed. Commands here are therefore written to be idempotent, and
       ``undo``/``redo`` never let an exception escape into Qt's C++ frame -
       an escaping exception there aborts the process rather than raising.

       Merging deliberately does **not** go through :meth:`mergeWith`. When Qt
       merges it ``delete``s the command it was handed, and deleting a
       Python-owned ``QUndoCommand`` from C++ leaves a dangling wrapper that
       crashes the interpreter when collected. :class:`UndoController` folds
       commands through :meth:`can_merge_with` / :meth:`absorb` *before*
       pushing, so Qt never owns a merge.
    """

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self._merge_key: Optional[str] = None

    @property
    def merge_key(self) -> Optional[str]:
        """Grouping token, or ``None`` when this edit never merges."""
        return self._merge_key

    def id(self) -> int:
        """Always ``-1``, which switches Qt's own merging off.

        See the class note on why. Folding is done by
        :class:`~trigger_designer.qt.undo.controller.UndoController`.
        """
        return -1

    def can_merge_with(self, other: Any) -> bool:
        """Whether ``other`` continues this edit's burst."""
        if self._merge_key is None:
            return False
        if not isinstance(other, UndoableEdit):
            return False
        return other.merge_key == self._merge_key

    def absorb(self, other: Any) -> bool:
        """Fold ``other`` in, keeping this edit's *old* value.

        That is the whole point of merging: a burst of keystrokes must undo
        back to where the burst started, not to the previous keystroke.
        """
        return False

    def _guard(self, action: Callable[[], None]) -> None:
        """Log a failed apply instead of letting it escape into Qt.

        Losing one history step is recoverable; an exception unwinding
        through ``QUndoStack`` takes the whole application with it.
        """
        try:
            action()
        except Exception as exc:
            global_logger.exception(
                f"Undo/redo failed while applying {self.text()!r}: {exc}"
            )


class _ContentEdit(UndoableEdit):
    """Shared restore behaviour for edits that touch one node's settings."""

    def __init__(self, text: str, node: Any) -> None:
        super().__init__(text)
        self.node = node

    @property
    def content(self) -> Any:
        return getattr(self.node, "content", None)

    def _restore(self, value: Any, *, rebuild: bool) -> None:
        """Write ``value`` into the model, then re-project it onto the widgets."""
        content = self.content
        if content is None:
            return
        try:
            self._apply(content, value)
        finally:
            sync_from_model(content, rebuild=rebuild)

    def _apply(self, content: Any, value: Any) -> None:  # pragma: no cover
        raise NotImplementedError

    def _merge_target_check(self, other: Any) -> bool:
        """Shared guard: merging only makes sense within one node and one path."""
        return (
            isinstance(other, type(self))
            and self._merge_key is not None
            and other.merge_key == self._merge_key
            and self.path == other.path
            and self.node is other.node
        )


class PropertyChangeCommand(_ContentEdit):
    """One setting on one node changed.

    The workhorse: renaming a field, toggling a column, picking a dtype,
    changing a sort key. Captures only the affected value rather than the
    whole scene, and re-projects it onto the node's widgets on restore.

    :param path: dotted path on the *content* widget. See :func:`set_in`.
    :param apply: optional custom writer called as ``apply(content, value)``.
        Defaults to assigning ``value`` at ``path``.
    """

    def __init__(
        self,
        node: Any,
        path: Sequence[str],
        old: Any,
        new: Any,
        text: str,
        *,
        apply: Optional[Callable[[Any, Any], None]] = None,
        rebuild: bool = False,
        merge_key: Optional[str] = None,
    ) -> None:
        super().__init__(text, node)
        self.path = tuple(path)
        self.old = _deepcopy(old)
        self.new = _deepcopy(new)
        self._apply_fn = apply
        self._rebuild = rebuild
        self._merge_key = merge_key

    def _apply(self, content: Any, value: Any) -> None:
        if self._apply_fn is not None:
            self._apply_fn(content, value)
            return
        set_in(content, self.path, _deepcopy(value))

    def undo(self) -> None:
        self._guard(lambda: self._restore(self.old, rebuild=self._rebuild))

    def redo(self) -> None:
        self._guard(lambda: self._restore(self.new, rebuild=self._rebuild))

    def can_merge_with(self, other: Any) -> bool:
        return self._merge_target_check(other)

    def absorb(self, other: Any) -> bool:
        if not self._merge_target_check(other):
            return False
        self.new = other.new
        self._rebuild = self._rebuild or other._rebuild
        self.setText(other.text())
        return True


class ListStructureCommand(_ContentEdit):
    """A node's *collection* of settings changed shape.

    Distinct from :class:`PropertyChangeCommand` because the number of widgets
    changes: adding or removing a formula section means the Config Dock gains
    or loses an editor, so a value-only restore would leave orphaned widgets
    behind. This always rebuilds structure.
    """

    def __init__(
        self,
        node: Any,
        path: Sequence[str],
        old: Iterable[Any],
        new: Iterable[Any],
        text: str,
        *,
        rebuild: str = "_rebuild_widgets",
        merge_key: Optional[str] = None,
    ) -> None:
        super().__init__(text, node)
        self.path = tuple(path)
        self.old = list(_deepcopy(list(old)))
        self.new = list(_deepcopy(list(new)))
        #: Name of the content method that recreates the widgets. Recorded for
        #: introspection and error messages; the restore path resolves it
        #: dynamically through :func:`sync_from_model`.
        self.rebuild_method = rebuild
        self._merge_key = merge_key

    def _apply(self, content: Any, value: Any) -> None:
        set_in(content, self.path, list(_deepcopy(list(value))))

    def undo(self) -> None:
        self._guard(lambda: self._restore(self.old, rebuild=True))

    def redo(self) -> None:
        self._guard(lambda: self._restore(self.new, rebuild=True))

    def can_merge_with(self, other: Any) -> bool:
        return self._merge_target_check(other)

    def absorb(self, other: Any) -> bool:
        if not self._merge_target_check(other):
            return False
        self.new = other.new
        self.setText(other.text())
        return True


class SceneSnapshotCommand(UndoableEdit):
    """Whole-scene capture, for operations with no fine grained inverse.

    Holds both the stamp captured *before* the change and the one captured
    after, which is what lets it invert itself. That mirrors the stepping
    semantics the old list-based history had, but each entry is now
    self-contained: a command can be applied without consulting its
    neighbours.

    Redo is seeded off. The scene is already in the "after" state when the
    command is created, so the ``redo()`` that ``QUndoStack.push`` performs is
    a no-op - and guarding makes the entry idempotent however it is reached.
    """

    def __init__(
        self,
        history: Any,
        previous_stamp: Optional[dict],
        current_stamp: dict,
        text: Optional[str] = None,
    ) -> None:
        super().__init__(text if text is not None else current_stamp.get("desc", ""))
        self.history = history
        self.previous_stamp = previous_stamp
        self.current_stamp = current_stamp
        self._merge_key = current_stamp.get("merge_key")
        self._seeded = True

    def _apply(self, stamp: Optional[dict], *, is_undo: bool) -> None:
        if stamp is None:
            # Nothing preceded this edit, so undoing it is a no-op rather than
            # an error.
            return
        self.history._apply_stamp(stamp, is_undo=is_undo)

    def undo(self) -> None:
        self._seeded = False
        self._guard(lambda: self._apply(self.previous_stamp, is_undo=True))

    def redo(self) -> None:
        if self._seeded:
            return
        self._guard(lambda: self._apply(self.current_stamp, is_undo=False))

    def can_merge_with(self, other: Any) -> bool:
        return False

    def absorb(self, other: Any) -> bool:
        return False

    def coalesce(
        self,
        stamp: dict,
        merge: Optional[
            Callable[[Optional[dict], Optional[dict]], Optional[dict]]
        ] = None,
    ) -> None:
        """Fold a newer store of the same burst into this entry.

        Mutating the tip command *is* the fold - unlike a list there is no
        "replace the last element" to perform, and the tip is by definition
        the entry the user has not stepped back from.
        """
        if merge is not None:
            existing = self.current_stamp.get("data")
            incoming = stamp.get("data")
            try:
                stamp = dict(stamp)
                stamp["data"] = merge(existing, incoming)
            except Exception as exc:
                global_logger.error(f"Failed to merge history payloads: {exc}")
        self.current_stamp = stamp
        self.setText(stamp.get("desc", self.text()))
