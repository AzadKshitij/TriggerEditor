"""Normalize: deterministic column-name cleanup (Qt-free)."""

from __future__ import annotations

import re

import polars as pl

from trigger_designer.core.shaping.common import ShapingError, as_lazy, schema_of

DEFAULTS = {
    "trim_whitespace": True,
    "spaces_to_underscore": True,
    "remove_all_whitespace": False,
    "case_modification": "none",
    "selected_columns": [],
}


def normalize_column_name(
    name: str,
    *,
    trim_whitespace: bool = True,
    spaces_to_underscore: bool = True,
    remove_all_whitespace: bool = False,
    case_modification: str = "none",
) -> str:
    """Apply the name rules in a fixed order: trim, whitespace, case."""
    result = name.strip() if trim_whitespace else name
    if remove_all_whitespace:
        result = re.sub(r"\s+", "", result)
    elif spaces_to_underscore:
        result = re.sub(r"\s+", "_", result)
    if case_modification == "lower":
        result = result.lower()
    elif case_modification == "upper":
        result = result.upper()
    elif case_modification == "title":
        result = result.title()
    # Never hand back an empty name; keep the original instead.
    return result or name


def build_rename_mapping(
    columns: list[str],
    selected: list[str],
    *,
    trim_whitespace: bool = True,
    spaces_to_underscore: bool = True,
    remove_all_whitespace: bool = False,
    case_modification: str = "none",
) -> dict[str, str]:
    """Map each in-scope column to its normalized name (changed ones only)."""
    scope = set(selected) if selected else set(columns)
    mapping: dict[str, str] = {}
    for column in columns:
        if column not in scope:
            continue
        normalized = normalize_column_name(
            column,
            trim_whitespace=trim_whitespace,
            spaces_to_underscore=spaces_to_underscore,
            remove_all_whitespace=remove_all_whitespace,
            case_modification=case_modification,
        )
        if normalized != column:
            mapping[column] = normalized
    return mapping


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    settings = settings or {}
    frame = as_lazy(frames[0])
    columns = list(schema_of(frame))
    selected = [
        name for name in settings.get("selected_columns") or [] if name in columns
    ]
    mapping = build_rename_mapping(
        columns,
        selected,
        trim_whitespace=bool(settings.get("trim_whitespace", True)),
        spaces_to_underscore=bool(settings.get("spaces_to_underscore", True)),
        remove_all_whitespace=bool(settings.get("remove_all_whitespace", False)),
        case_modification=str(settings.get("case_modification", "none")),
    )
    final_names = [mapping.get(name, name) for name in columns]
    duplicates = {name for name in final_names if final_names.count(name) > 1}
    if duplicates:
        raise ShapingError(
            "TD-SHAPE-002",
            f"Rules produce duplicate column name '{min(duplicates)}'",
        )
    return [frame.rename(mapping) if mapping else frame]
