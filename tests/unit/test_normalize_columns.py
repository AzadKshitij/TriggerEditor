#!/usr/bin/env python3

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
from qtpy.QtWidgets import QApplication, QMainWindow

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.nodes.Preparation.normalize_columns import (
    build_rename_mapping,
    normalize_column_name,
)

APP = QApplication.instance() or QApplication([])


def _make_content():
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    cls = get_class_from_opcode(
        PreparationNodes.NORMALIZE_COLUMNS, NodeTypes.PREPARATION
    )
    node = cls(window.scene)
    window.scene.nodes.append(node)
    return window, node.content


def test_op_resolves_to_normalize_columns() -> None:
    cls = get_class_from_opcode(
        PreparationNodes.NORMALIZE_COLUMNS, NodeTypes.PREPARATION
    )
    assert cls.node_title == "Normalize Columns"
    assert cls.node_type.value + "." + cls.node_code.name.lower() == (
        "preparation.normalize_columns"
    )


def test_normalize_column_name_cases() -> None:
    assert normalize_column_name(" Order ID ") == "Order_ID"
    assert normalize_column_name("Customer_Id") == "Customer_Id"
    assert normalize_column_name("a  b\tc") == "a_b_c"
    assert normalize_column_name("  ") == "  "
    assert normalize_column_name("a b", remove_all_whitespace=True) == "ab"
    assert normalize_column_name("Mixed Case", case_modification="lower") == (
        "mixed_case"
    )
    assert normalize_column_name("Mixed Case", case_modification="upper") == (
        "MIXED_CASE"
    )


def test_live_rename_and_codegen_agree() -> None:
    _, content = _make_content()
    content.incom_data = pl.DataFrame(
        {" Order ID ": [1], "Customer_Id": [2], "sku": [3]}
    ).lazy()
    content.incoming_variable = "var_in"
    content.update_data()
    assert content.data.collect_schema().names() == [
        "Order_ID",
        "Customer_Id",
        "sku",
    ]

    code = content.get_code()
    namespace = {"var_in": content.incom_data}
    exec(code, {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    result = namespace[content.variable_name]
    assert result.collect_schema().names() == [
        "Order_ID",
        "Customer_Id",
        "sku",
    ]


def test_duplicate_targets_invalidate() -> None:
    _, content = _make_content()
    content.incom_data = pl.DataFrame({"a b": [1], "a_b": [2]}).lazy()
    content.incoming_variable = "var_in"
    content.update_data()
    assert content.data is None
    assert content.node.isInvalid()


def test_build_rename_mapping_respects_scope() -> None:
    mapping = build_rename_mapping(["a b", "c d"], ["c d"])
    assert mapping == {"c d": "c_d"}


def test_serialize_carries_normalize_state() -> None:
    window, content = _make_content()
    assert content.variable_name.startswith("var_normalize_columns_")
    data = window.scene.serialize()
    node_data = [
        node
        for node in data["nodes"]
        if node.get("op") == "preparation.normalize_columns"
    ]
    assert len(node_data) == 1
    state = node_data[0]["content"]
    assert state["trim_whitespace"] is True
    assert state["spaces_to_underscore"] is True
    assert state["case_modification"] == "none"
    assert state["selected_columns"] == []
