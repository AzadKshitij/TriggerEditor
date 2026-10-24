"""A trailing operator is reported as a section syntax error."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.shaping import formula as core
from trigger_designer.core.shaping.common import ShapingError


def test_trailing_operator_is_reported() -> None:
    frame = pl.DataFrame({"g": [2], "discount_pct": [0.1]}).lazy()
    sections = [
        {
            "target_column": "result",
            "formula_text": "[g] * [discount_pct] + ",
            "editor_height": 120,
            "target_dtype": "",
        }
    ]
    with pytest.raises(ShapingError) as error:
        core.run_node([frame], {"sections": sections})
    assert error.value.code == "TD-SHAPE-004"
    assert "Section 1" in str(error.value)
