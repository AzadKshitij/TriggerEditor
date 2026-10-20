#!/usr/bin/env python3
"""Downstream Select nodes must follow upstream renames, not go stale."""

import copy
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

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
    """Rename via the same path the table widget uses (row edit + signal)."""
    for row in content.table_data:
        if row.text in mapping:
            row.rename = mapping[row.text]
    payload = [(row.text, row.dtype, row.rename) for row in content.table_data]
    content.handleDataChanged(payload)
    APP.processEvents()


def _wired_pair(left_cols=("customer_full_name", "age")):
    """stub -> up_select -> down_select, all evaluated. Returns refs dict."""
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    scene = window.scene
    stub = _stub_node(
        scene,
        pl.DataFrame({c: [1, 2] for c in left_cols}).lazy(),
    )
    up = _select_node(scene)
    Edge(scene, stub.outputs[0], up.inputs[0])
    up.eval()
    down = _select_node(scene)
    Edge(scene, up.outputs[0], down.inputs[0])
    down.eval()
    APP.processEvents()
    return {"parent": parent, "window": window, "stub": stub, "up": up, "down": down}


def test_downstream_select_follows_upstream_rename_end_to_end():
    refs = _wired_pair()
    up, down = refs["up"], refs["down"]
    assert [r.text for r in down.content.table_data] == [
        "customer_full_name",
        "age",
    ]

    _rename_headless(up.content, {"customer_full_name": "customer_name"})
    down.eval()
    APP.processEvents()

    assert list(up.content.data.collect_schema().names()) == [
        "customer_name",
        "age",
    ]
    # Followed in place: position kept, not appended at the end.
    assert [r.text for r in down.content.table_data] == ["customer_name", "age"]
    assert down.content.changes["selected_columns"] == ["customer_name", "age"]
    assert down.content.changes["column_order"] == ["customer_name", "age"]
    assert list(down.content.data.collect_schema().names()) == [
        "customer_name",
        "age",
    ]
    assert "customer_full_name" not in down.content.get_code()
    assert "customer_name" in down.content.get_code()


def test_follow_preserves_order_and_migrates_settings_keys():
    refs = _wired_pair()
    down = refs["down"]
    content = down.content
    # Downstream has its own rename + dtype pinned to the old name.
    content.changes["rename_mapping"] = {"customer_full_name": "cust"}
    content.changes["dtype_mapping"] = {"customer_full_name": "String"}
    content.apply_changes()
    assert next(iter(content.data.collect_schema().names())) == "cust"

    _rename_headless(refs["up"].content, {"customer_full_name": "customer_name"})
    down.eval()
    APP.processEvents()

    assert [r.text for r in content.table_data] == ["customer_name", "age"]
    assert content.changes["rename_mapping"] == {"customer_name": "cust"}
    assert content.changes["dtype_mapping"]["customer_name"] == "String"
    assert next(iter(content.data.collect_schema().names())) == "cust"


def test_follow_skips_collisions():
    refs = _wired_pair(left_cols=("a", "b"))
    down = refs["down"]
    content = down.content
    # Both old and new already present: ambiguous, leave untouched.
    assert content.apply_upstream_renames({"a": "b"}) is False
    assert [r.text for r in content.table_data] == ["a", "b"]


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


def test_auto_accept_off_new_column_arrives_unchecked():
    refs = _wired_pair()
    down = refs["down"]
    content = down.content
    content.changes["auto_accept_new_columns"] = False
    content.incom_data = pl.DataFrame(
        {"customer_full_name": [1], "age": [2], "nickname": [3]}
    ).lazy()
    content.apply_changes()
    APP.processEvents()
    assert [r.text for r in content.table_data] == [
        "customer_full_name",
        "age",
        "nickname",
    ]
    nick = next(r for r in content.table_data if r.text == "nickname")
    assert nick.checked is False
    assert "nickname" not in content.changes["selected_columns"]
    assert "nickname" not in list(content.data.collect_schema().names())


def test_auto_accept_on_is_default_and_arrives_checked():
    refs = _wired_pair()
    down = refs["down"]
    content = down.content
    assert content.changes.get("auto_accept_new_columns", True) is True
    content.incom_data = pl.DataFrame(
        {"customer_full_name": [1], "age": [2], "nickname": [3]}
    ).lazy()
    content.apply_changes()
    APP.processEvents()
    nick = next(r for r in content.table_data if r.text == "nickname")
    assert nick.checked is True
    assert "nickname" in content.changes["selected_columns"]


def _open_dock(content):
    host = QWidget()
    content.create_layout(QVBoxLayout(host))
    APP.processEvents()
    return host


def test_auto_accept_toggle_round_trip_with_undo():
    refs = _wired_pair()
    down = refs["down"]
    host = _open_dock(down.content)
    assert host is not None
    action = down.content._auto_accept_action
    assert action is not None and action.isChecked() is True
    history = refs["window"].scene.history
    before = history.controller.count

    action.setChecked(False)
    APP.processEvents()
    assert down.content.changes["auto_accept_new_columns"] is False
    assert history.controller.count == before + 1

    history.undo()
    APP.processEvents()
    assert down.content.changes["auto_accept_new_columns"] is True
    assert action.isChecked() is True

    history.redo()
    APP.processEvents()
    assert down.content.changes["auto_accept_new_columns"] is False
    assert action.isChecked() is False


def test_undo_redo_restore_renamed_order():
    """Real scene undo of a rename follow, not a model-level simulation."""
    refs = _wired_pair()
    up, down = refs["up"], refs["down"]
    history = refs["window"].scene.history

    _rename_headless(up.content, {"customer_full_name": "customer_name"})
    down.eval()
    APP.processEvents()
    assert [r.text for r in down.content.table_data] == ["customer_name", "age"]
    # First stamp is the baseline, not an undo step.
    assert history.controller.count == 0

    _rename_headless(up.content, {"age": "years"})
    down.eval()
    APP.processEvents()
    assert [r.text for r in down.content.table_data] == ["customer_name", "years"]
    assert history.controller.count == 1

    history.undo()
    APP.processEvents()
    # Undo restores configs; downstream recomputes on the next evaluation
    # (the scene does not cascade evals after a restore).
    up.markDirty(True)
    down.markDirty(True)
    down.eval()
    APP.processEvents()
    assert [r.text for r in down.content.table_data] == ["customer_name", "age"]
    assert list(down.content.data.collect_schema().names()) == [
        "customer_name",
        "age",
    ]

    history.redo()
    APP.processEvents()
    up.markDirty(True)
    down.markDirty(True)
    down.eval()
    APP.processEvents()
    assert [r.text for r in down.content.table_data] == ["customer_name", "years"]


def test_serialize_round_trip_keeps_flag():
    refs = _wired_pair()
    down = refs["down"]
    down.content.changes["auto_accept_new_columns"] = False
    payload = down.content.serialize()
    assert payload["changes"]["auto_accept_new_columns"] is False

    fresh = _select_node(refs["window"].scene)
    fresh.content.deserialize(copy.deepcopy(payload))
    assert fresh.content.changes["auto_accept_new_columns"] is False
