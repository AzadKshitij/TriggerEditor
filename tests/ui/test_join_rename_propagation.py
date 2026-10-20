#!/usr/bin/env python3
"""Join must follow upstream renames and auto-accept new columns on demand."""

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
    JoinNodes,
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode

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


def _join_node(scene):
    cls = get_class_from_opcode(JoinNodes.JOIN, NodeTypes.JOIN)
    return cls(scene)


def _rename_headless(content, mapping):
    """Rename via the same path the table widget uses (row edit + signal)."""
    for row in content.table_data:
        if row.text in mapping:
            row.rename = mapping[row.text]
    payload = [(row.text, row.dtype, row.rename) for row in content.table_data]
    content.handleDataChanged(payload)
    APP.processEvents()


def _wired_join():
    """left Select -> Join <- right stub. Returns refs dict."""
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    scene = window.scene
    left_stub = _stub_node(
        scene,
        pl.DataFrame({"customer_full_name": ["A", "B"], "age": [30, 40]}).lazy(),
        "var_left_src",
    )
    left = _select_node(scene)
    Edge(scene, left_stub.outputs[0], left.inputs[0])
    left.eval()
    right = _stub_node(
        scene,
        pl.DataFrame({"customer_full_name": ["A", "C"], "city": ["X", "Y"]}).lazy(),
        "var_right",
    )
    join = _join_node(scene)
    Edge(scene, left.outputs[0], join.inputs[0])
    Edge(scene, right.outputs[0], join.inputs[1])
    join.eval()
    APP.processEvents()
    return {
        "parent": parent,
        "window": window,
        "left": left,
        "right": right,
        "join": join,
    }


def test_mapping_follows_left_rename_end_to_end():
    refs = _wired_join()
    join = refs["join"]
    assert join.content.mapping_data == [
        {"left_column": "customer_full_name", "right_column": "customer_full_name"}
    ]

    _rename_headless(refs["left"].content, {"customer_full_name": "customer_name"})
    join.eval()
    APP.processEvents()

    assert join.content.mapping_data == [
        {"left_column": "customer_name", "right_column": "customer_full_name"}
    ]
    assert join.content.data is not None
    out = join.content.data.columns
    assert "customer_name" in out
    assert "customer_full_name" not in out


def test_selected_follows_rename_and_code_is_fresh():
    refs = _wired_join()
    join = refs["join"]
    join.content.selected_columns = [
        {"name": "customer_full_name", "source": "L"},
        {"name": "age", "source": "L"},
    ]
    _rename_headless(refs["left"].content, {"customer_full_name": "customer_name"})
    join.eval()
    APP.processEvents()

    names = [
        (c["name"], c["source"])
        for c in join.content.selected_columns
        if c["source"] == "L"
    ]
    assert ("customer_name", "L") in names
    assert ("customer_full_name", "L") not in names
    code = join.content.get_code()
    assert "customer_name" in code
    assert "customer_full_name" not in code.split("right_on")[0]


def _headless_join():
    """Join content with direct data (no edges) for selection-matrix tests."""
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    join = _join_node(window.scene)
    content = join.content
    content.left_data = pl.DataFrame({"a": [1], "b": [2]})
    content.left_variable = "var_l"
    content.right_data = pl.DataFrame({"a": [1], "c": [3]})
    content.right_variable = "var_r"
    content.mapping_data = [{"left_column": "a", "right_column": "a"}]
    content.selected_columns = [
        {"name": "a", "source": "L"},
        {"name": "b", "source": "L"},
    ]
    return parent, window, content


def test_first_sync_records_selection_without_expanding_it():
    _parent, _window, content = _headless_join()
    assert content.transform_data() is not None
    # Legacy selection (L-only) is preserved, not expanded to R columns.
    assert content.selected_columns == [
        {"name": "a", "source": "L"},
        {"name": "b", "source": "L"},
    ]


def test_new_arrival_auto_added_when_on():
    _parent, _window, content = _headless_join()
    assert content.transform_data() is not None
    content.left_data = pl.DataFrame({"a": [1], "b": [2], "nick": [3]})
    assert content.transform_data() is not None
    assert {"name": "nick", "source": "L"} in content.selected_columns


def test_new_arrival_held_back_when_off():
    _parent, _window, content = _headless_join()
    assert content.transform_data() is not None
    content.auto_accept_new_columns = False
    content.left_data = pl.DataFrame({"a": [1], "b": [2], "nick": [3]})
    assert content.transform_data() is not None
    assert {"name": "nick", "source": "L"} not in content.selected_columns
    # Enabling picks up the pending arrival but nothing else.
    content.auto_accept_new_columns = True
    content.transform_data()
    assert {"name": "nick", "source": "L"} in content.selected_columns


def test_explicit_uncheck_survives_reeval():
    _parent, _window, content = _headless_join()
    assert content.transform_data() is not None
    content.selected_columns = [c for c in content.selected_columns if c["name"] != "b"]
    assert content.transform_data() is not None
    assert content.transform_data() is not None
    names = {(c["name"], c["source"]) for c in content.selected_columns}
    assert ("b", "L") not in names
    assert ("a", "L") in names


def _open_dock(content):
    host = QWidget()
    content.create_layout(QVBoxLayout(host))
    APP.processEvents()
    return host


def test_toggle_round_trip_with_undo_redo():
    _parent, window, content = _headless_join()
    host = _open_dock(content)
    assert host is not None
    action = content._auto_accept_action
    assert action is not None and action.isChecked() is True
    history = window.scene.history
    history.storeInitialHistoryStamp()

    action.setChecked(False)
    APP.processEvents()
    assert content.auto_accept_new_columns is False
    assert history.controller.count == 1

    history.undo()
    APP.processEvents()
    assert content.auto_accept_new_columns is True
    # The app rebuilds the dock on history restore (force=True); simulate
    # that here since there is no ConfigDock headless (keep the host alive
    # or Qt deletes the new action out from under the assertion).
    host_after_undo = _open_dock(content)
    APP.processEvents()
    assert content._auto_accept_action.isChecked() is True

    history.redo()
    APP.processEvents()
    assert content.auto_accept_new_columns is False
    host_after_redo = _open_dock(content)
    APP.processEvents()
    assert content._auto_accept_action.isChecked() is False
    assert host_after_undo is not None and host_after_redo is not None


def test_serialize_round_trip_keeps_flag_and_known():
    _parent, _window, content = _headless_join()
    assert content.transform_data() is not None
    content.auto_accept_new_columns = False
    payload = content.serialize()
    assert payload["auto_accept_new_columns"] is False
    assert payload["known_columns"] != []

    scene = _window.scene
    fresh_join = _join_node(scene)
    fresh_join.content.deserialize(payload)
    assert fresh_join.content.auto_accept_new_columns is False
    assert fresh_join.content.known_columns == payload["known_columns"]
