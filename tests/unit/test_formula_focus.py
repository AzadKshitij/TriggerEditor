#!/usr/bin/env python3

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
from qtpy.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

APP = QApplication.instance() or QApplication([])


def _make_content():
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    cls = get_class_from_opcode(PreparationNodes.FORMULA, NodeTypes.PREPARATION)
    node = cls(window.scene)
    window.scene.nodes.append(node)
    content = node.content
    content.incom_data = pl.DataFrame({"a": [1, 2, 3]}).lazy()
    content.incoming_variable = "var_in"
    content.formula_sections[0]["target_column"] = "b"
    host = QWidget()
    content.create_layout(QVBoxLayout(host))
    return parent, window, content, host


def test_typing_keeps_editor_identity_and_focus() -> None:
    _parent, window, content, host = _make_content()
    host.show()
    APP.processEvents()
    editor_widget = content.section_widgets[0]["formula_input"]
    editor_widget.editor.setFocus()
    APP.processEvents()
    editor_widget.set_text("[a] + 1")
    content.commit_formula_text(0)

    # No rebuild: the same editor object survives the commit.
    assert content.section_widgets[0]["formula_input"] is editor_widget
    focused = QApplication.focusWidget()
    assert focused is not None and (
        focused is editor_widget.editor
        or editor_widget.editor.isAncestorOf(focused)
        or focused is editor_widget
    )
    assert content.formula_sections[0]["formula_text"] == "[a] + 1"
    window.scene.history.controller.undo()
    assert content.formula_sections[0]["formula_text"] == ""
    assert editor_widget.get_text() == ""


def test_structural_change_still_rebuilds() -> None:
    _parent, window, content, _host = _make_content()
    before = len(content.section_widgets)
    content.add_formula_section()
    assert len(content.section_widgets) == before + 1
    window.scene.history.controller.undo()
    assert len(content.formula_sections) == before
