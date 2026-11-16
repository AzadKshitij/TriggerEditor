"""Checks every value an edit writes into a workflow (Qt-free).

Three layers, all structured errors and none of them guessing:

* **shape**: the key is one of the node's settings and the value has the type
  its default has (``core/headless/node_spec.settings_schema``). The editor's
  own labels and choices are not loaded here (they need Qt); the node still
  checks its choices when it runs.
* **paths**: a setting that names a file may only point into the workflow's
  folder or a folder the data owner's policy lists, so an edit cannot aim an
  output at, or read from, somewhere else.
* **SQL**: SQL text goes through ``core/sql_guard.check_select_only``, the same
  guard that runs when the node executes, so a bad query is refused before it is
  saved.
"""

from __future__ import annotations

import difflib
import json
import math
import os
from functools import cache
from typing import Any

from trigger_designer.core.authoring.model import (
    INVALID_SETTING,
    PATH_NOT_ALLOWED,
    SQL_REJECTED,
    fail,
)
from trigger_designer.core.headless.exit_codes import ExitCode
from trigger_designer.core.headless.node_spec import settings_schema
from trigger_designer.core.headless.op_catalog import OPS

MAX_SETTINGS_CHARS = 1_000_000
MAX_TEXT_CHARS = 200_000
MAX_TITLE_CHARS = 200
MAX_LABEL_CHARS = 500


@cache
def _schema(op: str) -> dict:
    return settings_schema(op)


def allowed_keys(op: str) -> list[str]:
    return list(_schema(op).get("properties", {}))


# -------------------------------------------------------------------- shape
def _type_ok(kind: str, value: Any) -> bool:
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )
    if kind == "string":
        return isinstance(value, str) and len(value) <= MAX_TEXT_CHARS
    if kind == "array":
        return isinstance(value, list)
    if kind == "object":
        return isinstance(value, dict)
    return True


def validate_value(schema: dict | None, value: Any, where: str) -> str | None:
    """A problem description, or ``None`` when ``value`` fits ``schema``."""
    if not schema:
        return None
    kind = schema.get("type")
    if kind and not _type_ok(kind, value):
        return f"{where} must be {_article(kind)}, not {_describe(value)}"
    if "enum" in schema and value not in schema["enum"]:
        return f"{where} must be one of {schema['enum']}, not {value!r}"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        low, high = schema.get("minimum"), schema.get("maximum")
        if low is not None and value < low:
            return f"{where} must be at least {low}"
        if high is not None and value > high:
            return f"{where} must be at most {high}"
    if kind == "array":
        limit = schema.get("maxItems")
        if limit is not None and len(value) > limit:
            return f"{where} can have at most {limit} items"
        item_schema = schema.get("items")
        for i, item in enumerate(value):
            problem = validate_value(item_schema, item, f"{where}[{i}]")
            if problem:
                return problem
    if kind == "object":
        props = schema.get("properties") or {}
        for key, item in value.items():
            problem = validate_value(props.get(key), item, f"{where}.{key}")
            if problem:
                return problem
    return None


def _article(kind: str) -> str:
    return {"array": "a list", "object": "an object"}.get(
        kind, f"a {kind}" if kind != "integer" else "a whole number"
    )


def _describe(value: Any) -> str:
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "an object"
    return "nothing" if value is None else type(value).__name__


# -------------------------------------------------------------------- paths
def _inside(path: str, root: str) -> bool:
    p = os.path.normcase(os.path.abspath(path))
    r = os.path.normcase(os.path.abspath(root)).rstrip("\\/")
    return p == r or p.startswith(r + os.sep)


def check_path(value: str, key: str, base_dir: str, extra: tuple[str, ...]) -> None:
    """Refuse a file setting that points outside the allowed folders."""
    if "\x00" in value:
        raise fail(PATH_NOT_ALLOWED, f"{key} contains an invalid character.")
    resolved = os.path.join(base_dir, value)
    roots = (base_dir, *extra)
    if any(_inside(resolved, root) for root in roots):
        return
    raise fail(
        PATH_NOT_ALLOWED,
        f"{key} '{value}' is outside the folders an edit may use.",
        "Use a path inside the workflow's folder, or ask the data owner to list "
        'the folder under "paths" in the agent policy file.',
        ExitCode.REFUSED,
    )


# ---------------------------------------------------------------------- SQL
def _guard(sql: str, key: str, *, loose: bool) -> None:
    from trigger_designer.core.shaping.common import ShapingError
    from trigger_designer.core.sql_guard import check_select_only

    try:
        check_select_only(sql, allow_unparsable=loose)
    except ShapingError as exc:
        raise fail(
            SQL_REJECTED,
            f"The SQL in '{key}' was refused: {exc.detail} ({exc.code}).",
            "Only one read-only SELECT is allowed: no files, no system or random "
            "functions, no changes.",
        ) from None


def _fragments(op: str, key: str, value: Any) -> list[tuple[str, bool]]:
    """(statement to check, loose?) for each piece of SQL in ``key``. A fragment
    is wrapped the way the node builds its query before it is checked."""
    if not isinstance(value, (str, list)):
        return []
    if op == "transform.sql_query" and key == "sql":
        return [(value, False)]
    if op == "preparation.filter" and key == "expression" and str(value).strip():
        return [(f"SELECT * FROM df_filter WHERE {value}", True)]
    if op == "preparation.formula" and key == "sections":
        out = []
        for section in value:
            text = section.get("formula_text") if isinstance(section, dict) else None
            if isinstance(text, str) and text.strip():
                out.append((f"SELECT {text} FROM df_formula", True))
        return out
    if (
        op == "preparation.multi_field_formula"
        and key == "template"
        and str(value).strip()
    ):
        return [(f"SELECT {str(value).replace('{col}', 'x')} FROM df", True)]
    return []


class Raw(str):
    """Text typed on a command line (``--set NAME=VALUE``): it becomes the type
    the setting has, so ``10000`` is text for a text setting and a number for a
    number setting. JSON edit lists carry real types and never use this."""


def coerce_raw(op: str, settings: dict) -> dict:
    """``settings`` with every :class:`Raw` value turned into its setting's type
    where that is possible; a value that does not fit is left for the type check
    to refuse."""
    props = _schema(op).get("properties", {})
    out = {}
    for key, value in settings.items():
        if isinstance(value, Raw):
            kind = (props.get(key) or {}).get("type")
            text = str(value)
            if kind not in (None, "string"):
                try:
                    out[key] = json.loads(text)
                    continue
                except ValueError:
                    pass
            out[key] = text
        else:
            out[key] = value
    return out


# --------------------------------------------------------------------- main
def check_settings(
    op: str,
    settings: dict,
    *,
    base_dir: str,
    extra_paths: tuple[str, ...] = (),
) -> None:
    """Raise a structured error unless every key/value in ``settings`` is allowed."""
    if not isinstance(settings, dict):
        raise fail(INVALID_SETTING, "settings must be an object of name: value.")
    try:
        size = len(json.dumps(settings, ensure_ascii=False))
    except TypeError, ValueError:
        raise fail(INVALID_SETTING, "settings must be plain JSON values.") from None
    if size > MAX_SETTINGS_CHARS:
        raise fail(INVALID_SETTING, "settings are too large.")
    schema = _schema(op)
    props = schema.get("properties", {})
    info = OPS[op]
    file_keys = {*info.input_keys, *info.output_keys, *info.list_keys}
    for key, value in settings.items():
        if key not in props:
            near = difflib.get_close_matches(str(key), list(props), n=3, cutoff=0.5)
            hint = "Settings of this node: " + (", ".join(props) or "none") + "."
            if near:
                hint = "Did you mean: " + ", ".join(near) + "? " + hint
            raise fail(
                INVALID_SETTING, f"'{key}' is not a setting of {info.title}.", hint
            )
        problem = validate_value(props[key], value, key)
        if problem:
            raise fail(
                INVALID_SETTING,
                f"{info.title}: {problem}.",
                f"Run `ops {op}` for the type and default of each setting.",
            )
        if key in file_keys and isinstance(value, str):
            for line in value.splitlines() or [""]:
                if line.strip():
                    check_path(line.strip(), key, base_dir, extra_paths)
        for statement, loose in _fragments(op, key, value):
            _guard(statement, key, loose=loose)
