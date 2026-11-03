"""Find and Replace: a switched-off rule is neither checked nor run."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.shaping import find_replace
from trigger_designer.core.shaping.common import ShapingError


def _apply(rules: list[dict]) -> pl.DataFrame:
    frame = pl.DataFrame({"c": ["abc", "xyz"]})
    out = find_replace.apply_find_replace(frame, {"columns": ["c"], "rules": rules})
    return out.collect()


def test_disabled_rule_with_empty_find_does_not_stop_the_node() -> None:
    out = _apply(
        [
            {"find": "", "replace": "!", "enabled": False},
            {"find": "abc", "replace": "ok"},
        ]
    )
    assert out["c"].to_list() == ["ok", "xyz"]


def test_disabled_rule_with_invalid_regex_is_not_checked() -> None:
    out = _apply([{"find": "(", "mode": "regex", "enabled": False}])
    assert out["c"].to_list() == ["abc", "xyz"]


def test_enabled_empty_find_still_errors_and_names_its_position() -> None:
    with pytest.raises(ShapingError) as error:
        _apply(
            [
                {"find": "a", "replace": "b", "enabled": False},
                {"find": "", "replace": "!"},
            ]
        )
    assert error.value.code == "TD-SHAPE-042"
    assert "Rule 2" in str(error.value)
