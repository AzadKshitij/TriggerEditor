#!/usr/bin/env python3
"""Select node move up/down buttons must reorder columns and stick."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
from qtpy.QtCore import QItemSelectionModel, Qt
from qtpy.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

APP = QApplication.instance() or QApplication([])


def _make_content(cols=("a", "b", "c", "d")):
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    cls = get_class_from_opcode(PreparationNodes.SELECT, NodeTypes.PREPARATION)
    node = cls(window.scene)
    window.scene.nodes.append(node)
    content = node.content
    content.incom_data = pl.DataFrame({c: [1, 2] for c in cols}).lazy()
    content.incoming_variable = "var_in"
    host = QWidget()
    content.create_layout(QVBoxLayout(host))
    return parent, window, content, host


def _table_order(content):
    return [row.text for row in content.table_data]


def _output_cols(content):
    return list(content.data.collect_schema().names())


def _select_proxy_row(content, proxy_row, clear=True):
    sel = content.table_view.selectionModel()
    if clear:
        sel.clear()
        content.table_view.clearSelection()
    index = content.proxy_model.index(proxy_row, 0)
    sel.select(
        index,
        QItemSelectionModel.SelectionFlag.Select
        | QItemSelectionModel.SelectionFlag.Rows,
    )
    content.table_view.setCurrentIndex(index)


def test_move_up_single_row_sticks():
    _parent, _window, content, _host = _make_content()
    assert _table_order(content) == ["a", "b", "c", "d"]
    _select_proxy_row(content, 2)  # 'c'
    content.table_widget.moveSelectedRow("up", content.table_view)
    APP.processEvents()
    assert _table_order(content) == ["a", "c", "b", "d"]
    assert content.changes["selected_columns"] == ["a", "c", "b", "d"]
    assert content.changes["column_order"] == ["a", "c", "b", "d"]
    assert [r[0] for r in content.table_widget.getData()] == ["a", "c", "b", "d"]
    assert _output_cols(content) == ["a", "c", "b", "d"]


def test_move_down_single_row_sticks():
    _parent, _window, content, _host = _make_content()
    _select_proxy_row(content, 1)  # 'b'
    content.table_widget.moveSelectedRow("down", content.table_view)
    APP.processEvents()
    assert _table_order(content) == ["a", "c", "b", "d"]
    assert _output_cols(content) == ["a", "c", "b", "d"]


def test_move_up_via_toolbar_button():
    _parent, _window, content, _host = _make_content()
    _select_proxy_row(content, 1)  # 'b'
    content.up_btn.click()
    APP.processEvents()
    assert _table_order(content) == ["b", "a", "c", "d"]
    assert _output_cols(content) == ["b", "a", "c", "d"]
    _select_proxy_row(content, 0)  # 'b' is now at 0
    content.down_btn.click()
    APP.processEvents()
    assert _table_order(content) == ["a", "b", "c", "d"]


def test_move_at_edges_is_noop():
    _parent, window, content, _host = _make_content()
    before = window.scene.history.controller.stack.count()
    _select_proxy_row(content, 0)
    content.table_widget.moveSelectedRow("up", content.table_view)
    APP.processEvents()
    assert _table_order(content) == ["a", "b", "c", "d"]
    _select_proxy_row(content, 3)
    content.table_widget.moveSelectedRow("down", content.table_view)
    APP.processEvents()
    assert _table_order(content) == ["a", "b", "c", "d"]
    # No-ops must not record history.
    assert window.scene.history.controller.stack.count() == before


def test_move_uses_highlight_when_current_missing():
    """Highlight-only selections (no current index) must still move."""
    _parent, _window, content, _host = _make_content()
    sel = content.table_view.selectionModel()
    sel.clear()
    # Highlight without setting a current index, like a drag-select.
    sel.select(
        content.proxy_model.index(2, 0),
        QItemSelectionModel.SelectionFlag.Select
        | QItemSelectionModel.SelectionFlag.Rows,
    )
    assert not content.table_view.selectionModel().currentIndex().isValid()
    content.table_widget.moveSelectedRow("up", content.table_view)
    APP.processEvents()
    assert _table_order(content) == ["a", "c", "b", "d"]


def test_move_preserves_unchecked_and_filters_output():
    _parent, _window, content, _host = _make_content()
    # Uncheck 'b'.
    assert content.table_widget.setData(
        content.table_widget.index(1, 0), 0, Qt.ItemDataRole.CheckStateRole
    )
    APP.processEvents()
    assert content.changes["selected_columns"] == ["a", "c", "d"]
    assert _output_cols(content) == ["a", "c", "d"]
    # Move 'c' (source row 2) above 'a'.
    _select_proxy_row(content, 2)
    content.table_widget.moveSelectedRow("up", content.table_view)
    APP.processEvents()
    content.table_widget.moveSelectedRow("up", content.table_view)
    APP.processEvents()
    assert _table_order(content) == ["c", "a", "b", "d"]
    assert [r.text for r in content.table_data if not r.checked] == ["b"]
    assert content.changes["selected_columns"] == ["c", "a", "d"]
    assert _output_cols(content) == ["c", "a", "d"]


def test_moves_record_history_steps():
    _parent, window, content, _host = _make_content()
    history = window.scene.history
    _select_proxy_row(content, 1)
    content.table_widget.moveSelectedRow("up", content.table_view)
    APP.processEvents()
    assert _table_order(content) == ["b", "a", "c", "d"]
    # First stamp is the baseline, not an undo step.
    assert history.controller.stack.count() == 0
    _select_proxy_row(content, 2)
    content.table_widget.moveSelectedRow("up", content.table_view)
    APP.processEvents()
    assert _table_order(content) == ["b", "c", "a", "d"]
    assert history.controller.stack.count() == 1


def test_move_undo_redo_round_trip():
    """Real scene undo of a move (snapshot restore + widget re-projection)."""
    _parent, window, content, _host = _make_content()
    history = window.scene.history
    _select_proxy_row(content, 1)
    content.table_widget.moveSelectedRow("up", content.table_view)
    APP.processEvents()
    assert _table_order(content) == ["b", "a", "c", "d"]
    _select_proxy_row(content, 2)
    content.table_widget.moveSelectedRow("up", content.table_view)
    APP.processEvents()
    assert _table_order(content) == ["b", "c", "a", "d"]
    assert history.controller.count == 1

    history.undo()
    APP.processEvents()
    assert _table_order(content) == ["b", "a", "c", "d"]
    assert _output_cols(content) == ["b", "a", "c", "d"]

    history.redo()
    APP.processEvents()
    assert _table_order(content) == ["b", "c", "a", "d"]
    assert _output_cols(content) == ["b", "c", "a", "d"]


def test_move_order_restores_via_update_from_changes():
    """Undo at the model level must put the rows back.

    (Full scene undo for snapshot nodes is legacy; this pins the widget
    reorder that an undo relies on.)
    """
    import copy

    _parent, _window, content, _host = _make_content()
    _select_proxy_row(content, 1)
    content.table_widget.moveSelectedRow("up", content.table_view)
    APP.processEvents()
    assert _table_order(content) == ["b", "a", "c", "d"]
    saved_changes = copy.deepcopy(content.changes)
    _select_proxy_row(content, 2)
    content.table_widget.moveSelectedRow("up", content.table_view)
    APP.processEvents()
    assert _table_order(content) == ["b", "c", "a", "d"]
    # Re-apply the restored state as an undo would (no new history).
    with content.history.restoring(is_undo=True):
        content.table_widget.update_from_changes(saved_changes)
        content.changes = copy.deepcopy(saved_changes)
        content.apply_changes()
    APP.processEvents()
    assert _table_order(content) == ["b", "a", "c", "d"]
    assert _output_cols(content) == ["b", "a", "c", "d"]


def test_upstream_add_preserves_user_order():
    _parent, _window, content, _host = _make_content()
    _select_proxy_row(content, 2)
    content.table_widget.moveSelectedRow("up", content.table_view)
    APP.processEvents()
    assert _table_order(content) == ["a", "c", "b", "d"]
    # Upstream adds 'e': survivors keep their order, newcomer appends checked.
    content.incom_data = pl.DataFrame(
        {c: [1, 2] for c in ["a", "b", "c", "d", "e"]}
    ).lazy()
    content.apply_changes()
    APP.processEvents()
    assert _table_order(content) == ["a", "c", "b", "d", "e"]
    assert content.changes["selected_columns"] == ["a", "c", "b", "d", "e"]
    assert _output_cols(content) == ["a", "c", "b", "d", "e"]
