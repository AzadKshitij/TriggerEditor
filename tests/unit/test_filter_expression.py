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

FRAME = pl.DataFrame(
    {
        "order_value": [10, 100, 600, 250],
        "status": ["paid", "pending", "paid", "refunded"],
    }
).lazy()


def _make_content():
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    cls = get_class_from_opcode(PreparationNodes.FILTER, NodeTypes.PREPARATION)
    node = cls(window.scene)
    window.scene.nodes.append(node)
    content = node.content
    content.incom_data = FRAME
    content.incoming_variable = "var_in"
    return parent, window, content


def _column_values(frame, column):
    collected = frame.collect() if hasattr(frame, "collect") else frame
    return collected.get_column(column).to_list()


def test_in_between_is_inclusive_and_order_free() -> None:
    _parent, _window, content = _make_content()
    content.mode = "builder"
    content.column = "order_value"
    content.operation = "In Between"
    content.value = "500"
    content.value2 = "0"
    content.update_data()
    assert sorted(_column_values(content.data, "order_value")) == [10, 100, 250]
    assert _column_values(content.f_data, "order_value") == [600]


def test_in_between_codegen_executes() -> None:
    _parent, _window, content = _make_content()
    content.mode = "builder"
    content.column = "order_value"
    content.operation = "In Between"
    content.value = "0"
    content.value2 = "500"
    content.update_data()
    code = content.get_code()
    assert "is_between(0.0, 500.0, closed='both')" in code
    namespace = {"var_in": FRAME}
    exec(code, {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    assert sorted(_column_values(namespace[content.variable_name], "order_value")) == [
        10,
        100,
        250,
    ]


def test_expression_mode_matches_live_and_codegen() -> None:
    _parent, _window, content = _make_content()
    content.mode = "expression"
    content.expression = "[order_value] in_between (0, 500) AND [status] = 'paid'"
    content.update_data()
    assert _column_values(content.data, "order_value") == [10]
    assert sorted(_column_values(content.f_data, "order_value")) == [100, 250, 600]

    code = content.get_code()
    assert "BETWEEN 0 AND 500" in code
    namespace = {"var_in": FRAME}
    exec(code, {"__name__": "__main__"}, namespace)  # noqa: S102
    assert _column_values(namespace[content.variable_name], "order_value") == [10]


def test_serialize_carries_filter_mode_state() -> None:
    _parent, window, content = _make_content()
    content.mode = "expression"
    content.expression = "[order_value] > 1"
    content.value2 = "7"
    data = window.scene.serialize()
    node_data = [
        node for node in data["nodes"] if node.get("op") == "preparation.filter"
    ]
    assert len(node_data) == 1
    state = node_data[0]["content"]
    assert state["mode"] == "expression"
    assert state["expression"] == "[order_value] > 1"
    assert state["value2"] == "7"


def test_legacy_filter_files_default_new_keys() -> None:
    _parent, _window, content = _make_content()
    content.deserialize({"column": "order_value", "operation": "Equals", "value": "5"})
    assert content.mode == "builder"
    assert content.expression == ""
    assert content.value2 == ""


def _cursor_position(widget) -> int:
    cursor = widget.textCursor()
    return cursor.position()


def _set_cursor_position(widget, position: int) -> None:
    cursor = widget.textCursor()
    cursor.setPosition(position)
    widget.setTextCursor(cursor)


def test_commit_preserves_caret_position() -> None:
    parent, window, content = _make_content()
    host = QWidget(parent)
    content.create_layout(QVBoxLayout(host))

    # Expression editor: caret mid-text survives a commit + sync round-trip.
    content.mode_selector.setCurrentText("Expression")
    editor = content.expression_input.editor
    content.expression_input.set_text("[order_value] > 100")
    _set_cursor_position(editor, 5)
    content.commit_expression()
    assert _cursor_position(editor) == 5, _cursor_position(editor)
    assert content.expression == "[order_value] > 100"

    # Builder value box: same guarantee through the sync path.
    content.mode_selector.setCurrentText("Simple")
    content.value_input.setText("250")
    content.value_input.setCursorPosition(1)
    content._sync_widgets_from_model()
    assert content.value_input.cursorPosition() == 1

    parent.deleteLater()


def test_strip_alias_filters_like_trim() -> None:
    parent, _window, content = _make_content()
    content.mode = "expression"
    content.expression = "strip([status]) = 'paid'"
    content.update_data()
    assert content.data.collect().get_column("order_value").to_list() == [10, 600]
    code = content.get_code()
    assert "trim(" in code and "strip(" not in code.split("WHERE", 1)[-1]
    parent.deleteLater()
