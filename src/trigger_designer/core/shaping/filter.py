"""Filter: split rows into matching and non-matching outputs (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import (
    ShapingError,
    as_lazy,
    connect_duckdb,
    schema_of,
)
from trigger_designer.core.shaping.sql_expression import (
    prepare_expression_sql,
    shorten_error,
)

DEFAULTS = {
    "mode": "builder",
    "column": "",
    "operation": "Equals",
    "value": "",
    "value2": "",
    "expression": "",
}

_NUMERIC_OPERATIONS = [
    "Equals",
    "Not Equals",
    "Less Than",
    "Greater Than",
    "Less Than or Equal",
    "Greater Than or Equal",
    "In Between",
]
_STRING_OPERATIONS = ["Equals", "Not Equals", "Contains"]
_OTHER_OPERATIONS = ["Equals", "Not Equals"]
_DATE_TYPES = (pl.Date, pl.Datetime, pl.Time, pl.Duration)


def operations_for(dtype: pl.DataType | None) -> list[str]:
    """Operations the Simple builder offers for a column dtype."""
    if dtype is None:
        return list(_OTHER_OPERATIONS)
    if dtype in _DATE_TYPES:
        return list(_NUMERIC_OPERATIONS)
    if dtype == pl.String:
        return list(_STRING_OPERATIONS)
    if getattr(dtype, "is_numeric", lambda: False)():
        return list(_NUMERIC_OPERATIONS)
    return list(_OTHER_OPERATIONS)


def _as_number(text: str) -> float:
    try:
        return float(text)
    except TypeError, ValueError:
        raise ShapingError("TD-SHAPE-004", "Filter value must be a number") from None


def _builder_expression(
    column: str,
    dtype: pl.DataType,
    operation: str,
    value: str,
    value2: str,
) -> pl.Expr:
    numeric = getattr(dtype, "is_numeric", lambda: False)()
    if operation == "In Between":
        if numeric:
            low, high = _as_number(value), _as_number(value2)
            if low > high:
                low, high = high, low
            return pl.col(column).is_between(low, high, closed="both")
        return pl.col(column).is_between(value, value2, closed="both")

    converted = _as_number(value) if numeric else value
    expression = pl.col(column)
    if operation == "Equals":
        return expression == converted
    if operation == "Not Equals":
        return expression != converted
    if operation == "Contains":
        return expression.str.contains(value)
    if operation == "Less Than":
        return expression < converted
    if operation == "Greater Than":
        return expression > converted
    if operation == "Less Than or Equal":
        return expression <= converted
    if operation == "Greater Than or Equal":
        return expression >= converted
    raise ShapingError("TD-SHAPE-004", f"Unsupported filter operation: {operation}")


def _builder_outputs(frame: pl.LazyFrame, settings: dict) -> list[pl.LazyFrame]:
    column = str(settings.get("column") or "")
    if not column:
        return [frame, frame.head(0)]

    schema = schema_of(frame)
    if column not in schema:
        raise ShapingError("TD-SHAPE-003", f"Column(s) not found: {column}", [column])

    operation = str(settings.get("operation") or "Equals")
    value = "" if settings.get("value") is None else str(settings.get("value"))
    value2 = "" if settings.get("value2") is None else str(settings.get("value2"))
    if not value or (operation == "In Between" and not value2):
        # Incomplete configuration passes rows through, as the old code did.
        return [frame, frame.head(0)]

    expression = _builder_expression(column, schema[column], operation, value, value2)
    return [frame.filter(expression), frame.filter(~expression)]


def _expression_outputs(
    frame: pl.LazyFrame, expression_text: str
) -> list[pl.LazyFrame]:
    text = (expression_text or "").strip()
    if not text:
        return [frame, frame.head(0)]

    try:
        prepared = prepare_expression_sql(text, list(schema_of(frame)))
        with connect_duckdb() as duck:
            duck.register("df_filter", frame)
            # Eager .pl(): a lazy result streams from this connection after
            # the with-block closes, which fails. Materialise now.
            matched = duck.sql(f"SELECT * FROM df_filter WHERE {prepared}").pl()
            unmatched = duck.sql(f"SELECT * FROM df_filter WHERE NOT ({prepared})").pl()
    except Exception as exc:  # noqa: BLE001 - engine errors become a stable code
        raise ShapingError("TD-SHAPE-004", shorten_error(str(exc))) from None
    return [matched.lazy(), unmatched.lazy()]


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    settings = {**DEFAULTS, **(settings or {})}
    frame = as_lazy(frames[0])
    if settings["mode"] == "expression":
        return _expression_outputs(frame, str(settings["expression"] or ""))
    return _builder_outputs(frame, settings)


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    settings = {**DEFAULTS, **(settings or {})}
    if settings["mode"] == "expression":
        if not str(settings.get("expression") or "").strip():
            return [("No expression: rows pass through", "warning")]
        return []
    if not str(settings.get("column") or ""):
        return [("No condition: rows pass through", "warning")]
    if not settings.get("value") or (
        settings.get("operation") == "In Between" and not settings.get("value2")
    ):
        return [("Incomplete condition: rows pass through", "warning")]
    return []
