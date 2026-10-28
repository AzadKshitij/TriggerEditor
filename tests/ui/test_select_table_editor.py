#!/usr/bin/env python3
"""Focused tests for the rebuilt Select table editor."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
from qtpy.QtCore import QEvent, QItemSelectionModel, Qt
from qtpy.QtGui import QColor, QKeyEvent
from qtpy.QtTest import QTest
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QMainWindow,
    QMenu,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.select_table_widget import (
    RowData,
    SelectTableModel,
)

APP = QApplication.instance() or QApplication([])


def _make_content(cols=("a", "b", "c", "d")):
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    cls = get_class_from_opcode(PreparationNodes.SELECT, NodeTypes.PREPARATION)
    node = cls(window.scene)
    window.scene.nodes.append(node)
    content = node.content
    content.frames[0] = pl.DataFrame({c: [1, 2] for c in cols}).lazy()
    content.input_vars[0] = "var_in"
    host = QWidget()
    content.create_layout(QVBoxLayout(host))
    return parent, window, content, host


def _select_proxy_row(content, proxy_row, clear=True):
    selection = content.table_view.selectionModel()
    if clear:
        selection.clear()
        content.table_view.clearSelection()
    index = content.proxy_model.index(proxy_row, 0)
    selection.select(
        index,
        QItemSelectionModel.SelectionFlag.Select
        | QItemSelectionModel.SelectionFlag.Rows,
    )
    content.table_view.setCurrentIndex(index)
    return index


def _undo_text(window):
    return window.scene.history.controller.stack.undoText()


def _proxy_names(content):
    return [
        content.proxy_model.index(row, SelectTableModel.COL_NAME).data()
        for row in range(content.proxy_model.rowCount())
    ]


def _current_name(content):
    index = content.table_view.currentIndex()
    return content.proxy_model.index(index.row(), SelectTableModel.COL_NAME).data()


# ---- search ----------------------------------------------------------------


def test_search_filters_live_after_debounce():
    _parent, window, content, _host = _make_content()
    content.search_input.setText("bee")
    content.table_widget.rows()[1].rename = "Bee"
    QTest.qWait(350)
    assert _proxy_names(content) == ["b"]
    # The search itself is view state, not a document edit.
    assert window.scene.history.controller.stack.count() == 0


def test_search_matches_name_rename_and_dtype():
    _parent, _window, content, _host = _make_content()
    rows = content.table_widget.rows()
    rows[1].rename = "Bee"
    content.search_input.setText("bee")
    content._apply_search_filter()
    assert _proxy_names(content) == ["b"]

    content.search_input.setText("Int64")
    content._apply_search_filter()
    assert _proxy_names(content) == ["a", "b", "c", "d"]

    content.search_input.setText("nothing")
    content._apply_search_filter()
    assert content.proxy_model.rowCount() == 0


# ---- keyboard --------------------------------------------------------------


def test_space_toggles_the_current_row():
    _parent, window, content, _host = _make_content()
    _select_proxy_row(content, 1)
    QTest.keyClick(content.table_view, Qt.Key.Key_Space)
    APP.processEvents()
    assert content.table_widget.rows()[1].checked is False
    assert content._table_changes()["selected_columns"] == ["a", "c", "d"]
    assert _undo_text(window) == "Column Deselected"


def test_alt_up_and_down_move_the_current_row():
    _parent, window, content, _host = _make_content()
    _select_proxy_row(content, 2)
    QTest.keyClick(content.table_view, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
    APP.processEvents()
    assert [row.text for row in content.table_data] == ["a", "c", "b", "d"]
    assert _undo_text(window) == "Columns Reordered"

    QTest.keyClick(content.table_view, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    APP.processEvents()
    assert [row.text for row in content.table_data] == ["a", "b", "c", "d"]


def test_f2_opens_the_rename_editor():
    _parent, _window, content, host = _make_content()
    host.show()
    _select_proxy_row(content, 0)
    QTest.keyClick(content.table_view, Qt.Key.Key_F2)
    APP.processEvents()
    assert content.table_view.currentIndex().column() == SelectTableModel.COL_RENAME
    editor = content.table_view.findChild(QLineEdit, "RenameEditor")
    assert editor is not None
    host.hide()


# ---- edges -----------------------------------------------------------------


def test_move_to_top_and_bottom_keep_selection_and_label_history():
    _parent, window, content, _host = _make_content()
    _select_proxy_row(content, 1)
    content.table_widget.moveSelectedToTop(content.table_view)
    APP.processEvents()
    assert [row.text for row in content.table_data] == ["b", "a", "c", "d"]
    assert _current_name(content) == "b"
    assert _undo_text(window) == "Columns Moved to Top"

    _select_proxy_row(content, 2)
    content.table_widget.moveSelectedToBottom(content.table_view)
    APP.processEvents()
    assert [row.text for row in content.table_data] == ["b", "a", "d", "c"]
    assert _current_name(content) == "c"
    assert _undo_text(window) == "Columns Moved to Bottom"


def test_move_to_top_is_a_noop_when_already_first():
    _parent, window, content, _host = _make_content()
    before = window.scene.history.controller.stack.count()
    _select_proxy_row(content, 0)
    content.table_widget.moveSelectedToTop(content.table_view)
    APP.processEvents()
    assert [row.text for row in content.table_data] == ["a", "b", "c", "d"]
    assert window.scene.history.controller.stack.count() == before


# ---- delegates -------------------------------------------------------------


def _dtype_index(content, row):
    return content.proxy_model.index(row, SelectTableModel.COL_DTYPE)


def test_clicking_a_dtype_cell_opens_the_dropdown():
    _parent, _window, content, host = _make_content()
    host.show()
    content.table_view.resize(640, 320)
    content.table_view.show()
    APP.processEvents()
    index = _dtype_index(content, 0)
    rect = content.table_view.visualRect(index)
    QTest.mouseClick(
        content.table_view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=rect.center(),
    )
    APP.processEvents()
    editor = content.table_view.findChild(QComboBox, "DataTypeCombo")
    assert editor is not None
    assert editor.currentText() == "Int64"
    editor.hidePopup()
    host.hide()


def test_dtype_delegate_commits_and_clears_stale_date_format():
    _parent, window, content, _host = _make_content()
    row = content.table_widget.rows()[0]
    row.date_format = "%Y-%m-%d"
    index = _dtype_index(content, 0)
    delegate = content.table_view.itemDelegateForColumn(SelectTableModel.COL_DTYPE)
    editor = delegate.createEditor(content.table_view, QStyleOptionViewItem(), index)
    delegate.setEditorData(editor, index)
    assert editor.currentText() == "Int64"
    editor.setCurrentText("Float64")
    delegate.setModelData(editor, content.proxy_model, index)
    APP.processEvents()

    assert row.dtype == "Float64"
    assert row.date_format == ""
    assert content._table_changes()["dtype_mapping"]["a"] == "Float64"
    assert _undo_text(window) == "Column Type Changed"
    editor.deleteLater()


def test_rename_delegate_commits_trimmed_on_close_not_on_typing():
    _parent, window, content, _host = _make_content()
    index = content.proxy_model.index(0, SelectTableModel.COL_RENAME)
    delegate = content.table_view.itemDelegateForColumn(SelectTableModel.COL_RENAME)
    editor = delegate.createEditor(content.table_view, QStyleOptionViewItem(), index)
    delegate.setEditorData(editor, index)

    editor.setText("  Bee  ")
    assert content.table_widget.rows()[0].rename == ""
    delegate.setModelData(editor, content.proxy_model, index)
    APP.processEvents()

    assert content.table_widget.rows()[0].rename == "Bee"
    assert content._table_changes()["rename_mapping"]["a"] == "Bee"
    assert _undo_text(window) == "Column Renamed"
    editor.deleteLater()


def test_rename_delegate_escape_reverts_without_touching_the_model():
    _parent, _window, content, _host = _make_content()
    content.table_widget.rows()[0].rename = "Bee"
    index = content.proxy_model.index(0, SelectTableModel.COL_RENAME)
    delegate = content.table_view.itemDelegateForColumn(SelectTableModel.COL_RENAME)
    editor = delegate.createEditor(content.table_view, QStyleOptionViewItem(), index)
    delegate.setEditorData(editor, index)
    editor.setText("Other")

    hints = []
    delegate.closeEditor.connect(lambda _editor, hint: hints.append(hint))
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
    )
    handled = delegate.eventFilter(editor, event)
    APP.processEvents()

    assert handled is True
    assert hints == [delegate.EndEditHint.RevertModelCache]
    assert content.table_widget.rows()[0].rename == "Bee"
    editor.deleteLater()


# ---- context menu ----------------------------------------------------------


def test_context_menu_offers_selection_move_and_bulk_actions(monkeypatch):
    _parent, _window, content, _host = _make_content()
    _select_proxy_row(content, 1)
    captured = {}

    class _CapturingMenu(QMenu):
        def exec(self, *_args):
            captured["texts"] = [action.text() for action in self.actions()]
            for action in self.actions():
                if action.text() == "Move to Top":
                    action.trigger()

    select_module = sys.modules["trigger_designer.qt.widgets.nodes.Preparation.select"]
    monkeypatch.setattr(select_module, "QMenu", _CapturingMenu)
    content._show_table_context_menu(
        content.table_view.mapToGlobal(content.table_view.rect().center())
    )

    texts = captured["texts"]
    assert "Select Highlighted" in texts
    assert "Deselect Highlighted" in texts
    assert "Move to Top" in texts
    assert "Move Up" in texts
    assert "Move Down" in texts
    assert "Move to Bottom" in texts
    assert "Clear Renames" in texts
    assert "Reset Types" in texts
    assert [row.text for row in content.table_data] == ["b", "a", "c", "d"]


# ---- model roles -----------------------------------------------------------


def test_missing_rows_are_tinted_and_explained():
    row = RowData(checked=True, text="gone", dtype="Int64", is_missing=True)
    model = SelectTableModel([row], {})
    index = model.index(0, SelectTableModel.COL_NAME)

    background = model.data(index, Qt.ItemDataRole.BackgroundRole)
    assert isinstance(background, QColor)
    assert background.alpha() == 140
    assert model.data(index, Qt.ItemDataRole.ToolTipRole) == (
        "Column not found in the current input"
    )
