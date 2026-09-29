#!/usr/bin/env python3
"""dtype_mapping serializes sparsely (an entry only when it genuinely
differs from the column's incoming dtype) but deserializes back to the
same fully-populated shape apply_changes()/get_code() have always expected,
so runtime behavior is unchanged and only the saved/undo-snapshot bytes
shrink.
"""

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
from qtpy.QtWidgets import QApplication, QMainWindow

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.nodes.Preparation.select import SelectContent
from trigger_designer.qt.widgets.select_table_widget import RowData

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


def _evaluated_select(df):
    """stub -> select, evaluated once. Returns (parent, window, node)."""
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    scene = window.scene
    stub = _stub_node(scene, df)
    node = _select_node(scene)
    Edge(scene, stub.outputs[0], node.inputs[0])
    node.eval()
    APP.processEvents()
    return parent, window, node


def _retype_headless(content, dtypes: dict):
    """Change dtypes via the same path the table widget uses (row edit + signal)."""
    for row in content.table_data:
        if row.text in dtypes:
            row.dtype = dtypes[row.text]
    payload = [(row.text, row.dtype, row.rename) for row in content.table_data]
    content.handleDataChanged(payload)
    APP.processEvents()


# --- serialize() sparsifies dtype_mapping ---


def test_serialize_omits_dtype_entries_that_match_incoming_schema():
    _parent, _window, node = _evaluated_select(
        pl.DataFrame({"id": [1, 2], "name": ["a", "b"]}).lazy()
    )
    content = node.content
    content.changes["dtype_mapping"] = {"id": "Int64", "name": "String"}
    content.apply_changes()

    payload = content.serialize()
    assert payload["changes"]["dtype_mapping"] == {}
    assert [row["dtype"] for row in payload["table_data"]] == ["Int64", "String"]
    # Live state must be untouched by a call that can happen mid-edit.
    assert content.changes["dtype_mapping"] == {"id": "Int64", "name": "String"}


def test_serialize_keeps_only_genuinely_overridden_dtype_entry():
    _parent, _window, node = _evaluated_select(
        pl.DataFrame({"id": [1, 2], "amount": ["10", "20"]}).lazy()
    )
    content = node.content
    content.changes["dtype_mapping"] = {"id": "Int64", "amount": "Int64"}
    content.apply_changes()

    payload = content.serialize()
    assert payload["changes"]["dtype_mapping"] == {"amount": "Int64"}


def test_serialize_writes_dense_when_incom_data_is_none():
    content = SelectContent.__new__(SelectContent)
    content.incom_data = None
    content.table_data = []
    changes = {"dtype_mapping": {"a": "Int64", "b": "String"}}
    assert content._sparse_dtype_mapping(changes) == {"a": "Int64", "b": "String"}


# --- round trip: sparse out, dense back in, behavior unchanged ---


def test_serialize_deserialize_round_trip_reproduces_dense_shape_and_behavior():
    _parent, window, node = _evaluated_select(
        pl.DataFrame({"id": [1, 2], "amount": ["10", "20"]}).lazy()
    )
    content = node.content
    content.changes["dtype_mapping"] = {"id": "Int64", "amount": "Int64"}
    content.apply_changes()
    expected_dense = dict(content.changes["dtype_mapping"])

    payload = content.serialize()
    assert payload["changes"]["dtype_mapping"] != expected_dense

    fresh = _select_node(window.scene)
    fresh.content.deserialize(copy.deepcopy(payload))
    assert fresh.content.changes["dtype_mapping"] == expected_dense

    fresh.content.incom_data = content.incom_data
    fresh.content.incoming_variable = content.incoming_variable
    fresh.content.apply_changes()
    code = fresh.content.get_code()
    assert "pl.col('id').cast" not in code
    assert "pl.col('amount').cast" in code
    assert fresh.content.data.collect_schema()["amount"] == pl.Int64


def test_deserialize_loads_old_dense_payload_unchanged():
    """A pre-this-feature save file (dense dtype_mapping, incl. a real ''
    column name, mirroring savedfiles/I_select.tds) must load unchanged."""
    _parent, window, _node = _evaluated_select(pl.DataFrame({"": [1]}).lazy())
    dense_payload = {
        "table_data": [
            {"checked": True, "text": "", "dtype": "Int64", "rename": ""},
            {"checked": True, "text": "Keyword", "dtype": "String", "rename": ""},
        ],
        "changes": {
            "selected_columns": ["", "Keyword"],
            "rename_mapping": {},
            "dtype_mapping": {"": "Int64", "Keyword": "String"},
            "column_order": ["", "Keyword"],
            "auto_accept_new_columns": True,
        },
    }
    fresh = _select_node(window.scene)
    fresh.content.deserialize(copy.deepcopy(dense_payload))
    assert fresh.content.changes["dtype_mapping"] == {"": "Int64", "Keyword": "String"}
    assert [r.text for r in fresh.content.table_data] == ["", "Keyword"]


# --- pure unit tests of the two new helpers ---


def test_densify_dtype_mapping_backfills_missing_entries_only():
    content = SelectContent.__new__(SelectContent)
    content.table_data = [
        _row("a", checked=True, dtype="Int64"),
        _row("b", checked=True, dtype="String"),
        _row("c", checked=False, dtype="Float64"),
    ]
    content.changes = {"dtype_mapping": {"a": "Int64"}}
    content._densify_dtype_mapping()
    assert content.changes["dtype_mapping"] == {"a": "Int64", "b": "String"}


def test_densify_dtype_mapping_handles_empty_string_column_name():
    content = SelectContent.__new__(SelectContent)
    content.table_data = [_row("", checked=True, dtype="Int64")]
    content.changes = {"dtype_mapping": {}}
    content._densify_dtype_mapping()
    assert content.changes["dtype_mapping"] == {"": "Int64"}


def _row(text, checked, dtype):
    return RowData(checked=checked, text=text, dtype=dtype, rename="")


# --- real undo/redo round trip through a sparse-serialize/densify cycle ---


def test_undo_redo_round_trip_after_dtype_edit():
    _parent, window, node = _evaluated_select(
        pl.DataFrame({"id": ["1", "2"]}).lazy()
    )
    content = node.content
    history = window.scene.history

    _retype_headless(content, {"id": "Int64"})
    assert history.controller.count == 0  # first stamp is the baseline

    _retype_headless(content, {"id": "Float64"})
    assert history.controller.count == 1
    assert content.data.collect_schema()["id"] == pl.Float64

    history.undo()
    APP.processEvents()
    content.apply_changes()
    assert content.data.collect_schema()["id"] == pl.Int64

    history.redo()
    APP.processEvents()
    content.apply_changes()
    assert content.data.collect_schema()["id"] == pl.Float64
