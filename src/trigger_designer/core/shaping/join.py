"""Join: one full outer join split into left-only, joined and right-only."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import (
    ShapingError,
    as_lazy,
    schema_of,
)

DEFAULTS = {
    "join_type": "inner",
    "mapping_data": [],
    "selected_columns": [],
    "auto_accept_new_columns": True,
    "known_columns": [],
}

LEFT_SUFFIX = "_left"
RIGHT_SUFFIX = "_right"
LEFT_TAG = "__left_present"
RIGHT_TAG = "__right_present"


def sanitize_mapping(mapping, left_names, right_names) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple] = set()
    for item in mapping or []:
        if not isinstance(item, dict):
            continue
        left = item.get("left_column")
        right = item.get("right_column")
        key = (left, right)
        if left in left_names and right in right_names and key not in seen:
            out.append({"left_column": left, "right_column": right})
            seen.add(key)
    return out


def sync_selected_with_schema(
    settings: dict, left_names: list[str], right_names: list[str]
) -> dict:
    """Prune stale selections, auto-add arrivals, refresh known_columns."""
    mapping = sanitize_mapping(settings.get("mapping_data"), left_names, right_names)

    selected: list[dict] = []
    for item in settings.get("selected_columns") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        source = item.get("source")
        candidate = {"name": name, "source": source}
        allowed = (source == "L" and name in left_names) or (
            source == "R" and name in right_names
        )
        if allowed and candidate not in selected:
            selected.append(candidate)

    auto_accept = bool(settings.get("auto_accept_new_columns", True))
    known = settings.get("known_columns")
    if not isinstance(known, list):
        known = []
    known_set = {
        (entry.get("name"), entry.get("source"))
        for entry in known
        if isinstance(entry, dict)
    }
    live = [{"name": name, "source": "L"} for name in sorted(left_names)] + [
        {"name": name, "source": "R"} for name in sorted(right_names)
    ]
    live_set = {(entry["name"], entry["source"]) for entry in live}

    if auto_accept and selected and known_set:
        selected_set = {
            (column.get("name"), column.get("source")) for column in selected
        }
        for entry in live:
            key = (entry["name"], entry["source"])
            if key not in known_set and key not in selected_set:
                selected.append(dict(entry))
                selected_set.add(key)

    kept_known = [
        dict(entry)
        for entry in known
        if (entry.get("name"), entry.get("source")) in live_set
    ]
    kept_keys = {(entry["name"], entry["source"]) for entry in kept_known}
    for entry in live if auto_accept else selected:
        if not isinstance(entry, dict):
            continue
        key = (entry.get("name"), entry.get("source"))
        if key in live_set and key not in kept_keys:
            kept_known.append({"name": key[0], "source": key[1]})
            kept_keys.add(key)

    return {
        **settings,
        "mapping_data": mapping,
        "selected_columns": selected,
        "known_columns": kept_known,
    }


def ensure_default_mapping(
    settings: dict, left_names: list[str], right_names: list[str]
) -> dict:
    if settings.get("mapping_data") or not left_names or not right_names:
        return settings
    return {
        **settings,
        "mapping_data": [
            {"left_column": left_names[0], "right_column": right_names[0]}
        ],
    }


def apply_upstream_renames(
    settings: dict,
    left_map: dict,
    right_map: dict,
    left_names: list[str],
    right_names: list[str],
) -> tuple[dict, bool]:
    """Remap stored references from pre-rename upstream names."""
    if not left_map and not right_map:
        return settings, False
    live_left = set(left_names)
    live_right = set(right_names)
    changed = False

    def remap(side_map: dict, live: set, current: str) -> str:
        for old, new in side_map.items():
            if old == current and old not in live and new in live:
                return new
        return current

    mapping = [dict(item) for item in settings.get("mapping_data") or []]
    for item in mapping:
        new_left = remap(left_map, live_left, item.get("left_column"))
        if new_left != item.get("left_column"):
            item["left_column"] = new_left
            changed = True
        new_right = remap(right_map, live_right, item.get("right_column"))
        if new_right != item.get("right_column"):
            item["right_column"] = new_right
            changed = True

    selected = [dict(item) for item in settings.get("selected_columns") or []]
    for column in selected:
        name = column.get("name")
        if column.get("source") == "L":
            new_name = remap(left_map, live_left, name)
        elif column.get("source") == "R":
            new_name = remap(right_map, live_right, name)
        else:
            continue
        if new_name != name:
            column["name"] = new_name
            changed = True

    return (
        {**settings, "mapping_data": mapping, "selected_columns": selected},
        changed,
    )


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    settings = {**DEFAULTS, **(settings or {})}
    left = as_lazy(frames[0])
    right = as_lazy(frames[1])
    left_names = list(schema_of(left))
    right_names = list(schema_of(right))
    settings = sync_selected_with_schema(settings, left_names, right_names)
    mapping = settings["mapping_data"]
    if not mapping:
        raise ShapingError("TD-SHAPE-001", "Add at least one key pair")

    left_cols = [item["left_column"] for item in mapping]
    right_cols = [item["right_column"] for item in mapping]
    selected_columns = settings["selected_columns"]

    conflicting = [
        name for name in right_names if name in left_names and name not in right_cols
    ]
    right_renamed = (
        right.rename({name: f"{name}{RIGHT_SUFFIX}" for name in conflicting})
        if conflicting
        else right
    )

    left_tagged = left.with_columns(pl.lit(1).alias(LEFT_TAG))
    right_tagged = right_renamed.with_columns(pl.lit(1).alias(RIGHT_TAG))
    result = left_tagged.join(
        right_tagged,
        left_on=left_cols,
        right_on=right_cols,
        how="full",
        suffix=LEFT_SUFFIX,
        coalesce=True,
    )
    result_columns = result.collect_schema().names()

    if selected_columns:
        selected: list[str] = []
        for column in selected_columns:
            name = column["name"]
            if column["source"] == "L":
                if name in left_cols:
                    selected.append(name)
                elif f"{name}{LEFT_SUFFIX}" in result_columns:
                    selected.append(f"{name}{LEFT_SUFFIX}")
                else:
                    selected.append(name)
            else:
                if name in right_cols:
                    selected.append(name)
                elif f"{name}{RIGHT_SUFFIX}" in result_columns:
                    selected.append(f"{name}{RIGHT_SUFFIX}")
                else:
                    selected.append(name)

        result_set = set(result_columns)
        fixed: list[str] = []
        for column in selected:
            if column not in result_set and column in right_cols:
                counterpart = left_cols[right_cols.index(column)]
                column = counterpart if counterpart in result_set else column
            fixed.append(column)
        selected = [
            column
            for index, column in enumerate(fixed)
            if column in result_columns and column not in fixed[:index]
        ]
    else:
        selected = []

    # The outputs stay lazy: an output nothing consumes costs nothing, and a
    # consumed one streams instead of holding the whole join in memory.
    both = pl.col(LEFT_TAG).is_not_null() & pl.col(RIGHT_TAG).is_not_null()
    left_only = pl.col(RIGHT_TAG).is_null()
    right_only = pl.col(LEFT_TAG).is_null()

    if selected_columns:
        data = result.filter(both).select(selected)
    else:
        data = result.filter(both).select(
            [name for name in result_columns if not name.startswith("__")]
        )

    left_final = [
        name
        for name in result_columns
        if name in left_names
        or (name.endswith(LEFT_SUFFIX) and name.replace(LEFT_SUFFIX, "") in left_names)
    ]
    left_final = [name for name in left_final if not name.startswith("__")]
    l_data = result.filter(left_only).select(left_final)

    # Right-only output carries the right frame's columns only. A conflicting
    # right column was renamed before the join, so its original name belongs
    # to the left frame and must not be pulled in here.
    right_after_rename = {name for name in right_names if name not in conflicting} | {
        f"{name}{RIGHT_SUFFIX}" for name in conflicting
    }
    right_final = [
        name
        for name in result_columns
        if name in right_after_rename and not name.startswith("__")
    ]
    result_set = set(result_columns)
    for left_key, right_key in zip(left_cols, right_cols):
        if (
            right_key not in result_set
            and left_key in result_set
            and left_key not in right_final
        ):
            right_final.append(left_key)
    r_data = result.filter(right_only).select(right_final)

    return [l_data, data, r_data]
