"""Item shapes and examples in ``node_items/prep_b.py`` (the preparation group b).

Each shape is checked against the op's real settings schema. Each example runs
through the node's own ``run_node`` on a small frame, and its result is checked.
"""

from __future__ import annotations

import ast
import importlib
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from trigger_designer.core.authoring.validate import validate_value
from trigger_designer.core.headless import node_spec as ns
from trigger_designer.core.headless.node_items import prep_b
from trigger_designer.core.shaping import date_helper, find_replace

pytestmark = pytest.mark.unit

MY_OPS = (
    "preparation.normalize_columns",
    "preparation.record_id",
    "preparation.select_records",
    "preparation.find_replace",
    "preparation.date_helper",
    "preparation.multi_field_formula",
)


def _contains(actual: Any, expected: Any) -> bool:
    """``expected`` is part of ``actual``: dicts match key by key, the rest exactly."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _contains(actual[key], value)
            for key, value in expected.items()
        )
    return actual == expected


def _frame(extra: dict[str, Any] | None = None) -> pl.DataFrame:
    columns: dict[str, Any] = {
        "Amount": pl.Series([5, 20000, 30000], dtype=pl.Int64),
        "InvoiceNo": pl.Series(["a", "a", "b"], dtype=pl.String),
        "Vendor": pl.Series(["x", "y", "y"], dtype=pl.String),
        "Date": pl.Series(
            [date(2026, 11, 16), date(2026, 11, 21), date(2026, 11, 30)],
            dtype=pl.Date,
        ),
    }
    columns.update(extra or {})
    return pl.DataFrame(columns)


def _run(op: str, frame: pl.DataFrame) -> list[pl.DataFrame]:
    """The op's example through its own ``run_node``, every output collected."""
    source = ns.SETTINGS_SOURCES[op].source
    assert source is not None
    core = importlib.import_module(source.partition(":")[0])
    outs = core.run_node([frame.lazy()], ns.EXAMPLES[op])
    return [out.collect() for out in outs]


def _find_replace_modes_in_source() -> list[str]:
    """The tuple ``validate_rules`` checks a rule's mode against (no named constant)."""
    tree = ast.parse(Path(find_replace.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Compare)
            and isinstance(node.ops[0], ast.NotIn)
            and isinstance(node.left, ast.Subscript)
            and isinstance(node.left.slice, ast.Constant)
            and node.left.slice.value == "mode"
        ):
            return list(ast.literal_eval(node.comparators[0]))
    raise AssertionError("validate_rules no longer checks a rule mode against a tuple")


def test_group_covers_exactly_its_ops():
    assert set(prep_b.EXAMPLES) == set(MY_OPS)
    assert {op for op, _ in prep_b.PROPS} <= set(MY_OPS)


def test_module_holds_only_plain_literals():
    tree = ast.parse(Path(prep_b.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert imported <= {"__future__", "typing"}
    tables = {
        node.target.id: node.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert set(tables) == {"PROPS", "EXAMPLES"}
    for value in tables.values():
        ast.literal_eval(value)  # raises unless the table is a plain literal


@pytest.mark.parametrize("op, key", sorted(prep_b.PROPS))
def test_each_shape_is_part_of_its_setting(op, key):
    prop = ns.describe_op(op)["settings"]["schema"]["properties"][key]
    assert _contains(prop, prep_b.PROPS[(op, key)])


@pytest.mark.parametrize("op", MY_OPS)
def test_every_list_setting_says_what_its_items_are(op):
    schema = ns.describe_op(op)["settings"]["schema"]
    for key, prop in schema["properties"].items():
        if prop.get("type") == "array":
            assert prop.get("items"), (op, key)


@pytest.mark.parametrize("op", MY_OPS)
def test_example_fits_the_settings_schema(op):
    schema = ns.describe_op(op)["settings"]["schema"]
    example = prep_b.EXAMPLES[op]
    # validate_value ignores keys the schema does not name, so check them here.
    assert set(example) <= set(schema["properties"])
    assert validate_value(schema, example, "settings") is None


def test_normalize_example_renames_only_the_selected_column():
    [out] = _run(
        "preparation.normalize_columns",
        _frame(
            {
                "Vendor Name": ["Acme", "Beta", "Beta"],
                "Invoice Date": ["2026-11-16", "2026-11-21", "2026-11-30"],
            }
        ),
    )
    assert "Vendor_Name" in out.columns
    assert "Vendor Name" not in out.columns
    assert "Invoice Date" in out.columns  # not selected, so the name is kept


def test_record_id_example_numbers_each_vendor_by_amount():
    [out] = _run("preparation.record_id", _frame())
    assert out.columns[0] == "RecordID"
    # Rows keep their order; within Vendor y the 30000 row is numbered first.
    assert out["RecordID"].to_list() == [1, 2, 1]


def test_select_records_example_keeps_the_largest_amount_per_vendor():
    selected, rest = _run("preparation.select_records", _frame())
    assert selected["Amount"].to_list() == [30000, 5]  # ranked, largest first
    assert rest["Amount"].to_list() == [20000]
    assert selected.columns == _frame().columns


def test_find_replace_example_rewrites_the_matching_vendor():
    [out] = _run("preparation.find_replace", _frame())
    assert out["Vendor"].to_list() == ["x", "Y-Corp", "Y-Corp"]
    assert out.columns == _frame().columns


def test_date_helper_example_adds_one_column_per_calculation():
    frame = _frame(
        {
            "PaidDate": pl.Series(
                [date(2026, 11, 20), date(2026, 11, 21), date(2026, 12, 10)],
                dtype=pl.Date,
            )
        }
    )
    [out] = _run("preparation.date_helper", frame)
    assert out["Weekday"].to_list() == ["Monday", "Saturday", "Monday"]
    assert out["DaysToPay"].to_list() == [4, 0, 10]
    assert out["DueDate"].cast(pl.Date).to_list() == [
        date(2026, 12, 16),
        date(2026, 12, 21),
        date(2026, 12, 30),
    ]


def test_multi_field_formula_example_uppercases_both_columns():
    [out] = _run("preparation.multi_field_formula", _frame())
    assert out["InvoiceNo"].to_list() == ["A", "A", "B"]
    assert out["Vendor"].to_list() == ["X", "Y", "Y"]
    assert out.columns == _frame().columns


def test_date_helper_op_enum_is_the_core_op_tuple():
    items = prep_b.PROPS[("preparation.date_helper", "ops")]["items"]
    assert items["properties"]["op"]["enum"] == list(date_helper.OPS)


def test_find_replace_mode_enum_is_the_tuple_the_core_checks():
    items = prep_b.PROPS[("preparation.find_replace", "rules")]["items"]
    assert items["properties"]["mode"]["enum"] == _find_replace_modes_in_source()
