"""Item shapes and examples for the join group (``node_items/join.py``).

``node_spec`` merges those tables into each op's settings schema, so the shapes
are checked through the same export an agent reads (``describe_op``). The
examples are also run through each node's own ``run_node``: an example that
drifts from the core fails here rather than in a harness.
"""

from __future__ import annotations

import copy
import importlib

import polars as pl
import pytest

from trigger_designer.core.authoring.validate import validate_value
from trigger_designer.core.headless import node_spec as ns
from trigger_designer.core.headless.node_items import join as group

pytestmark = pytest.mark.unit

#: Every op this group describes. join.union is covered for its shape and for
#: its existing example, but it is not run here: its column map is executed by
#: the Qt widget, so there is no headless ``run_node`` to call.
GROUP_OPS = ("join.join", "join.union", "join.reconcile", "join.fuzzy_match")


def _left() -> pl.LazyFrame:
    return pl.DataFrame(
        {
            "InvoiceNo": ["a", "b", "c"],
            "Amount": pl.Series([5, 20000, 30000], dtype=pl.Int64),
            "Vendor": ["Acme Ltd", "Birch Supply", "Cedar Co"],
        }
    ).lazy()


def _right() -> pl.LazyFrame:
    return pl.DataFrame(
        {
            "InvoiceNo": ["a", "b", "d"],
            "Paid": pl.Series([1, 2, 3], dtype=pl.Int64),
        }
    ).lazy()


def _suppliers() -> pl.LazyFrame:
    """Right side for the fuzzy example: it compares text, so it needs a text
    column that the shared right frame does not have."""
    return pl.DataFrame(
        {
            "InvoiceNo": ["a", "b", "d"],
            "Paid": pl.Series([1, 2, 3], dtype=pl.Int64),
            "Supplier": ["ACME LIMITED", "Birch Supplies", "Dune Ltd"],
        }
    ).lazy()


def _run(op: str, *frames: pl.LazyFrame) -> list[pl.LazyFrame]:
    """The op's own ``run_node`` on its example (a copy, so the table is never
    mutated)."""
    source = ns.SETTINGS_SOURCES[op].source
    assert source is not None, op
    module = importlib.import_module(source.partition(":")[0])
    return module.run_node(list(frames), copy.deepcopy(ns.EXAMPLES[op]))


def _arrays_without_items(schema: dict, path: str = "") -> list[str]:
    """Paths of array schemas, at any depth, that do not say what their items are."""
    found = []
    if schema.get("type") == "array" and not schema.get("items"):
        found.append(path or "<root>")
    for key, prop in (schema.get("properties") or {}).items():
        found += _arrays_without_items(prop, f"{path}.{key}" if path else key)
    if isinstance(schema.get("items"), dict):
        found += _arrays_without_items(schema["items"], f"{path}[]")
    return found


def _has_enum(node: object) -> bool:
    if isinstance(node, dict):
        return "enum" in node or any(_has_enum(value) for value in node.values())
    return False


@pytest.mark.parametrize("op, key", sorted(group.PROPS))
def test_props_reach_the_exported_schema(op, key):
    prop = ns.describe_op(op)["settings"]["schema"]["properties"][key]
    fragment = group.PROPS[(op, key)]
    assert {name: prop.get(name) for name in fragment} == fragment


@pytest.mark.parametrize("op", GROUP_OPS)
def test_every_array_says_what_its_items_are(op):
    schema = ns.describe_op(op)["settings"]["schema"]
    assert _arrays_without_items(schema) == []


@pytest.mark.parametrize("op", [op for op in GROUP_OPS if op in ns.EXAMPLES])
def test_examples_validate_against_the_settings_schema(op):
    schema = ns.settings_schema(op)
    assert validate_value(schema, ns.EXAMPLES[op], "settings") is None


def test_the_validator_enforces_item_types():
    schema = ns.settings_schema("join.join")
    wrong = {"mapping_data": [{"left_column": 5, "right_column": "InvoiceNo"}]}
    assert validate_value(schema, wrong, "settings") is not None


def test_join_example_keeps_matched_rows_and_the_rest_on_each_side():
    left_only, joined, right_only = (
        out.collect() for out in _run("join.join", _left(), _right())
    )
    assert joined.columns == ["InvoiceNo", "Amount", "Vendor", "Paid"]
    assert joined.sort("InvoiceNo").rows() == [
        ("a", 5, "Acme Ltd", 1),
        ("b", 20000, "Birch Supply", 2),
    ]
    assert left_only.columns == ["InvoiceNo", "Amount", "Vendor"]
    assert left_only["InvoiceNo"].to_list() == ["c"]
    assert right_only.columns == ["InvoiceNo", "Paid"]
    assert right_only["InvoiceNo"].to_list() == ["d"]


def test_reconcile_example_matches_on_invoice_number():
    matched, left_open, right_open, summary = (
        out.collect() for out in _run("join.reconcile", _left(), _right())
    )
    assert matched.columns == [
        "Match_ID",
        "Match_Status",
        "InvoiceNo",
        "Amount",
        "Vendor",
        "InvoiceNo_right",
        "Paid",
    ]
    assert sorted(matched["InvoiceNo"].to_list()) == ["a", "b"]
    assert left_open["InvoiceNo"].to_list() == ["c"]
    assert left_open["Unmatched_Reason"].to_list() == ["No candidate with the same key"]
    assert right_open["InvoiceNo"].to_list() == ["d"]
    counts = summary.row(0, named=True)
    assert counts["Matched_Groups"] == 2
    assert (counts["Left_Unmatched_Rows"], counts["Right_Unmatched_Rows"]) == (1, 1)


def test_fuzzy_example_pairs_spelling_variants_and_leaves_the_rest():
    matched, left_open, right_open = (
        out.collect() for out in _run("join.fuzzy_match", _left(), _suppliers())
    )
    assert matched["Vendor"].to_list() == ["Acme Ltd", "Birch Supply"]
    assert matched["Supplier"].to_list() == ["ACME LIMITED", "Birch Supplies"]
    assert all(score >= 0.85 for score in matched["Match_Score"].to_list())
    assert left_open["Vendor"].to_list() == ["Cedar Co"]
    assert right_open["Supplier"].to_list() == ["Dune Ltd"]


def test_no_enum_without_a_named_core_constant():
    """An enum must copy a constant that core code names, and the test pins it to
    that constant. This group has none: the L/R source of a selected column is a
    literal comparison in core/shaping/join.py, so it is described in words."""
    assert not any(_has_enum(fragment) for fragment in group.PROPS.values())
