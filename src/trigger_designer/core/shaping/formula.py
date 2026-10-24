"""Formula: chained calculated columns through DuckDB (Qt-free)."""

from __future__ import annotations

import re

import duckdb
import polars as pl

from trigger_designer.core.shaping.common import (
    ShapingError,
    as_lazy,
    schema_of,
)
from trigger_designer.core.shaping.sql_expression import (
    apply_outside_string_literals,
    normalize_string_literals,
    quote_identifier,
    replace_column_names,
    translate_function_aliases,
)
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes

MAX_FORMULA_SECTIONS = 5
MIN_EDITOR_HEIGHT = 60
MAX_EDITOR_HEIGHT = 600
DEFAULT_EDITOR_HEIGHT = 120
AUTO_DTYPE_OPTION = "Auto"
DTYPE_OPTIONS = [
    AUTO_DTYPE_OPTION,
    "String",
    "Integer",
    "Float",
    "Boolean",
    "Date",
    "Datetime",
    "Time",
    "Categorical",
]
DTYPE_TO_DUCKDB = {
    "String": "VARCHAR",
    "Integer": "BIGINT",
    "Float": "DOUBLE",
    "Boolean": "BOOLEAN",
    "Date": "DATE",
    "Datetime": "TIMESTAMP",
    "Time": "TIME",
    "Categorical": "VARCHAR",
}

DEFAULT_SECTION = {
    "target_column": "",
    "formula_text": "",
    "editor_height": DEFAULT_EDITOR_HEIGHT,
    "target_dtype": "",
}

DEFAULTS = {"sections": [dict(DEFAULT_SECTION)]}


def normalize(settings: dict) -> dict:
    sections: list[dict] = []
    for section in (settings or {}).get("sections") or []:
        if not isinstance(section, dict):
            continue
        try:
            editor_height = int(section.get("editor_height", DEFAULT_EDITOR_HEIGHT))
        except (TypeError, ValueError):
            editor_height = DEFAULT_EDITOR_HEIGHT
        target_dtype = str(section.get("target_dtype") or "")
        if target_dtype not in DTYPE_OPTIONS[1:]:
            target_dtype = ""
        sections.append(
            {
                "target_column": str(section.get("target_column") or ""),
                "formula_text": str(section.get("formula_text") or ""),
                "editor_height": min(
                    MAX_EDITOR_HEIGHT, max(MIN_EDITOR_HEIGHT, editor_height)
                ),
                "target_dtype": target_dtype,
            }
        )
    if not sections:
        sections.append(dict(DEFAULT_SECTION))
    return {"sections": sections[:MAX_FORMULA_SECTIONS]}


def is_configured(section: dict) -> bool:
    return bool(
        str(section.get("target_column") or "").strip()
        and str(section.get("formula_text") or "").strip()
    )


def prepare_formula_for_sql(formula_text: str, available_columns: list[str]) -> str:
    sql_formula = normalize_string_literals(formula_text)
    sql_formula = apply_outside_string_literals(sql_formula, translate_function_aliases)
    for column_name in available_columns:
        sql_formula = replace_column_names(sql_formula, column_name)
    return sql_formula


def shorten_error(message: str) -> str:
    text = (message or "").strip().replace("\r\n", "\n")
    match = re.search(r'Referenced column "[^"]+" not found', text)
    if match:
        return match.group()
    first_line = text.split("\n", 1)[0].strip()
    for prefix in ("Binder Error:", "Catalog Error:", "Parser Error:"):
        if first_line.startswith(prefix):
            first_line = first_line[len(prefix) :].strip()
    return first_line[:160]


def section_query(
    section: dict, available_columns: list[str], relation_name: str
) -> tuple[str, list[str]]:
    target = section["target_column"]
    sql_formula = prepare_formula_for_sql(section["formula_text"], available_columns)
    columns = list(available_columns)
    if target in columns:
        query = (
            f"SELECT * REPLACE ({sql_formula} AS {quote_identifier(target)}) "
            f"FROM {relation_name}"
        )
    else:
        db_type = DTYPE_TO_DUCKDB.get(section.get("target_dtype") or "")
        if db_type:
            sql_formula = f"CAST({sql_formula} AS {db_type})"
        query = (
            f"SELECT *, {sql_formula} AS {quote_identifier(target)} "
            f"FROM {relation_name}"
        )
        columns.append(target)
    return query, columns


def build_combined_query(
    configured: list[tuple[int, dict]], available_columns: list[str], base: str
) -> tuple[str, list[str]]:
    ctes: list[str] = []
    current = base
    columns = list(available_columns)
    for index, section in configured:
        query, columns = section_query(section, columns, current)
        step = f"df_step_{index}"
        ctes.append(f"{step} AS ({query})")
        current = step
    return "WITH " + ", ".join(ctes) + f" SELECT * FROM {current}", columns


def _run_sequential(
    frame, configured: list[tuple[int, dict]], available: list[str]
) -> tuple[pl.DataFrame, list[str], dict[int, str]]:
    columns = list(available)
    errors: dict[int, str] = {}
    with duckdb.connect(":memory:") as duck:
        for index, section in configured:
            relation = f"df_step_{index}"
            query, columns = section_query(section, columns, relation)
            duck.register(relation, frame)
            try:
                frame = duck.execute(query).pl()
            except Exception as exc:  # noqa: BLE001 - identify the section
                errors[index] = shorten_error(str(exc))
                break
    return frame, columns, errors


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    frame = as_lazy(frames[0])
    sections = normalize(settings)["sections"]
    configured = [
        (index, section)
        for index, section in enumerate(sections)
        if is_configured(section)
    ]
    if not configured:
        return [frame]

    available = list(schema_of(frame))
    query, _columns = build_combined_query(configured, available, "df_for_duck")
    try:
        with duckdb.connect(":memory:") as duck:
            duck.register("df_for_duck", frame)
            result = duck.execute(query).pl()
    except Exception:  # noqa: BLE001 - fall back to identify the section
        result, _columns, errors = _run_sequential(frame, configured, available)
        if errors:
            index = min(errors)
            raise ShapingError(
                "TD-SHAPE-004", f"Section {index + 1}: {errors[index]}"
            ) from None

    return [normalize_to_supported_dtypes(result).lazy()]


def validate_section(frames: list, settings: dict, section_index: int) -> list[dict]:
    """EXPLAIN one section against a zero-row copy of the live schema."""
    if not frames or frames[0] is None:
        return []
    sections = normalize(settings)["sections"]
    if not 0 <= section_index < len(sections):
        return []
    sample = pl.DataFrame(schema=schema_of(frames[0]))
    available = list(sample.columns)
    with duckdb.connect(":memory:") as duck:
        current = sample
        for index, section in enumerate(sections[:section_index]):
            if not is_configured(section):
                continue
            relation = f"df_step_{index}"
            query, available = section_query(section, available, relation)
            duck.register(relation, current)
            try:
                current = duck.execute(query).pl()
            except Exception:  # noqa: BLE001 - an earlier section's problem
                return []
        section = sections[section_index]
        if not is_configured(section):
            return []
        relation = f"df_step_{section_index}"
        query, _available = section_query(section, available, relation)
        duck.register(relation, current)
        try:
            duck.execute(f"EXPLAIN {query}").fetchall()
        except Exception as exc:  # noqa: BLE001 - report on this section
            return [
                {
                    "message": shorten_error(str(exc)),
                    "line": 1,
                    "column": 0,
                    "length": 1,
                }
            ]
    return []
