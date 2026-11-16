"""Item shapes and examples of the Transform list settings.

The data lives in ``node_items/transform.py``; these tests check it through the
public ``describe_op`` export and each node's own runner on a small frame.
"""

from __future__ import annotations

import importlib
from datetime import date

import polars as pl
import pytest

from trigger_designer.core.authoring.validate import validate_value
from trigger_designer.core.headless import node_spec as ns
from trigger_designer.core.headless.node_items import transform
from trigger_designer.core.headless.node_spec import describe_op
from trigger_designer.core.shaping import window

pytestmark = pytest.mark.unit

#: Every op this group describes.
OPS = (
    "transform.running_total",
    "transform.transpose",
    "transform.pivot",
    "transform.unpivot",
    "transform.window",
)

#: The function each node executes: the ``RUNNER`` of its Qt wrapper. Pivot and
#: Unpivot name their own (``qt/widgets/nodes/Transform/pivot.py:20``,
#: ``unpivot.py:20``); the others use ``run_node``.
RUNNERS = {
    "transform.running_total": "run_node",
    "transform.transpose": "run_node",
    "transform.pivot": "run_pivot",
    "transform.unpivot": "run_unpivot",
    "transform.window": "run_node",
}


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "Amount": pl.Series([5, 20000, 30000], dtype=pl.Int64),
            "InvoiceNo": ["a", "a", "b"],
            "Vendor": ["x", "y", "y"],
            "Date": pl.Series(
                [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)],
                dtype=pl.Date,
            ),
        }
    )


def _run(op: str, frame: pl.DataFrame) -> list[pl.DataFrame]:
    """The node's own runner on its example, with every output collected."""
    source = ns.SETTINGS_SOURCES[op].source
    assert source is not None, op
    module = importlib.import_module(source.partition(":")[0])
    runner = getattr(module, RUNNERS[op])
    outs = runner([frame.lazy()], ns.EXAMPLES[op])
    return [out.collect() for out in outs]


@pytest.mark.parametrize(("op", "setting"), sorted(transform.PROPS))
def test_props_reach_the_public_schema(op, setting):
    prop = describe_op(op)["settings"]["schema"]["properties"][setting]
    for key, wanted in transform.PROPS[(op, setting)].items():
        assert prop[key] == wanted, (op, setting, key)


@pytest.mark.parametrize("op", OPS)
def test_every_list_setting_describes_its_items(op):
    properties = describe_op(op)["settings"]["schema"]["properties"]
    lists = [key for key, prop in properties.items() if prop.get("type") == "array"]
    assert lists, f"{op} has no list setting to check"
    for key in lists:
        assert properties[key].get("items"), f"{op}.{key} has no item schema"


@pytest.mark.parametrize("op", OPS)
def test_example_fits_its_settings_schema(op):
    settings = describe_op(op)["settings"]
    assert settings["example_is_default"] is False, op
    assert validate_value(settings["schema"], settings["example"], "settings") is None


def test_running_total_example_sums_within_each_vendor():
    [out] = _run("transform.running_total", _frame())
    assert out.columns == ["Amount", "InvoiceNo", "Vendor", "Date", "RunTot_Amount"]
    assert out["RunTot_Amount"].to_list() == [5, 20000, 50000]


def test_transpose_example_stacks_amount_under_each_key_pair():
    [out] = _run("transform.transpose", _frame())
    assert out.columns == ["Vendor", "InvoiceNo", "Name", "Value"]
    assert out.rows() == [
        ("x", "a", "Amount", 5),
        ("y", "a", "Amount", 20000),
        ("y", "b", "Amount", 30000),
    ]


def test_pivot_example_makes_one_column_per_invoice():
    [out] = _run("transform.pivot", _frame())
    assert out.columns == ["Vendor", "a", "b"]
    assert out.rows() == [("x", 5.0, None), ("y", 20000.0, 30000.0)]


def test_unpivot_example_stacks_amount_into_name_and_value():
    [out] = _run("transform.unpivot", _frame())
    assert out.columns == ["Vendor", "Attribute", "Value"]
    assert out.rows() == [
        ("x", "Amount", 5),
        ("y", "Amount", 20000),
        ("y", "Amount", 30000),
    ]


def test_window_example_follows_date_order_within_each_vendor():
    frame = _frame()
    [out] = _run("transform.window", frame)
    assert out.columns == [
        "Amount",
        "InvoiceNo",
        "Vendor",
        "Date",
        "RunningAmount",
        "PreviousAmount",
    ]
    assert out["RunningAmount"].to_list() == [5, 20000, 50000]
    assert out["PreviousAmount"].to_list() == [None, None, 20000]
    # Date decides the order, not the row order: reversed rows give reversed results.
    [reversed_out] = _run("transform.window", frame.reverse())
    assert reversed_out["RunningAmount"].to_list() == [50000, 20000, 5]


def test_window_operation_enum_is_the_real_operation_list():
    properties = describe_op("transform.window")["settings"]["schema"]["properties"]
    operation = properties["ops"]["items"]["properties"]["op"]
    assert operation["enum"] == list(window.OPS)
