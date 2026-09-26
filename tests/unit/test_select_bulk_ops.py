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
    cls = get_class_from_opcode(PreparationNodes.SELECT, NodeTypes.PREPARATION)
    node = cls(window.scene)
    window.scene.nodes.append(node)
    content = node.content
    content.incom_data = pl.DataFrame(
        {
            "id": [1, 2],
            "price": ["10.5", "20.0"],
            "flag": ["true", "false"],
            "day": ["2024-01-01", "2024-01-02"],
            "name": ["a", "b"],
        }
    ).lazy()
    content.incoming_variable = "var_in"
    host = QWidget()
    content.create_layout(QVBoxLayout(host))
    return parent, window, content


def test_bulk_prefix_composes_onto_existing_rename() -> None:
    _parent, _window, content = _make_content()
    content.table_data[0].rename = "key"
    content.prompt_bulk_affix = _no_dialog(content, "p_")
    content.prompt_bulk_affix(selected_only=True, is_prefix=True)
    assert content.table_data[0].rename == "p_key"
    assert content.table_data[1].rename == "p_price"
    assert content.changes["rename_mapping"]["id"] == "p_key"


def _no_dialog(content, affix):
    def _prompt(selected_only, is_prefix):
        rows = content._bulk_target_rows(selected_only)
        for row in rows:
            base = row.rename or row.text
            row.rename = f"{affix}{base}" if is_prefix else f"{base}{affix}"
        content._bulk_commit()

    return _prompt


def test_bulk_scope_selected_vs_all() -> None:
    _parent, _window, content = _make_content()
    content.table_data[0].checked = False
    content.bulk_clear_renames(selected_only=True)
    # checked rows untouched (renames were empty); now set + clear selected
    content.table_data[1].rename = "x"
    content.bulk_clear_renames(selected_only=True)
    assert content.table_data[1].rename == ""
    content.table_data[1].rename = "x"
    content.table_data[0].rename = "y"
    content.bulk_clear_renames(selected_only=False)
    assert content.table_data[0].rename == ""
    assert content.table_data[1].rename == ""


def test_bulk_auto_detect_and_reset() -> None:
    _parent, _window, content = _make_content()
    content.bulk_auto_detect(selected_only=False)
    detected = {row.text: row.dtype for row in content.table_data}
    assert detected["id"] == "Int64"
    assert detected["price"] == "Float64"
    assert detected["flag"] == "Boolean"
    assert detected["day"] == "Date"
    assert detected["name"] == "String"
    content.bulk_reset_dtypes(selected_only=False)
    reset = {row.text: row.dtype for row in content.table_data}
    assert reset == {
        "id": "Int64",
        "price": "String",
        "flag": "String",
        "day": "String",
        "name": "String",
    }


def test_bulk_ops_record_single_history_step() -> None:
    _parent, window, content = _make_content()
    history = window.scene.history
    content.table_data[0].rename = "key"
    content.handleDataChanged(content.table_widget.getData())
    # First stamp is the baseline, not an undo step.
    assert history.controller.stack.count() == 0
    assert content.changes["rename_mapping"].get("id") == "key"
    content.bulk_clear_renames(selected_only=False)
    assert history.controller.stack.count() == 1
    assert content.changes["rename_mapping"] == {}
