"""Multi-Field Formula: one SQL expression applied to many columns (Qt-free).

The template holds ``{col}`` (the quoted column) and optionally ``{name}`` (the
column's name as a text literal). Every composed query goes through the shared
read-only guard in ``core/sql_guard.py`` and runs on a locked connection, so the
template can neither read files, run a second statement nor change the engine.
"""

from __future__ import annotations

import re

import polars as pl

from trigger_designer.core.shaping.common import (
    Frame,
    ShapingError,
    as_lazy,
    require_columns,
    schema_of,
)
from trigger_designer.core.sql_guard import check_select_only, mask, run_select
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes

MAX_COLUMNS = 200
MODES = ("in_place", "suffix")
DEFAULTS = {"columns": [], "template": "", "mode": "in_place", "suffix": "_new"}

_PLACEHOLDER = re.compile(r"\{col\}|\{name\}")


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def quote_text(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def expression_for(template: str, column: str) -> str:
    """Substitute the placeholders in one pass; parenthesised to keep precedence.

    One pass (not two ``replace`` calls) so a column literally named ``{name}``
    is not substituted a second time. The closing parenthesis sits on its own
    line so a trailing ``--`` comment in the template cannot swallow it.
    """
    quoted_ident, quoted_text = quote_ident(column), quote_text(column)
    body = _PLACEHOLDER.sub(
        lambda m: quoted_ident if m.group() == "{col}" else quoted_text, template
    )
    return f"({body}\n)"


def build_query(columns: list[str], template: str, mode: str, suffix: str) -> str:
    if mode == "in_place":
        parts = ", ".join(
            f"{expression_for(template, c)} AS {quote_ident(c)}" for c in columns
        )
        return f"SELECT * REPLACE ({parts}) FROM t1"
    parts = ", ".join(
        f"{expression_for(template, c)} AS {quote_ident(c + suffix)}" for c in columns
    )
    return f"SELECT *, {parts} FROM t1"


def normalize(settings: dict) -> dict:
    """Validate the settings that need no data; raise ``ShapingError``."""
    s = {**DEFAULTS, **(settings or {})}
    columns = list(dict.fromkeys(str(c) for c in (s["columns"] or [])))
    mode = str(s["mode"])
    template = str(s["template"] or "")
    suffix = str(s["suffix"] or "").strip()
    if not columns:
        raise ShapingError("TD-SHAPE-001", "Pick at least one column")
    if len(columns) > MAX_COLUMNS:
        raise ShapingError("TD-SHAPE-004", f"At most {MAX_COLUMNS} columns")
    if mode not in MODES:
        raise ShapingError("TD-SHAPE-004", f"Unknown mode {mode}")
    if "{col}" not in template:
        raise ShapingError("TD-SHAPE-120", "The formula must contain {col}")
    masked = mask(template)
    if ";" in masked:
        raise ShapingError("TD-SHAPE-110", "Only one expression is allowed")
    if mode == "suffix" and not suffix:
        raise ShapingError("TD-SHAPE-001", "Suffix is empty")
    return {"columns": columns, "template": template, "mode": mode, "suffix": suffix}


def _single_expression(template: str) -> bool:
    """Parentheses balance, so the template cannot close its own wrapper."""
    depth = 0
    for char in mask(template):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def apply_multi_formula(frame: Frame, settings: dict) -> pl.LazyFrame:
    s = normalize(settings)
    lf = as_lazy(frame)
    schema = schema_of(lf)
    columns = s["columns"]
    require_columns(schema, columns)
    if s["mode"] == "suffix":
        targets = [f"{c}{s['suffix']}" for c in columns]
        clashes = [t for t in targets if t in schema]
        if clashes:
            raise ShapingError("TD-SHAPE-002", "Output column already exists", clashes)
    query = build_query(columns, s["template"], s["mode"], s["suffix"])
    # The guard runs on the whole composed text first, so a template that
    # smuggles in a file read or a second statement is named by its own code;
    # run_select below reports anything the engine cannot parse as TD-SHAPE-113.
    check_select_only(query, allow_unparsable=True)
    if not _single_expression(s["template"]):
        raise ShapingError("TD-SHAPE-110", "Only one expression is allowed")
    out = run_select(query, {"t1": lf.collect()})
    return normalize_to_supported_dtypes(out).lazy()


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    try:
        s = normalize(settings)
    except ShapingError:
        return []
    count = len(s["columns"])
    noun = "column" if count == 1 else "columns"
    verb = "replaced" if s["mode"] == "in_place" else "added"
    return [(f"{count} {noun} {verb}", "accent")]


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return [apply_multi_formula(frames[0], settings)]
