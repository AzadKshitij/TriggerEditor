#!/usr/bin/env python3
"""Downstream Select nodes must follow upstream renames, not go stale."""

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

from tests.support.flush import flush
from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode, upstream_rename_map

APP = QApplication.instance() or QApplication([])


class _Stub(TriggerNode):
    """Source node evaluating to a fixed frame."""

    def evalImplementation(self):
        return [{"data": self._df, "variable_name": self._var}]


def _stub_node(scene, df, var="var_in"):
    node = _Stub(scene, inputs=[], outputs=[3])
    node._df, node._var = df, var
    node.markDirty(True)
    return node


def _select_node(scene):
    cls = get_class_from_opcode(PreparationNodes.SELECT, NodeTypes.PREPARATION)
    return cls(scene)


def _rename_headless(content, mapping):
    columns = [dict(column) for column in content.settings["columns"]]
    for column in columns:
        if column["name"] in mapping:
            column["rename"] = mapping[column["name"]]
    content.set_setting("columns", columns, "Select Columns Changed")
    flush(content)  # the node runs when it is left
    content.node.markDirty(True)
    content.node.eval()
    APP.processEvents()


def _wired_pair(left_cols=("customer_full_name", "age")):
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    scene = window.scene
    stub = _stub_node(
        scene,
        pl.DataFrame({column: [1, 2] for column in left_cols}).lazy(),
    )
    up = _select_node(scene)
    Edge(scene, stub.outputs[0], up.inputs[0])
    up.eval()
    down = _select_node(scene)
    Edge(scene, up.outputs[0], down.inputs[0])
    down.eval()
    APP.processEvents()
    return {"parent": parent, "window": window, "stub": stub, "up": up, "down": down}


def _names(content):
    return [column["name"] for column in content.settings["columns"]]


def _schema(node):
    if not node.value:
        return []
    return node.value[0]["data"].collect_schema().names()


def test_downstream_select_follows_upstream_rename_end_to_end():
    refs = _wired_pair()
    up, down = refs["up"], refs["down"]
    assert _names(down.content) == ["customer_full_name", "age"]

    _rename_headless(up.content, {"customer_full_name": "customer_name"})
    down.eval()
    APP.processEvents()

    assert _schema(up) == ["customer_name", "age"]
    assert _names(down.content) == ["customer_name", "age"]
    assert [column["selected"] for column in down.content.settings["columns"]] == [
        True,
        True,
    ]
    assert _schema(down) == ["customer_name", "age"]
    assert "customer_full_name" not in down.content.get_code()
    assert "customer_name" in down.content.get_code()


def test_follow_preserves_order_and_settings():
    refs = _wired_pair()
    down = refs["down"]
    content = down.content
    columns = [dict(column) for column in content.settings["columns"]]
    for column in columns:
        if column["name"] == "customer_full_name":
            column["rename"] = "cust"
            column["dtype"] = "String"
            column["dtype_custom"] = True
    content.set_setting("columns", columns, "Select Columns Changed")
    down.markDirty(True)
    down.eval()
    assert _schema(down)[0] == "cust"

    _rename_headless(refs["up"].content, {"customer_full_name": "customer_name"})
    down.eval()
    APP.processEvents()

    assert _names(content) == ["customer_name", "age"]
    renamed = next(
        column
        for column in content.settings["columns"]
        if column["name"] == "customer_name"
    )
    assert renamed["rename"] == "cust"
    assert renamed["dtype"] == "String"
    assert _schema(down)[0] == "cust"


def test_follow_skips_collisions():
    refs = _wired_pair(left_cols=("a", "b"))
    content = refs["down"].content
    assert content.apply_upstream_renames({"a": "b"}) is False
    assert _names(content) == ["a", "b"]


def test_upstream_rename_map_reports_select_renames():
    refs = _wired_pair()
    up = refs["up"]
    assert upstream_rename_map(up) == {}
    _rename_headless(up.content, {"customer_full_name": "customer_name"})
    assert upstream_rename_map(up) == {"customer_full_name": "customer_name"}


def test_upstream_rename_map_ignores_non_renaming_nodes():
    refs = _wired_pair()
    assert upstream_rename_map(refs["stub"]) == {}
    assert upstream_rename_map(None) == {}
