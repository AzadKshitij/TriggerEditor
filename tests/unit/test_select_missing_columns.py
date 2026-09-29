#!/usr/bin/env python3
"""A column disappearing from the upstream schema must be retained (its
rename/dtype/checked state preserved) and flagged is_missing, not silently
dropped -- and must never leak into the execution-facing dicts that
apply_changes()/get_code() rely on already being pruned to live columns.
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


def _wired_pair(df):
    """stub -> up -> down, both evaluated. Returns refs dict."""
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    scene = window.scene
    stub = _stub_node(scene, df)
    up = _select_node(scene)
    Edge(scene, stub.outputs[0], up.inputs[0])
    up.eval()
    down = _select_node(scene)
    Edge(scene, up.outputs[0], down.inputs[0])
    down.eval()
    APP.processEvents()
    return {"parent": parent, "window": window, "stub": stub, "up": up, "down": down}


def _rename_headless(content, mapping):
    """Rename via the same path the table widget uses (row edit + signal)."""
    for row in content.table_data:
        if row.text in mapping:
            row.rename = mapping[row.text]
    payload = [(row.text, row.dtype, row.rename) for row in content.table_data]
    content.handleDataChanged(payload)
    APP.processEvents()


def test_column_disappearing_is_retained_and_flagged_missing():
    refs = _wired_pair(pl.DataFrame({"id": [1, 2], "name": ["a", "b"]}).lazy())
    content = refs["up"].content
    _rename_headless(content, {"name": "full_name"})
    assert [r.text for r in content.table_data] == ["id", "name"]

    content.incom_data = pl.DataFrame({"id": [1, 2]}).lazy()
    content.apply_changes()

    assert len(content.table_data) == 2
    name_row = next(r for r in content.table_data if r.text == "name")
    assert name_row.is_missing is True
    assert name_row.rename == "full_name"
    assert name_row.checked is True
    id_row = next(r for r in content.table_data if r.text == "id")
    assert id_row.is_missing is False


def test_missing_column_excluded_from_execution_facing_changes():
    refs = _wired_pair(pl.DataFrame({"id": [1, 2], "name": ["a", "b"]}).lazy())
    content = refs["up"].content
    _rename_headless(content, {"name": "full_name"})

    content.incom_data = pl.DataFrame({"id": [1, 2]}).lazy()
    content.apply_changes()

    assert "name" not in content.changes["selected_columns"]
    assert "name" not in content.changes["rename_mapping"]
    assert "name" not in content.changes["dtype_mapping"]

    code = content.get_code()
    assert "name" not in code
    assert "full_name" not in code
    assert list(content.data.collect_schema().names()) == ["id"]


def test_missing_column_reappearing_clears_flag_and_reapplies_settings():
    refs = _wired_pair(pl.DataFrame({"id": [1, 2], "name": ["a", "b"]}).lazy())
    content = refs["up"].content
    _rename_headless(content, {"name": "full_name"})

    content.incom_data = pl.DataFrame({"id": [1, 2]}).lazy()
    content.apply_changes()
    assert next(r for r in content.table_data if r.text == "name").is_missing is True

    content.incom_data = pl.DataFrame({"id": [1, 2], "name": ["a", "b"]}).lazy()
    content.apply_changes()

    name_row = next(r for r in content.table_data if r.text == "name")
    assert name_row.is_missing is False
    assert "name" in content.changes["rename_mapping"]
    assert content.changes["rename_mapping"]["name"] == "full_name"
    assert "full_name" in list(content.data.collect_schema().names())


def test_undo_redo_round_trip_through_missing_column_state():
    refs = _wired_pair(pl.DataFrame({"id": [1, 2], "name": ["a", "b"]}).lazy())
    up = refs["up"]
    history = refs["window"].scene.history

    # First stamp is the baseline, not an undo step (matches the established
    # pattern in test_select_rename_propagation.py::test_undo_redo_restore_renamed_order).
    _rename_headless(up.content, {"id": "identifier"})
    assert history.controller.count == 0

    _rename_headless(up.content, {"name": "full_name"})
    assert history.controller.count == 1

    # Column goes missing (not via a table edit, so no new history step).
    up.content.incom_data = pl.DataFrame({"id": [1, 2]}).lazy()
    up.content.apply_changes()
    assert history.controller.count == 1
    name_row = next(r for r in up.content.table_data if r.text == "name")
    assert name_row.is_missing is True
    assert name_row.rename == "full_name"

    history.undo()
    APP.processEvents()
    # Undo restores configs; downstream recomputes on the next evaluation
    # (the scene does not cascade evals after a restore, and reconciling
    # missing-state against the live schema is deferred to that real
    # evaluation rather than attempted from the restore's own, possibly
    # stale, view of the schema -- see _reconcile_schema's "restoring"
    # branch docstring).
    up.content.apply_changes()
    name_row = next(r for r in up.content.table_data if r.text == "name")
    assert name_row.rename == ""
    assert name_row.is_missing is True

    history.redo()
    APP.processEvents()
    up.content.apply_changes()
    name_row = next(r for r in up.content.table_data if r.text == "name")
    assert name_row.rename == "full_name"
    assert name_row.is_missing is True


def test_serialize_deserialize_round_trips_is_missing():
    refs = _wired_pair(pl.DataFrame({"id": [1, 2], "name": ["a", "b"]}).lazy())
    content = refs["up"].content
    content.incom_data = pl.DataFrame({"id": [1, 2]}).lazy()
    content.apply_changes()
    assert next(r for r in content.table_data if r.text == "name").is_missing is True

    payload = content.serialize()
    fresh = _select_node(refs["window"].scene)
    fresh.content.deserialize(copy.deepcopy(payload))
    fresh_name_row = next(r for r in fresh.content.table_data if r.text == "name")
    assert fresh_name_row.is_missing is True

    # Old-style payload predating this field must still load (defaults False).
    old_payload = copy.deepcopy(payload)
    for row in old_payload["table_data"]:
        row.pop("is_missing", None)
    fresh2 = _select_node(refs["window"].scene)
    fresh2.content.deserialize(old_payload)
    assert all(not getattr(r, "is_missing", False) for r in fresh2.content.table_data)
