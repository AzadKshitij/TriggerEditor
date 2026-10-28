"""Aggregate: group keys and measures (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import (
    ShapingError,
    as_lazy,
    schema_of,
)
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes

DEFAULTS = {"actions": []}

AGGREGATION_FUNCTIONS = [
    "GroupBy",
    "Count",
    "Sum",
    "Mean",
    "Min",
    "Max",
    "Std",
    "Var",
    "Median",
    "First",
    "Last",
    "N_Unique",
    "List",
]

ACTION_TO_FUNCTION = {
    "Count": "count",
    "Sum": "sum",
    "Mean": "mean",
    "Min": "min",
    "Max": "max",
    "Std": "std",
    "Var": "var",
    "Median": "median",
    "First": "first",
    "Last": "last",
    "N_Unique": "n_unique",
    "List": "list",
}

FUNCTION_TO_ACTION = {
    function: action for action, function in ACTION_TO_FUNCTION.items()
}

PREFIX_MAP = {
    "GroupBy": "",
    "Count": "Count_",
    "Sum": "Sum_",
    "Mean": "Avg_",
    "Min": "Min_",
    "Max": "Max_",
    "Std": "Std_",
    "Var": "Var_",
    "Median": "Median_",
    "First": "First_",
    "Last": "Last_",
    "N_Unique": "Unique_",
    "List": "List_",
}

#: Actions offered for text (String/Categorical) columns.
TEXT_ACTIONS = [
    "GroupBy",
    "Count",
    "Min",
    "Max",
    "First",
    "Last",
    "N_Unique",
    "List",
]

#: Substrings of ``str(dtype)`` that mark a text column.
TEXT_DTYPE_HINTS = ("String", "Categorical")


def actions_for_dtype(dtype) -> list[str]:
    """Actions that make sense for a column dtype."""
    text = str(dtype or "")
    if any(hint in text for hint in TEXT_DTYPE_HINTS):
        return list(TEXT_ACTIONS)
    return list(AGGREGATION_FUNCTIONS)


def default_output_name(field: str, action: str) -> str:
    if action == "GroupBy":
        return field
    return f"{PREFIX_MAP.get(action, '')}{field}"


def normalize(settings: dict) -> dict:
    """One canonical action list: non-empty fields, known action spelling."""
    actions = []
    for item in (settings or {}).get("actions") or []:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()
        if not field:
            continue
        action = str(item.get("action") or "Count")
        if action == "Group By":
            action = "GroupBy"
        output = str(item.get("output_name") or "").strip()
        if not output:
            output = default_output_name(field, action)
        actions.append({"field": field, "action": action, "output_name": output})
    return {"actions": actions}


def _expression(field: str, action: str, output: str) -> pl.Expr:
    if action == "Count":
        return pl.len().alias(output)
    if action == "List":
        return pl.col(field).implode().alias(output)
    function = ACTION_TO_FUNCTION[action]
    return getattr(pl.col(field), function)().alias(output)


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    actions = normalize(settings)["actions"]
    frame = as_lazy(frames[0])
    if not actions:
        return [frame]

    schema = schema_of(frame)
    valid = [entry for entry in actions if entry["field"] in schema]
    if not valid:
        return [frame]
    for entry in valid:
        if entry["action"] != "GroupBy" and entry["action"] not in ACTION_TO_FUNCTION:
            raise ShapingError(
                "TD-SHAPE-004", f"Unknown aggregate action: {entry['action']}"
            )

    group_fields: list[str] = []
    for entry in valid:
        if entry["action"] == "GroupBy" and entry["field"] not in group_fields:
            group_fields.append(entry["field"])
    # The old dict model let a later action for a field overwrite the earlier
    # one while keeping the first position.
    measures: dict[str, dict] = {}
    for entry in valid:
        if entry["action"] != "GroupBy":
            measures[entry["field"]] = entry

    expressions = [
        _expression(entry["field"], entry["action"], entry["output_name"])
        for entry in measures.values()
    ]
    final_names = group_fields + [entry["output_name"] for entry in measures.values()]
    duplicates = {name for name in final_names if final_names.count(name) > 1}
    if duplicates:
        raise ShapingError(
            "TD-SHAPE-002",
            f"Duplicate output column name '{min(duplicates)}'",
        )

    if group_fields:
        grouped = frame.group_by(group_fields, maintain_order=True)
        result = (
            grouped.agg(expressions)
            if expressions
            else grouped.agg(pl.len().alias("count"))
        )
    elif expressions:
        result = frame.select(expressions)
    else:
        return [frame]

    return [normalize_to_supported_dtypes(result)]


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    actions = normalize(settings)["actions"]
    schema = schema_of(as_lazy(frames[0]))
    missing = [entry["field"] for entry in actions if entry["field"] not in schema]
    return [(f"{len(missing)} field(s) missing", "warning")] if missing else []
