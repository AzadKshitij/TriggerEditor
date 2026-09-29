"""Progress feedback for long synchronous graph recomputes.

File load (``doEvalOutputs``) and a downstream cascade from a single edit
(``TriggerNode.onInputChanged``) both walk the graph via plain recursive
``eval()``/``evalImplementation()`` calls (see node_base.py) - there is no
worker thread and no point where the walk yields to the Qt event loop. This
module does not change that; it only makes the wait visible and keeps the
window painting while it happens, via the standard Qt idiom for a long
synchronous operation: a modal ``QProgressDialog`` whose ``setValue`` pumps
just enough of the event loop to repaint.

``TriggerNode.eval()`` reports through ``scene._eval_progress_cb`` every time
it actually recomputes (not on a cached hit), so the same hook drives both
call sites: :func:`eval_progress_dialog` just sizes the dialog to how many
nodes are about to recompute and tears the hook down afterwards.
"""

from __future__ import annotations

from contextlib import contextmanager

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QProgressDialog, QWidget

#: Below this node count, a dialog would only flash and vanish - the
#: recompute finishes before ``setMinimumDuration`` would even show it.
PROGRESS_NODE_THRESHOLD = 8

#: Matches QProgressDialog's own default; a fast edit never shows the dialog.
PROGRESS_MINIMUM_DURATION_MS = 300


@contextmanager
def eval_progress_dialog(scene, parent: QWidget | None, total: int, title: str):
    """Show a modal progress dialog while up to ``total`` nodes recompute.

    No-op for small graphs/cascades (see ``PROGRESS_NODE_THRESHOLD``) so a
    normal edit never flashes a dialog. ``total`` is an estimate (the
    descendant count before the cascade runs); real ticks come from nodes
    that actually recompute, so the bar can finish short of ``total`` if an
    upstream error stops the cascade early - harmless, since the dialog just
    closes once the ``with`` block exits.
    """
    if scene is None or total < PROGRESS_NODE_THRESHOLD:
        yield
        return

    dialog = QProgressDialog(title, None, 0, total, parent)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setMinimumDuration(PROGRESS_MINIMUM_DURATION_MS)
    dialog.setCancelButton(None)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)

    progress = {"n": 0}

    def _tick() -> None:
        progress["n"] += 1
        dialog.setValue(min(progress["n"], total))

    previous_cb = getattr(scene, "_eval_progress_cb", None)
    scene._eval_progress_cb = _tick
    try:
        yield
    finally:
        scene._eval_progress_cb = previous_cb
        dialog.close()
        dialog.deleteLater()


def count_pending_recomputes(node) -> int:
    """``node`` plus every descendant reachable through its outputs.

    Mirrors what ``markDescendantsDirty()`` marks dirty, so it sizes the
    dialog to (approximately) the number of ``eval()`` calls the cascade
    from this node is about to trigger.
    """
    seen = {id(node)}
    stack = list(node.getChildrenNodes())
    count = 1
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        count += 1
        stack.extend(current.getChildrenNodes())
    return count
