"""``describe_op`` tells a harness what every list setting holds (AI plan).

The per-group files pin each shape to the code that reads it. This file checks
the whole catalogue at once, so a new node or setting cannot ship with an
undescribed list.
"""

from __future__ import annotations

import pytest

from trigger_designer.core.authoring.validate import validate_value
from trigger_designer.core.headless import node_items, node_spec

pytestmark = pytest.mark.unit

LIVE_OPS = [row["op"] for row in node_spec.list_ops()]


def _props(op: str) -> dict:
    return node_spec.describe_op(op)["settings"]["schema"]["properties"]


@pytest.mark.parametrize("op", LIVE_OPS)
def test_every_list_setting_says_what_its_items_are(op):
    for key, prop in _props(op).items():
        if prop.get("type") == "array":
            assert prop.get("items"), f"{op}.{key} is a list with no item schema"


@pytest.mark.parametrize("op", LIVE_OPS)
def test_every_setting_has_a_type_or_choices(op):
    for key, prop in _props(op).items():
        assert prop.get("type") or "enum" in prop, f"{op}.{key} has no type"


def test_every_described_setting_exists():
    """A typo in a table would describe nothing and be silent."""
    for op, key in node_items.PROPS:
        assert key in _props(op), f"{op}.{key} is not a setting of {op}"
    for op in node_items.EXAMPLES:
        assert op in LIVE_OPS, op


def test_every_example_fits_its_own_schema_and_is_used_by_describe():
    for op, example in node_items.EXAMPLES.items():
        spec = node_spec.describe_op(op)["settings"]
        assert validate_value(spec["schema"], example, "settings") is None, op
        assert spec["example"] == node_spec.EXAMPLES[op]


def test_item_schemas_catch_a_wrong_item_and_accept_a_right_one():
    schema = _props("preparation.groupby")["actions"]
    good = [{"field": "Vendor", "action": "Sum", "output_name": "t"}]
    assert validate_value(schema, good, "actions") is None
    wrong_action = [{"field": "Vendor", "action": "Total", "output_name": "t"}]
    assert "must be one of" in validate_value(schema, wrong_action, "actions")
    assert "string" in validate_value(
        schema, [{"field": 3, "action": "Sum"}], "actions"
    )


def test_a_union_type_accepts_either_kind_and_refuses_the_rest():
    schema = {"type": ["integer", "null"], "minimum": 0}
    assert validate_value(schema, None, "x") is None
    assert validate_value(schema, 4, "x") is None
    assert "whole number or empty" in validate_value(schema, "four", "x")
    assert "at least 0" in validate_value(schema, -1, "x")


def test_gaps_range_accepts_empty_for_lowest_and_highest_seen():
    schema = _props("audit.gaps")["range_start"]
    assert validate_value(schema, None, "range_start") is None
    assert validate_value(schema, "2024-01-01", "range_start") is not None
