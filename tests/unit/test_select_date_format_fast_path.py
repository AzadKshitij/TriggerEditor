#!/usr/bin/env python3
"""bulk_auto_detect already samples data to find a matching strptime format
for a Date column, then discarded it -- leaving the actual cast to blindly
coalesce across every format _date_parse_formats()/_datetime_parse_formats()
know (~85 strptime attempts per column, duplicated across the live-eval and
codegen paths). RowData.date_format lets the detector's finding survive to
cast time, so the common case (one consistent format) pays for one strptime
attempt instead of the full brute-force list -- while any column with no
known format (never auto-detected, or the format was invalidated by a
dtype/manual edit) keeps the exact old fallback behavior.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import datetime as dt

import polars as pl
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.nodes.Preparation.select import SelectContent

APP = QApplication.instance() or QApplication([])


def _evaluated_select(df):
    """A Select node with incom_data set and its dock built, so table_data
    is populated and bulk ops (which need table_widget) work. Returns
    (parent, window, node)."""
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    cls = get_class_from_opcode(PreparationNodes.SELECT, NodeTypes.PREPARATION)
    node = cls(window.scene)
    window.scene.nodes.append(node)
    content = node.content
    content.incom_data = df
    content.incoming_variable = "var_in"
    host = QWidget()
    content.create_layout(QVBoxLayout(host))
    node._host = host  # keep alive for the test's lifetime
    return parent, window, node


# --- _infer_column_dtype returns the matched format ---


def test_infer_column_dtype_returns_matched_format_for_consistent_date_column():
    content = SelectContent.__new__(SelectContent)
    dtype, fmt = content._infer_column_dtype(
        "col", ["2024-01-01", "2024-06-15", "2024-12-31"]
    )
    assert dtype == "Date"
    assert fmt == "%Y-%m-%d"


def test_infer_column_dtype_returns_none_format_for_non_date_dtype():
    content = SelectContent.__new__(SelectContent)
    dtype, fmt = content._infer_column_dtype("col", ["1", "2", "3"])
    assert dtype == "Int64"
    assert fmt is None


def test_infer_column_dtype_returns_none_format_when_unparseable():
    content = SelectContent.__new__(SelectContent)
    dtype, fmt = content._infer_column_dtype("col", ["not", "a", "date"])
    assert dtype == "String"
    assert fmt is None


# --- bulk_auto_detect / bulk_reset_dtypes / manual edit manage date_format ---


def test_bulk_auto_detect_records_date_format_only_on_date_rows():
    _parent, _window, node = _evaluated_select(
        pl.DataFrame(
            {
                "day": ["2024-01-01", "2024-06-15"],
                "amount": ["10", "20"],
            }
        ).lazy()
    )
    content = node.content
    content.bulk_auto_detect(selected_only=False)
    by_text = {row.text: row for row in content.table_data}
    assert by_text["day"].dtype == "Date"
    assert by_text["day"].date_format == "%Y-%m-%d"
    assert by_text["amount"].dtype == "Int64"
    assert by_text["amount"].date_format == ""


def test_bulk_reset_dtypes_clears_date_format():
    _parent, _window, node = _evaluated_select(
        pl.DataFrame({"day": ["2024-01-01", "2024-06-15"]}).lazy()
    )
    content = node.content
    content.bulk_auto_detect(selected_only=False)
    assert content.table_data[0].date_format == "%Y-%m-%d"
    content.bulk_reset_dtypes(selected_only=False)
    assert content.table_data[0].dtype == "String"
    assert content.table_data[0].date_format == ""


def test_manual_dtype_edit_clears_stale_date_format():
    _parent, _window, node = _evaluated_select(
        pl.DataFrame({"day": ["2024-01-01", "2024-06-15"]}).lazy()
    )
    content = node.content
    content.bulk_auto_detect(selected_only=False)
    assert content.table_data[0].date_format == "%Y-%m-%d"

    index = content.table_widget.index(0, 2)
    content.table_widget.setData(index, "Datetime", Qt.ItemDataRole.EditRole)
    assert content.table_data[0].dtype == "Datetime"
    assert content.table_data[0].date_format == ""


# --- fast path vs full path: correctness and size ---


def test_fast_path_expr_matches_full_path_result_for_consistent_format():
    content = SelectContent.__new__(SelectContent)
    df = pl.DataFrame({"day": ["2024-01-01", "2024-06-15", "2024-12-31"]})

    full = df.with_columns(content._build_dtype_conversion_expr("day", "Date"))
    fast = df.with_columns(
        content._build_dtype_conversion_expr("day", "Date", "%Y-%m-%d")
    )
    assert (
        full["day"].to_list()
        == fast["day"].to_list()
        == [
            dt.date(2024, 1, 1),
            dt.date(2024, 6, 15),
            dt.date(2024, 12, 31),
        ]
    )


def test_fast_path_code_uses_one_strptime_call_instead_of_the_full_list():
    content = SelectContent.__new__(SelectContent)
    full_code = content._build_dtype_conversion_code("day", "Date")
    fast_code = content._build_dtype_conversion_code("day", "Date", "%Y-%m-%d")

    assert full_code.count("strptime") > 50  # the brute-force list, unchanged
    assert fast_code.count("strptime") == 1
    assert "%Y-%m-%d" in fast_code
    assert len(fast_code) < len(full_code) / 10


def test_fast_path_still_falls_back_when_known_format_does_not_match():
    """A stale/wrong cached format must never produce a worse result than
    the full path -- the cheap to_date()/raw-cast fallbacks after it catch
    values the specific format misses."""
    content = SelectContent.__new__(SelectContent)
    df = pl.DataFrame({"day": ["31/01/2024"]})  # doesn't match %Y-%m-%d
    fast = df.with_columns(
        content._build_dtype_conversion_expr("day", "Date", "%Y-%m-%d")
    )
    assert fast["day"].to_list() == [dt.date(2024, 1, 31)]


# --- full-stack wiring: apply_changes / get_code use the cached format ---


def test_apply_changes_produces_correct_dates_via_cached_format():
    _parent, _window, node = _evaluated_select(
        pl.DataFrame({"day": ["2024-01-01", "2024-06-15"]}).lazy()
    )
    content = node.content
    content.bulk_auto_detect(selected_only=False)
    content.apply_changes()
    assert content.data.collect()["day"].to_list() == [
        dt.date(2024, 1, 1),
        dt.date(2024, 6, 15),
    ]


def test_get_code_shrinks_and_stays_correct_when_format_is_known():
    _parent, _window, node = _evaluated_select(
        pl.DataFrame({"day": ["2024-01-01", "2024-06-15"]}).lazy()
    )
    content = node.content
    content.bulk_auto_detect(selected_only=False)
    content.apply_changes()

    code = content.get_code()
    assert code.count("strptime") == 1

    globs = {"pl": pl, content.incoming_variable: node.content.incom_data}
    exec(code, globs)
    result = globs[content.variable_name]
    assert result.collect()["day"].to_list() == [
        dt.date(2024, 1, 1),
        dt.date(2024, 6, 15),
    ]


# --- persistence: serialize/deserialize and undo/redo ---


def test_date_format_survives_serialize_deserialize_round_trip():
    _parent, _window, node = _evaluated_select(
        pl.DataFrame({"day": ["2024-01-01", "2024-06-15"]}).lazy()
    )
    content = node.content
    content.bulk_auto_detect(selected_only=False)
    payload = content.serialize()

    fresh = SelectContent.__new__(SelectContent)
    fresh.node = node
    fresh.history = content.history
    fresh.deserialize(payload)
    assert fresh.table_data[0].date_format == "%Y-%m-%d"


def test_date_format_survives_undo_redo_round_trip():
    _parent, window, node = _evaluated_select(
        pl.DataFrame({"day": ["2024-01-01", "2024-06-15"]}).lazy()
    )
    content = node.content
    history = window.scene.history

    # First stamp is the baseline, not an undo step (see
    # test_select_missing_columns.py::test_undo_redo_round_trip_through_missing_column_state).
    content.table_data[0].rename = "unrelated"
    content.handleDataChanged(content.table_widget.getData())
    assert history.controller.count == 0

    content.bulk_auto_detect(selected_only=False)
    assert history.controller.count == 1
    assert content.table_data[0].date_format == "%Y-%m-%d"

    history.undo()
    APP.processEvents()
    assert content.table_data[0].date_format == ""

    history.redo()
    APP.processEvents()
    assert content.table_data[0].date_format == "%Y-%m-%d"
