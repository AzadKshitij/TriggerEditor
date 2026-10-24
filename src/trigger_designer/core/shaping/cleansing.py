"""Cleansing: null handling and text cleanup (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import as_lazy
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy

DEFAULTS = {
    "remove_null_rows": False,
    "remove_null_rows_from_selected_columns": False,
    "remove_null_columns": False,
    "replace_null_strings": True,
    "replace_null_numbers": True,
    "strip_whitespace": True,
    "normalize_spaces": True,
    "remove_all_whitespace": False,
    "case_modification": "none",
    "remove_letters": False,
    "remove_numbers": False,
    "remove_punctuation": False,
    "selected_fields": [],
}


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    """Apply the null, whitespace, character and case rules in order."""
    settings = {**DEFAULTS, **(settings or {})}
    data = as_lazy(frames[0]).collect()
    cleaner = DataCleansing(data)
    fields = [
        name for name in settings.get("selected_fields") or [] if name in data.columns
    ]

    if settings["remove_null_rows"]:
        cleaner.handle_nulls(NullStrategy.REMOVE_ALL_NULL_ROWS)
    if settings["remove_null_rows_from_selected_columns"] and fields:
        cleaner.remove_rows_with_nulls(fields=fields)
    if settings["remove_null_columns"]:
        cleaner.handle_nulls(NullStrategy.REMOVE_ALL_NULL_COLS)
    if settings["replace_null_strings"] or settings["replace_null_numbers"]:
        cleaner.replace_null_defaults(
            replace_strings=bool(settings["replace_null_strings"]),
            replace_numbers=bool(settings["replace_null_numbers"]),
        )

    if fields:
        if (
            settings["strip_whitespace"]
            or settings["normalize_spaces"]
            or settings["remove_all_whitespace"]
        ):
            cleaner.strip_whitespace(
                remove_all=bool(settings["remove_all_whitespace"]),
                normalize_spaces=bool(settings["normalize_spaces"]),
                fields=fields,
            )
        if (
            settings["remove_letters"]
            or settings["remove_numbers"]
            or settings["remove_punctuation"]
        ):
            cleaner.remove_characters(
                remove_letters=bool(settings["remove_letters"]),
                remove_numbers=bool(settings["remove_numbers"]),
                remove_punctuation=bool(settings["remove_punctuation"]),
                fields=fields,
            )
        if settings["case_modification"] != "none":
            cleaner.modify_case(str(settings["case_modification"]), fields=fields)

    return [cleaner.get_result().lazy()]
