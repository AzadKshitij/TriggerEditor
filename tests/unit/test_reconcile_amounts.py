"""Reconcile reads text amounts like the Audit nodes: a decimal comma is a decimal."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.audit.common import amount_expr as audit_amount_expr
from trigger_designer.core.shaping import reconcile
from trigger_designer.core.utils.amounts import amount_expr


def _reconcile(left_amounts: list[str], right_amounts: list[str], tolerance=0.0):
    keys = [f"k{i}" for i in range(len(left_amounts))]
    left = pl.DataFrame({"k": keys, "amt": left_amounts}).lazy()
    right = pl.DataFrame({"k": keys, "amt": right_amounts}).lazy()
    return reconcile.apply_reconcile(
        left,
        right,
        {
            "key_pairs": [{"left": "k", "right": "k"}],
            "amount_left": "amt",
            "amount_right": "amt",
            "tolerance": tolerance,
        },
    )


def test_one_helper_serves_audit_and_reconcile() -> None:
    assert audit_amount_expr is amount_expr


def test_decimal_comma_is_a_decimal_not_a_thousand_times_larger() -> None:
    result = _reconcile(["1,50"], ["1.50"])
    assert result.matched["Match_Status"].to_list() == ["Within tolerance"]
    assert result.left_unmatched.height == 0


def test_150_does_not_match_1_comma_50() -> None:
    result = _reconcile(["1,50"], ["150"])
    # 1.5 against 150 is a real difference, no longer hidden by stripping commas.
    assert result.matched.height == 0
    assert result.left_unmatched.height == 1


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1,234.50", 1234.5),
        ("1.234,50", 1234.5),
        ("(1,234.50)", -1234.5),
        ("$5", 5.0),
        ("1,234", 1234.0),
        ("1234,5", 1234.5),
        ("1,2,3", None),
        ("abc", None),
    ],
)
def test_text_amount_forms(text, expected) -> None:
    out = pl.DataFrame({"a": [text]}).select(amount_expr("a", pl.String))["a"]
    assert out.to_list() == [expected]
