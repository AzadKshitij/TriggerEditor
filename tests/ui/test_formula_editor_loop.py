#!/usr/bin/env python3
"""Highlighting the errors must not touch the document.

The error underline is painted with ``setExtraSelections``. It used to be
painted by writing character formats into the document, and Qt answers a
format write with ``textChanged`` - the same signal a real edit produces.
This editor's ``textChanged`` handler clears the diagnostics, so the errors
were wiped between being computed and being shown, and the error label
stayed empty.

These tests pin the invariant: painting the diagnostics leaves the document
alone, leaves the text alone, and does not disturb the undo stack.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from qtpy.QtWidgets import QApplication

from trigger_designer.qt.widgets.sql_formula_editor import SQLFormulaEditor

APP = QApplication.instance() or QApplication([])


def _editor(text: str = "[amount] +\n )") -> SQLFormulaEditor:
    editor = SQLFormulaEditor()
    editor.setPlainText(text)
    return editor


def test_highlighting_does_not_fire_text_changed() -> None:
    """Painting the diagnostics must not look like a user edit."""
    editor = _editor()
    editor.errors = [
        {"message": "syntax error", "line": 2, "column": 1, "length": 1},
    ]

    changes = []
    editor.textChanged.connect(lambda: changes.append(True))

    editor.update_error_highlights()

    assert changes == [], "highlighting the errors must not emit textChanged"
    editor.deleteLater()


def test_highlighting_does_not_change_the_document() -> None:
    """The text and its formats survive a repaint."""
    editor = _editor()
    before = editor.toPlainText()

    editor.errors = [
        {"message": "syntax error", "line": 2, "column": 1, "length": 1},
    ]
    editor.update_error_highlights()

    assert editor.toPlainText() == before
    editor.deleteLater()


def test_highlighting_does_not_touch_the_undo_stack() -> None:
    """A repaint is not something the user can undo."""
    editor = _editor()
    editor.errors = [
        {"message": "syntax error", "line": 2, "column": 1, "length": 1},
    ]

    editor.update_error_highlights()
    assert not editor.document().isUndoAvailable()

    editor.deleteLater()


def test_the_errors_survive_a_repaint() -> None:
    """The diagnostics are still there after they have been painted."""
    editor = _editor()
    editor.errors = [
        {"message": "syntax error", "line": 2, "column": 1, "length": 1},
    ]

    editor.update_error_highlights()

    assert len(editor.errors) == 1
    assert editor.errors[0]["message"] == "syntax error"
    assert len(editor.extraSelections()) == 1
    editor.deleteLater()


def test_a_fixed_error_leaves_no_underline_behind() -> None:
    """Clearing the errors clears the underline as well."""
    editor = _editor()
    editor.errors = [
        {"message": "syntax error", "line": 2, "column": 1, "length": 1},
    ]
    editor.update_error_highlights()
    assert editor.extraSelections()

    editor.errors = []
    editor.update_error_highlights()

    assert editor.extraSelections() == []
    editor.deleteLater()
