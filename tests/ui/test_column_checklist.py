#!/usr/bin/env python3
"""Bulk-select tests: All/None must cost exactly one evaluation.

Regression: looping over raw checklist checkboxes fires `changed` per box,
and each handler run re-evaluates the whole downstream workflow, so one
"Select all" click on an N-column frame ran N+1 full recomputes.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from qtpy.QtWidgets import QApplication

APP = QApplication.instance() or QApplication([])


def _checklist(columns):
    from trigger_designer.qt.widgets.common.config_widgets import ColumnChecklist

    return ColumnChecklist(columns, [])


def test_set_all_checked_emits_changed_once() -> None:
    boxes = _checklist(["a", "b", "c", "d"])
    seen = []
    boxes.changed.connect(seen.append)
    boxes.set_all_checked(True)
    assert boxes.checked() == ["a", "b", "c", "d"]
    assert len(seen) == 1
    boxes.set_all_checked(False)
    assert boxes.checked() == []
    assert len(seen) == 2


def test_single_toggle_still_emits() -> None:
    boxes = _checklist(["a", "b"])
    seen = []
    boxes.changed.connect(seen.append)
    boxes.checkboxes["a"].setChecked(True)
    assert len(seen) == 1
