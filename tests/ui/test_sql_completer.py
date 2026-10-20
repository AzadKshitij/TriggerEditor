#!/usr/bin/env python3

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from qtpy.QtCore import Qt
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.widgets.sql_formula_editor import (
    SQLFormulaEditor,
    translate_function_aliases,
)

APP = QApplication.instance() or QApplication([])


def _open_popup(editor, text):
    editor.show()
    editor.setFocus()
    editor.setPlainText(text)
    from qtpy.QtGui import QTextCursor

    editor.moveCursor(QTextCursor.MoveOperation.End)
    editor._maybe_autocomplete(forced=True)
    APP.processEvents()
    return editor.completer.popup()


def test_enter_inserts_highlighted_suggestion_not_first() -> None:
    editor = SQLFormulaEditor()
    editor.set_column_names(["order_value", "status"])
    popup = _open_popup(editor, "s")
    model = editor.completer.completionModel()
    assert model.rowCount() > 1
    popup.setCurrentIndex(model.index(1, 0))
    APP.processEvents()
    wanted = model.index(1, 0).data()
    first = model.index(0, 0).data()
    assert wanted != first
    QTest.keyClick(editor, Qt.Key.Key_Return)
    APP.processEvents()
    text = editor.toPlainText()
    assert wanted in text, text
    assert first not in text, text
    editor.deleteLater()


def test_enter_with_no_highlight_falls_back() -> None:
    editor = SQLFormulaEditor()
    editor.set_column_names(["order_value"])
    popup = _open_popup(editor, "s")
    assert popup.isVisible()
    QTest.keyClick(editor, Qt.Key.Key_Return)
    APP.processEvents()
    assert editor.toPlainText() != "s"
    editor.deleteLater()


def test_translate_function_aliases() -> None:
    assert translate_function_aliases("strip([name])") == "trim([name])"
    assert translate_function_aliases("STRIP( [name] )") == "trim( [name] )"
    assert (
        translate_function_aliases("upper(strip([a])) + strip([b])")
        == "upper(trim([a])) + trim([b])"
    )
    # Word boundary: identifiers containing "strip" are untouched.
    assert translate_function_aliases("outstrip([a])") == "outstrip([a])"
    # String literals are the caller's job; the token swap is literal.
    assert "trim(" in translate_function_aliases("strip(' x ')")
