"""Shared protocol between the undo layer and node content widgets.

The Config Dock *is* the editor: selecting a node calls its
``create_layout()`` and deselecting destroys the widgets. That makes two
things mandatory for undo to behave.

* A restore has to be able to say "rebuild this node's widgets from its
  model" without going through selection - see :func:`sync_from_model`.
* A rebuild must not look like a user edit. Otherwise restoring state pushes
  a new history entry and the user can never undo past it. :func:`syncing`
  is the re-entrancy guard that makes that impossible.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Optional

#: Attribute holding the per-content re-entrancy depth for model -> widget
#: writes. Kept as a string constant so node code and the undo layer agree.
SYNC_DEPTH_ATTR = "_undo_sync_depth"

#: Attribute set while the Config Dock is building a node's layout, during
#: which signal-driven bookkeeping must stay silent.
SUSPEND_ATTR = "_suspend_input_tracking"


def is_syncing(target: Any) -> bool:
    """``True`` while widgets are being written from the model.

    Bindings must check this and return early: a widget signal fired by our
    own write-back is not a user edit.
    """
    content = content_of(target)
    if content is None:
        return False
    return int(getattr(content, SYNC_DEPTH_ATTR, 0) or 0) > 0


def content_of(target: Any) -> Optional[Any]:
    """Resolve ``target`` to a content widget.

    Accepts a node, a content widget, or ``None`` so callers can pass
    ``self`` from a content class and ``self.node`` from a node class
    interchangeably.
    """
    if target is None:
        return None
    # A content widget is its own content.
    if hasattr(target, "_sync_widgets_from_model"):
        return target
    return getattr(target, "content", None)


@contextmanager
def syncing(target: Any) -> Iterator[None]:
    """Mark a block as "model is driving the widgets".

    Nestable, so a node may rebuild its widgets and have those rebuilds
    re-enter :func:`sync_from_model` safely.
    """
    content = content_of(target)
    if content is None:
        yield
        return

    depth = int(getattr(content, SYNC_DEPTH_ATTR, 0) or 0)
    setattr(content, SYNC_DEPTH_ATTR, depth + 1)
    try:
        yield
    finally:
        setattr(content, SYNC_DEPTH_ATTR, max(0, depth))


def is_suspended(target: Any) -> bool:
    """``True`` while the Config Dock is (re)building this node's layout."""
    content = content_of(target)
    if content is None:
        return False
    return bool(getattr(content, SUSPEND_ATTR, False))


def sync_from_model(
    target: Any,
    *,
    rebuild: bool = False,
    evaluate: bool = True,
) -> bool:
    """Bring ``target``'s widgets back in line with its model.

    This is the single entry point commands use after mutating state, and the
    fix for the Config Dock desync: after an undo the same node is still
    selected, so ``ConfigDock.updateConfig`` short-circuits on its
    ``_current_key`` check and never rebuilds. Calling this directly ignores
    that check.

    :param rebuild: also recreate widget structure. Needed when the change
        altered the *number* of widgets (adding/removing a formula section,
        a join mapping row) rather than just their values.
    :param evaluate: re-run the node's evaluation so the graph reflects the
        restored settings.
    :return: ``True`` if a content widget was found and synced.
    """
    content = content_of(target)
    if content is None:
        return False

    # Guard the whole block so a _rebuild_widgets that rebuilds sub-widgets
    # cannot re-enter the bindings it just replaced.
    with syncing(content):
        if rebuild:
            rebuilder = getattr(content, "_rebuild_widgets", None)
            if callable(rebuilder):
                rebuilder()
        syncer = getattr(content, "_sync_widgets_from_model", None)
        if callable(syncer):
            syncer()

    history = getattr(content, "history", None)
    restoring = bool(getattr(history, "is_restoring_history", False))
    if evaluate and not restoring:
        request = getattr(content, "request_evaluation", None)
        signal = getattr(content, "evaluate", None)
        if callable(request):
            request()  # deferred until the dock is left
        elif signal is not None and hasattr(signal, "emit"):
            signal.emit()

    return True


def history_of(target: Any):
    """Return the scene history backing ``target``, or ``None``."""
    content = content_of(target)
    if content is not None:
        history = getattr(content, "history", None)
        if history is not None:
            return history
    node = getattr(target, "node", None)
    return getattr(getattr(node, "scene", None), "history", None)
