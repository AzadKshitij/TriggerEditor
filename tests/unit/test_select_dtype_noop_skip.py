#!/usr/bin/env python3
"""A Select node must not re-cast a column that is already the target dtype.

Chaining Select -> Select -> Select with the same dtype_mapping (e.g. from
auto-detect) previously re-emitted an identical, wasted cast on every hop --
for Date/Datetime targets this re-ran the expensive strptime/coalesce parse
on data that was already correctly typed.
"""

import datetime as dt
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


# --- _dtype_matches (pure, no Qt state needed) ---


def test_dtype_matches_true_for_parametrized_datetime_against_bare_target():
    content = SelectContent.__new__(SelectContent)
    assert content._dtype_matches(pl.Datetime(time_unit="us"), "Datetime") is True


def test_dtype_matches_false_for_missing_column():
    content = SelectContent.__new__(SelectContent)
    assert content._dtype_matches(None, "Int64") is False


def test_dtype_matches_false_for_unrecognized_target_string():
    content = SelectContent.__new__(SelectContent)
    assert content._dtype_matches(pl.Int64, "NotARealType") is False


def test_dtype_matches_false_for_different_base_type():
    content = SelectContent.__new__(SelectContent)
    assert content._dtype_matches(pl.String, "Int64") is False


# --- apply_changes()/get_code() skip an already-correct dtype ---


def test_get_code_omits_with_columns_when_all_dtypes_already_match():
    _parent, _window, node = _evaluated_select(pl.DataFrame({"id": [1, 2, 3]}).lazy())
    content = node.content
    content.changes["dtype_mapping"] = {"id": "Int64"}
    content.apply_changes()

    code = content.get_code()
    assert "with_columns" not in code
    assert content.data.collect().get_column("id").to_list() == [1, 2, 3]


def test_get_code_still_casts_when_incoming_dtype_differs():
    _parent, _window, node = _evaluated_select(
        pl.DataFrame({"id": ["1", "2", "3"]}).lazy()
    )
    content = node.content
    content.changes["dtype_mapping"] = {"id": "Int64"}
    content.apply_changes()

    code = content.get_code()
    assert "with_columns" in code
    assert "pl.Int64" in code
    assert content.data.collect_schema()["id"] == pl.Int64
    assert content.data.collect().get_column("id").to_list() == [1, 2, 3]


def test_get_code_partial_skip_only_casts_the_mismatched_column():
    _parent, _window, node = _evaluated_select(
        pl.DataFrame({"id": [1, 2], "amount": ["10", "20"]}).lazy()
    )
    content = node.content
    content.changes["dtype_mapping"] = {"id": "Int64", "amount": "Int64"}
    content.apply_changes()

    code = content.get_code()
    assert code.count("with_columns") == 1
    assert "pl.col('id').cast" not in code
    assert "pl.col('amount').cast" in code
    assert content.data.collect_schema()["amount"] == pl.Int64
    assert content.data.collect().get_column("amount").to_list() == [10, 20]


# --- the expensive Date/Datetime chain case (the motivating scenario) ---


def _date_chain():
    """stub -> up -> down, both with dtype_mapping={"day": "Date"} set before
    their first eval (as a loaded workflow would already have it configured),
    both evaluated once. Returns (parent, window, up, down)."""
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    scene = window.scene
    stub = _stub_node(
        scene, pl.DataFrame({"day": ["2024-01-01", "2024-02-15"]}).lazy()
    )
    up = _select_node(scene)
    Edge(scene, stub.outputs[0], up.inputs[0])
    up.content.changes["dtype_mapping"] = {"day": "Date"}
    up.eval()

    down = _select_node(scene)
    Edge(scene, up.outputs[0], down.inputs[0])
    down.content.changes["dtype_mapping"] = {"day": "Date"}
    down.eval()
    APP.processEvents()
    return parent, window, up, down


def test_downstream_select_skips_date_recast_after_upstream_already_cast():
    _parent, _window, up, down = _date_chain()
    assert up.content.data.collect_schema()["day"] == pl.Date

    code = down.content.get_code()
    assert "strptime" not in code
    assert "coalesce" not in code
    assert down.content.data.collect_schema()["day"] == pl.Date
    assert down.content.data.collect().get_column("day").to_list() == [
        dt.date(2024, 1, 1),
        dt.date(2024, 2, 15),
    ]


def test_upstream_select_still_parses_date_from_string_source():
    """Regression guard: the skip must not fire when a real parse is needed."""
    _parent, _window, up, _down = _date_chain()

    assert "strptime" in up.content.get_code()
