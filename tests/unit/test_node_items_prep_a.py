"""Item shapes and examples of file input and the first preparation nodes.

The data behind them lives in ``node_items/prep_a.py``; these tests check it
through the public ``describe_op`` export and the nodes' own ``run_node``.
"""

from __future__ import annotations

import importlib
from datetime import date

import polars as pl
import pytest

from trigger_designer.core.authoring.validate import validate_value
from trigger_designer.core.headless import node_spec as ns
from trigger_designer.core.headless.node_items import prep_a
from trigger_designer.core.headless.node_spec import describe_op
from trigger_designer.core.shaping import aggregate

pytestmark = pytest.mark.unit

#: Every op this group describes, including those that already had an example.
OPS = (
    "input.file_input",
    "preparation.cleansing",
    "preparation.formula",
    "preparation.groupby",
    "preparation.select",
    "preparation.sort",
    "preparation.unique",
)

#: Ops whose example must fit the schema: this group's own, plus existing ones.
EXAMPLE_OPS = sorted(set(prep_a.EXAMPLES) | (set(OPS) & set(ns.EXAMPLES)))


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "Amount": pl.Series([5, 20000, 30000], dtype=pl.Int64),
            "InvoiceNo": ["a", "a", "b"],
            "Vendor": ["x", "y", "y"],
            "Date": pl.Series(
                [date(2026, 1, 5), date(2026, 1, 9), date(2026, 2, 1)],
                dtype=pl.Date,
            ),
        }
    )


def _run(op: str) -> list[pl.DataFrame]:
    """The node's own ``run_node`` on its example, with every output collected."""
    source = ns.SETTINGS_SOURCES[op].source
    assert source is not None, op
    module = importlib.import_module(source.partition(":")[0])
    outs = module.run_node([_frame().lazy()], ns.EXAMPLES[op])
    return [out.collect() for out in outs]


@pytest.mark.parametrize(("op", "setting"), sorted(prep_a.PROPS))
def test_props_reach_the_public_schema(op, setting):
    prop = describe_op(op)["settings"]["schema"]["properties"][setting]
    for key, wanted in prep_a.PROPS[(op, setting)].items():
        assert prop[key] == wanted, (op, setting, key)


@pytest.mark.parametrize("op", OPS)
def test_every_list_setting_describes_its_items(op):
    properties = describe_op(op)["settings"]["schema"]["properties"]
    lists = [key for key, prop in properties.items() if prop.get("type") == "array"]
    assert lists, f"{op} has no list setting to check"
    for key in lists:
        assert properties[key].get("items"), f"{op}.{key} has no item schema"


@pytest.mark.parametrize("op", EXAMPLE_OPS)
def test_example_fits_its_settings_schema(op):
    settings = describe_op(op)["settings"]
    assert settings["example_is_default"] is False, op
    assert validate_value(settings["schema"], settings["example"], "settings") is None


def test_cleansing_example_upper_cases_only_the_chosen_column():
    [out] = _run("preparation.cleansing")
    assert out.columns == ["Amount", "InvoiceNo", "Vendor", "Date"]
    assert out["Vendor"].to_list() == ["X", "Y", "Y"]
    assert out["InvoiceNo"].to_list() == ["a", "a", "b"]  # not selected, untouched


def test_formula_example_adds_one_column_doubling_amount():
    [out] = _run("preparation.formula")
    assert out.columns == ["Amount", "InvoiceNo", "Vendor", "Date", "Amount_x2"]
    assert out["Amount_x2"].to_list() == [10, 40000, 60000]


def test_groupby_example_totals_and_counts_each_vendor():
    [out] = _run("preparation.groupby")
    assert out.columns == ["Vendor", "total", "invoices"]
    assert out.rows() == [("x", 5, 1), ("y", 50000, 2)]


def test_groupby_action_enum_is_the_real_action_list():
    properties = describe_op("preparation.groupby")["settings"]["schema"]["properties"]
    action = properties["actions"]["items"]["properties"]["action"]
    assert action["enum"] == aggregate.AGGREGATION_FUNCTIONS
