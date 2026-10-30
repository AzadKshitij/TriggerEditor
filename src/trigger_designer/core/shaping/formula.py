"""Formula: chained calculated columns through DuckDB (Qt-free)."""

from __future__ import annotations

import re

import polars as pl

from trigger_designer.core.shaping.common import (
    ShapingError,
    as_lazy,
    schema_of,
)
from trigger_designer.core.shaping.sql_expression import (
    prepare_expression_sql,
    quote_identifier,
    shorten_error,
)

# Formula text is SQL: every query is checked by the read-only guard and runs on
# a locked connection (BUG-029/030), never on a plain DuckDB connection.
from trigger_designer.core.sql_guard import check_select_only
from trigger_designer.core.sql_guard import connect_for_shaping as connect_duckdb
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes

MAX_FORMULA_SECTIONS = 5
MIN_EDITOR_HEIGHT = 60
MAX_EDITOR_HEIGHT = 600
DEFAULT_EDITOR_HEIGHT = 120
AUTO_DTYPE_OPTION = "Auto"
#: Rows of the live input a formula is trial-run on while it is being edited.
VALIDATION_SAMPLE_ROWS = 100
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
        except TypeError, ValueError:
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


def section_query(
    section: dict, available_columns: list[str], relation_name: str
) -> tuple[str, list[str]]:
    target = section["target_column"]
    sql_formula = prepare_expression_sql(
        section["formula_text"], available_columns, in_between=False
    )
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
    with connect_duckdb() as duck:
        for index, section in configured:
            relation = f"df_step_{index}"
            query, columns = section_query(section, columns, relation)
            duck.register(relation, frame)
            try:
                check_select_only(query, allow_unparsable=True)
                frame = duck.sql(query).pl()
            except ShapingError as exc:
                errors[index] = str(exc)
                break
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
        check_select_only(query, allow_unparsable=True)
        with connect_duckdb() as duck:
            duck.register("df_for_duck", frame)
            result = duck.sql(query).pl()
    except Exception:  # noqa: BLE001 - fall back to identify the section
        result, _columns, errors = _run_sequential(frame, configured, available)
        if errors:
            index = min(errors)
            # A guard rejection keeps its own code (TD-SHAPE-110..115).
            guard = re.match(r"\[(TD-SHAPE-11\d)\] (.*)", errors[index])
            code, detail = guard.groups() if guard else ("TD-SHAPE-004", errors[index])
            raise ShapingError(code, f"Section {index + 1}: {detail}") from None

    return [normalize_to_supported_dtypes(result).lazy()]


def _first_error(
    sections: list[dict], section_index: int, base: pl.DataFrame, *, explain: bool
) -> list[dict]:
    """Run sections up to ``section_index`` on ``base``; report the last one's error.

    ``explain`` only binds the query (right for a zero-row schema copy);
    otherwise the query really executes, which is what surfaces runtime
    conversion errors such as a number plus ``""``.
    """
    available = list(base.columns)
    with connect_duckdb() as duck:
        current = base
        for index, section in enumerate(sections[:section_index]):
            if not is_configured(section):
                continue
            relation = f"df_step_{index}"
            query, available = section_query(section, available, relation)
            duck.register(relation, current)
            try:
                check_select_only(query, allow_unparsable=True)
                current = duck.sql(query).pl()
            except Exception:  # noqa: BLE001 - an earlier section's problem
                return []
        section = sections[section_index]
        if not is_configured(section):
            return []
        relation = f"df_step_{section_index}"
        query, _available = section_query(section, available, relation)
        duck.register(relation, current)
        try:
            check_select_only(query, allow_unparsable=True)
            if explain:
                duck.execute(f"EXPLAIN {query}").fetchall()
            else:
                duck.sql(query).pl()
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


def _sample_rows(frame) -> pl.DataFrame | None:
    try:
        return as_lazy(frame).head(VALIDATION_SAMPLE_ROWS).collect()
    except Exception:  # noqa: BLE001 - validation must never break editing
        return None


def validate_section(frames: list, settings: dict, section_index: int) -> list[dict]:
    """Check one section: EXPLAIN on the live schema, then run it on a row sample.

    DuckDB binds ``[price] + ""`` without complaint and only fails when it
    converts the string for a real row, so a zero-row check alone would let
    that formula look valid until the workflow runs.
    """
    if not frames or frames[0] is None:
        return []
    sections = normalize(settings)["sections"]
    if not 0 <= section_index < len(sections):
        return []
    schema_only = pl.DataFrame(schema=schema_of(frames[0]))
    errors = _first_error(sections, section_index, schema_only, explain=True)
    if errors:
        return errors
    rows = _sample_rows(frames[0])
    if rows is None or rows.height == 0:
        return []
    return _first_error(sections, section_index, rows, explain=False)
