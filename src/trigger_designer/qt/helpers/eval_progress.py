"""Progress feedback for long synchronous graph work (file load, recompute).

File load and a downstream cascade from a single edit both run on the GUI
thread with no point where the work yields to the Qt event loop. This module
does not change that; it makes the wait visible: a modal ``QProgressDialog``
that is shown *and painted* before the work starts, and re-pumped by
``TriggerNode.eval()`` around every node it recomputes.

``eval()`` calls ``scene._eval_progress_cb(node, finished)`` - once with
``finished=False`` just before a node computes (so the dialog can name it and
repaint before a slow step blocks the thread) and once with ``finished=True``
after it. A cache hit never reaches the hook.
"""

from __future__ import annotations

from contextlib import contextmanager

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QProgressDialog, QWidget

#: Below this node count, a cascade dialog would only flash and vanish.
PROGRESS_NODE_THRESHOLD = 8


def make_progress_dialog(
    parent: QWidget | None, title: str, total: int = 0
) -> QProgressDialog:
    """A modal dialog that is visible and painted before this returns.

    ``total == 0`` gives the busy (indeterminate) bar, for phases whose size
    is unknown such as reading and deserializing a file.
    """
    dialog = QProgressDialog(title, None, 0, total, parent)
    dialog.setWindowTitle("Please wait")
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setMinimumDuration(0)
    dialog.setCancelButton(None)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    dialog.setValue(0)
    dialog.show()
    # A native window's contents only draw after a second pass through the
    # event loop; one pass leaves a blank frame while the thread is blocked.
    QApplication.processEvents()
    dialog.repaint()
    QApplication.processEvents()
    return dialog


@contextmanager
def eval_progress_dialog(
    scene,
    parent: QWidget | None,
    total: int,
    title: str,
    dialog: QProgressDialog | None = None,
):
    """Drive a progress dialog while up to ``total`` nodes recompute.

    Pass ``dialog`` to reuse one opened earlier (file load opens it before
    parsing); otherwise a dialog is created, but only for cascades of at
    least ``PROGRESS_NODE_THRESHOLD`` nodes so a normal edit never flashes
    one. ``total`` is an estimate; an upstream error can end the cascade
    early, which is harmless - the dialog closes when the block exits.
    """
    if scene is None or (dialog is None and total < PROGRESS_NODE_THRESHOLD):
        yield
        return

    owned = dialog is None
    if dialog is None:
        dialog = make_progress_dialog(parent, title, total)
    else:
        dialog.setLabelText(title)
        dialog.setMaximum(total)
        dialog.setValue(0)
        QApplication.processEvents()

    done = {"n": 0}

    def _hook(node, finished: bool) -> None:
        if finished:
            done["n"] += 1
            dialog.setValue(min(done["n"], total))
        else:
            name = getattr(node, "title", None) or type(node).__name__
            dialog.setLabelText(f"{title}\n{name}")
            dialog.repaint()
            QApplication.processEvents()

    previous_cb = getattr(scene, "_eval_progress_cb", None)
    scene._eval_progress_cb = _hook
    try:
        yield
    finally:
        scene._eval_progress_cb = previous_cb
        if owned:
            dialog.close()
            dialog.deleteLater()


def count_pending_recomputes(node) -> int:
    """``node`` plus every descendant reachable through its outputs."""
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
