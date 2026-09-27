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


class _EmitCounter:
    def __init__(self) -> None:
        self.count = 0

    def emit(self, *_args) -> None:
        self.count += 1


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


def _cleansing_content():
    from trigger_designer.qt.widgets.nodes.Preparation.cleansing import (
        CleansingContent,
    )

    content = CleansingContent.__new__(CleansingContent)
    content.fields_list = _checklist(["a", "b", "c"])
    content.field_checkboxes = content.fields_list.checkboxes
    # NB: signals connected to bound methods of a __new__-created (C++-
    # uninitialized) instance are silently never delivered, so invoke the
    # unbound handler explicitly - closest to the production wiring, where
    # `changed` is connected to this same method on a live object.
    content.fields_list.changed.connect(
        lambda _cols: CleansingContent.on_field_selection_changed(content)
    )
    content.selected_fields = []
    content._field_selection_initialized = False
    content.incom_data = None
    content.evaluate = _EmitCounter()
    return content


def test_cleansing_select_all_evaluates_once() -> None:
    content = _cleansing_content()
    content.select_all_fields()
    assert content.selected_fields == ["a", "b", "c"]
    assert content.evaluate.count == 1


def test_cleansing_select_none_evaluates_once() -> None:
    content = _cleansing_content()
    content.select_all_fields()
    content.evaluate.count = 0
    content.select_no_fields()
    assert content.selected_fields == []
    assert content.evaluate.count == 1


def _normalize_content():
    from trigger_designer.qt.widgets.nodes.Preparation.normalize_columns import (
        NormalizeColumnsContent,
    )

    content = NormalizeColumnsContent.__new__(NormalizeColumnsContent)
    content.columns_list = _checklist(["a", "b", "c"])
    content.field_checkboxes = content.columns_list.checkboxes
    # See _cleansing_content: invoke the unbound handler explicitly.
    content.columns_list.changed.connect(
        lambda _cols: NormalizeColumnsContent.on_columns_changed(content)
    )
    content.selected_columns = []
    content._field_selection_initialized = False
    content.incom_data = None
    content.evaluate = _EmitCounter()
    return content


def test_normalize_select_all_evaluates_once() -> None:
    content = _normalize_content()
    content.select_all_columns()
    assert content.selected_columns == ["a", "b", "c"]
    assert content.evaluate.count == 1
