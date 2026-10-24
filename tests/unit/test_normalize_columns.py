#!/usr/bin/env python3
"""Normalize node identity, live execution and saved state."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QApplication, QMainWindow

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.core.shaping import normalize as core
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode

APP = QApplication.instance() or QApplication([])


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, frame) -> None:
        self._frame = frame
        super().__init__(scene, inputs=[], outputs=[3])
        self.value = [{"data": frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)

    def evalImplementation(self):
        self.value = [{"data": self._frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


def _make_content():
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    cls = get_class_from_opcode(
        PreparationNodes.NORMALIZE_COLUMNS, NodeTypes.PREPARATION
    )
    node = cls(window.scene)
    window.scene.nodes.append(node)
    return window, node


def test_op_resolves_to_normalize_columns() -> None:
    cls = get_class_from_opcode(
        PreparationNodes.NORMALIZE_COLUMNS, NodeTypes.PREPARATION
    )
    assert cls.node_title == "Normalize"
    assert cls.node_type.value + "." + cls.node_code.name.lower() == (
        "preparation.normalize_columns"
    )


def test_normalize_column_name_cases() -> None:
    assert core.normalize_column_name(" Order ID ") == "Order_ID"
    assert core.normalize_column_name("Customer_Id") == "Customer_Id"
    assert core.normalize_column_name("a  b\tc") == "a_b_c"
    assert core.normalize_column_name("  ") == "  "
    assert core.normalize_column_name("a b", remove_all_whitespace=True) == "ab"
    assert core.normalize_column_name("Mixed Case", case_modification="lower") == (
        "mixed_case"
    )


def test_live_rename_and_codegen_agree() -> None:
    window, node = _make_content()
    frame = pl.DataFrame({" Order ID ": [1], "Customer_Id": [2], "sku": [3]}).lazy()
    source = Source(window.scene, frame)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    live = node.eval()
    assert live is not None and not node.isInvalid()
    assert live[0]["data"].collect_schema().names() == [
        "Order_ID",
        "Customer_Id",
        "sku",
    ]

    namespace = {"var_src": frame}
    exec(node.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    result = namespace[node.content.variable_name]
    assert result.collect_schema().names() == [
        "Order_ID",
        "Customer_Id",
        "sku",
    ]


def test_duplicate_targets_are_a_shaping_error() -> None:
    window, node = _make_content()
    source = Source(window.scene, pl.DataFrame({"a b": [1], "a_b": [2]}).lazy())
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    assert node.eval() is None
    assert node.isInvalid()


def test_serialize_carries_normalize_state() -> None:
    window, node = _make_content()
    assert node.content.variable_name.startswith("var_normalize_")
    data = window.scene.serialize()
    node_data = [
        item
        for item in data["nodes"]
        if item.get("op") == "preparation.normalize_columns"
    ]
    assert len(node_data) == 1
    settings = node_data[0]["content"]["settings"]
    assert settings["trim_whitespace"] is True
    assert settings["spaces_to_underscore"] is True
    assert settings["case_modification"] == "none"
    assert settings["selected_columns"] == []
