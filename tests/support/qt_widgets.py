#!/usr/bin/env python3
"""Qt teardown helpers for tests that draw charts.

A chart window owns a matplotlib canvas. The suite's leak fixture
(``tests/conftest.py``) hides and deletes every top-level widget it finds in
one batch; releasing the chart window in its own pass first keeps teardown
deterministic and independent of the plotting library.

This lives beside the tests that need it rather than in ``tests/conftest.py``
so the workaround stays visible where it applies.
"""

from __future__ import annotations

from qtpy.QtCore import QCoreApplication, QEvent
from qtpy.QtWidgets import QApplication, QWidget


def dispose_plot_widget(widget: QWidget | None) -> None:
    """Delete one widget and its children, before the batch teardown runs."""
    if widget is None:
        return
    try:
        widget.hide()
        widget.deleteLater()
    except RuntimeError:
        # Already destroyed along with a parent.
        return
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()
