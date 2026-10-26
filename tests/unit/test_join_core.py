"""Join core: full outer split, selection, naming and auto-accept."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.shaping import join as core
from trigger_designer.core.shaping.common import ShapingError


def _left() -> pl.LazyFrame:
    return pl.DataFrame({"id": [1, 2], "a": ["x", "y"]}).lazy()


def _right() -> pl.LazyFrame:
    return pl.DataFrame({"rid": [2, 3], "b": ["p", "q"]}).lazy()


def _settings(**overrides) -> dict:
    base = {
        "mapping_data": [{"left_column": "id", "right_column": "rid"}],
        "selected_columns": [],
        "auto_accept_new_columns": True,
        "known_columns": [],
    }
    base.update(overrides)
    return base


def _run(settings: dict, left=None, right=None):
    left_frame = left if left is not None else _left()
    right_frame = right if right is not None else _right()
    return [
        frame.collect() for frame in core.run_node([left_frame, right_frame], settings)
    ]


def test_three_outputs_split_the_full_outer_join() -> None:
    left_only, joined, right_only = _run(_settings())
    assert left_only["id"].to_list() == [1]
    assert joined["id"].to_list() == [2]
    assert right_only["id"].to_list() == [3]


def test_conflicting_names_get_the_right_suffix() -> None:
    right = pl.DataFrame({"rid": [2], "a": ["r"]}).lazy()
    _left_only, joined, _right_only = _run(_settings(), right=right)
    assert "a" in joined.columns
    assert "a_right" in joined.columns


def test_selected_columns_keep_order_and_source() -> None:
    _left_only, joined, _right_only = _run(
        _settings(
            selected_columns=[
                {"name": "b", "source": "R"},
                {"name": "id", "source": "L"},
            ]
        )
    )
    assert joined.columns == ["b", "id"]


def test_coalesced_right_key_maps_to_the_left_key() -> None:
    _left_only, joined, _right_only = _run(
        _settings(selected_columns=[{"name": "rid", "source": "R"}])
    )
    assert joined.columns == ["id"]


def test_empty_mapping_is_an_error() -> None:
    with pytest.raises(ShapingError) as error:
        core.run_node([_left(), _right()], _settings(mapping_data=[]))
    assert error.value.code == "TD-SHAPE-001"


def test_invalid_pairs_are_dropped() -> None:
    with pytest.raises(ShapingError):
        core.run_node(
            [_left(), _right()],
            _settings(mapping_data=[{"left_column": "gone", "right_column": "b"}]),
        )

    left_only, joined, _right_out = _run(
        _settings(
            mapping_data=[
                {"left_column": "gone", "right_column": "b"},
                {"left_column": "id", "right_column": "rid"},
            ]
        )
    )
    assert joined.height == 1
    assert left_only.height == 1


def test_auto_accept_adds_unseen_columns() -> None:
    settings = core.sync_selected_with_schema(
        {
            "mapping_data": [],
            "selected_columns": [{"name": "id", "source": "L"}],
            "known_columns": [{"name": "id", "source": "L"}],
            "auto_accept_new_columns": True,
        },
        ["id", "a"],
        ["rid", "b"],
    )
    selected = {
        (entry["name"], entry["source"]) for entry in settings["selected_columns"]
    }
    assert ("a", "L") in selected
    assert ("b", "R") in selected


def test_known_unchecked_columns_stay_out() -> None:
    settings = core.sync_selected_with_schema(
        {
            "mapping_data": [],
            "selected_columns": [{"name": "id", "source": "L"}],
            "known_columns": [
                {"name": "id", "source": "L"},
                {"name": "a", "source": "L"},
            ],
            "auto_accept_new_columns": True,
        },
        ["id", "a"],
        ["rid"],
    )
    selected = {entry["name"] for entry in settings["selected_columns"]}
    assert "a" not in selected


def test_upstream_renames_remap_mapping_and_selection() -> None:
    settings, changed = core.apply_upstream_renames(
        _settings(
            selected_columns=[{"name": "id", "source": "L"}],
        ),
        {"id": "new_id"},
        {},
        ["new_id", "a"],
        ["rid", "b"],
    )
    assert changed is True
    assert settings["mapping_data"][0]["left_column"] == "new_id"
    assert settings["selected_columns"][0]["name"] == "new_id"


def test_outputs_are_lazy() -> None:
    outs = core.run_node([_left(), _right()], _settings())
    assert all(isinstance(out, pl.LazyFrame) for out in outs)
