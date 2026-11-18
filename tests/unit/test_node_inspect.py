"""The pure parts of looking at a node's data: resolving it, what runs, stats."""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal

import polars as pl
import pytest

from tests.support.cli import synthetic_workflow
from trigger_designer.core.headless import node_inspect as ni
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.workflow_file import parse_workflow_bytes


def _doc(**kw):
    return parse_workflow_bytes(json.dumps(synthetic_workflow(**kw)).encode(), "wf.tds")


def test_resolve_by_id_title_and_op():
    doc = _doc()
    assert ni.resolve_node(doc, "102")["id"] == 102
    assert ni.resolve_node(doc, "filter")["id"] == 102  # any case
    assert ni.resolve_node(doc, "input.file_output")["id"] == 103


def test_resolve_unknown_lists_the_nodes():
    with pytest.raises(CliError) as exc:
        ni.resolve_node(_doc(), "Nope")
    assert exc.value.td_code == "TD-CLI-020"
    assert "102 = Filter" in exc.value.hint


def test_resolve_ambiguous_asks_for_an_id():
    extra = {
        "id": 104,
        "op": "preparation.filter",
        "title": "Filter",
        "inputs": [{"id": 1041}],
        "outputs": [{"id": 1042}],
        "content": {},
    }
    with pytest.raises(CliError) as exc:
        ni.resolve_node(_doc(extra_nodes=[extra]), "Filter")
    assert "numeric id" in exc.value.hint and "104" in exc.value.hint


def test_upstream_is_the_node_and_what_feeds_it():
    doc = _doc()
    assert ni.upstream_ids(doc, 102) == {101, 102}
    assert ni.upstream_ids(doc, 101) == {101}
    assert ni.upstream_ids(doc, 103) == {101, 102, 103}


def test_upstream_of_an_unknown_node_is_empty():
    assert ni.upstream_ids(_doc(), 999) == set()


def test_a_node_that_writes_a_file_cannot_be_inspected():
    doc = _doc()
    assert ni.check_inspectable(ni.resolve_node(doc, "102")) == "preparation.filter"
    with pytest.raises(CliError) as exc:
        ni.check_inspectable(ni.resolve_node(doc, "103"))
    assert exc.value.td_code == "TD-CLI-021" and exc.value.code == ExitCode.INVALID


def test_a_chart_has_no_table():
    with pytest.raises(CliError):
        ni.check_inspectable({"id": 1, "op": "report.graph", "title": "x"})


def test_jsonable_handles_what_orjson_cannot():
    value = {
        "d": Decimal("1.50"),
        "t": dt.timedelta(hours=1),
        "b": b"\x01\xff",
        "when": dt.datetime(2026, 1, 2, 3, 4),
        "day": dt.date(2026, 1, 2),
        "nan": float("nan"),
        "inf": float("inf"),
        "nested": [(1, 2), {"x": None}],
        "odd": object,
    }
    out = ni.jsonable(value)
    assert out["d"] == "1.50" and out["t"] == "1:00:00" and out["b"] == "01ff"
    assert out["when"] == "2026-01-02T03:04:00" and out["day"] == "2026-01-02"
    assert out["nan"] is None and out["inf"] is None
    assert out["nested"] == [[1, 2], {"x": None}]
    assert isinstance(out["odd"], str)
    json.dumps(out)


def _profile(frame: pl.DataFrame) -> dict:
    return {c["name"]: c for c in ni.profile_frame(frame.lazy())["columns"]}


def test_profile_counts_rows_nulls_and_distinct():
    frame = pl.DataFrame({"a": [1, 2, 2, None], "s": ["x", "x", None, " "]})
    result = ni.profile_frame(frame.lazy())
    assert result["rows"] == 4
    cols = {c["name"]: c for c in result["columns"]}
    assert cols["a"]["nulls"] == 1 and cols["a"]["distinct"] == 2
    assert cols["s"]["nulls"] == 1 and cols["s"]["distinct"] == 2


def test_profile_numbers_get_ranges_and_signs():
    col = _profile(pl.DataFrame({"n": [-2.0, 0.0, 4.0, 6.0]}))["n"]
    assert (col["min"], col["max"], col["sum"]) == (-2.0, 6.0, 8.0)
    assert col["mean"] == 2.0 and col["zeros"] == 1 and col["negatives"] == 1


def test_profile_text_reports_lengths_and_never_a_value():
    col = _profile(pl.DataFrame({"t": ["ab", "abcd", "  ", None]}))["t"]
    assert (col["min_length"], col["max_length"], col["blanks"]) == (2, 4, 1)
    assert not {"min", "max", "top", "values", "sample"} & set(col)


def test_profile_dates_booleans_and_nested_columns():
    frame = pl.DataFrame(
        {
            "d": [dt.date(2026, 1, 1), dt.date(2026, 3, 1)],
            "ok": [True, False],
            "nest": [[1], [2]],
        }
    )
    cols = _profile(frame)
    assert (cols["d"]["min"], cols["d"]["max"]) == ("2026-01-01", "2026-03-01")
    assert cols["ok"]["true_count"] == 1
    assert "distinct" not in cols["nest"] and cols["nest"]["nulls"] == 0


def test_profile_of_an_empty_table():
    result = ni.profile_frame(pl.DataFrame({"a": pl.Series([], dtype=pl.Int64)}).lazy())
    assert result["rows"] == 0
    assert result["columns"][0]["min"] is None


def test_schema_and_head_rows():
    frame = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]}).lazy()
    assert ni.schema_of_frame(frame) == [
        {"name": "a", "dtype": "Int64"},
        {"name": "b", "dtype": "String"},
    ]
    assert ni.head_rows(frame, 2) == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
