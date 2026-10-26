"""Ordered literal/regex find-and-replace over selected text columns."""

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

MAX_RULES = 50
MAX_PATTERN_LEN = 500
RULE_DEFAULTS = {
    "find": "",
    "replace": "",
    "mode": "literal",
    "case_sensitive": False,
    "whole_cell": False,
    "enabled": True,
}
DEFAULTS = {"columns": [], "rules": [], "suffix": ""}

_RUST_META = re.compile(r"([\\.+*?()|\[\]{}^$#&\-~])")


def escape_rust(text: str) -> str:
    return _RUST_META.sub(r"\\\1", text)


def _pattern(rule: dict) -> tuple[str, str]:
    if rule["mode"] == "regex":
        pattern, replacement = rule["find"], rule["replace"]
    else:
        pattern = escape_rust(rule["find"])
        replacement = rule["replace"].replace("$", "$$")
    if rule["whole_cell"]:
        pattern = f"^(?:{pattern})$"
    if not rule["case_sensitive"]:
        pattern = f"(?i){pattern}"
    return pattern, replacement


def validate_rules(rules: list[dict]) -> list[dict]:
    if len(rules) > MAX_RULES:
        raise ShapingError("TD-SHAPE-043", f"At most {MAX_RULES} rules are allowed")
    result = []
    for index, raw in enumerate(rules, start=1):
        rule = {**RULE_DEFAULTS, **raw}
        if rule["mode"] not in ("literal", "regex"):
            raise ShapingError("TD-SHAPE-004", f"Rule {index}: unknown mode")
        if rule["find"] == "":
            raise ShapingError("TD-SHAPE-042", f"Rule {index}: 'Find' is empty")
        if len(rule["find"]) > MAX_PATTERN_LEN:
            raise ShapingError(
                "TD-SHAPE-041",
                f"Rule {index}: pattern longer than {MAX_PATTERN_LEN}",
            )
        pattern, replacement = _pattern(rule)
        try:
            pl.select(pl.lit("").str.replace_all(pattern, replacement))
        except Exception as exc:
            raise ShapingError(
                "TD-SHAPE-040",
                f"Rule {index}: invalid pattern ({str(exc)[:80]})",
            ) from exc
        result.append(rule)
    return result


def _rule_expr(expr: pl.Expr, rule: dict) -> pl.Expr:
    if rule["mode"] == "literal" and rule["whole_cell"]:
        if rule["case_sensitive"]:
            hit = expr == rule["find"]
        else:
            hit = expr.str.to_lowercase() == rule["find"].lower()
        return pl.when(hit).then(pl.lit(rule["replace"])).otherwise(expr)
    if rule["mode"] == "literal" and rule["case_sensitive"] and not rule["whole_cell"]:
        return expr.str.replace_all(rule["find"], rule["replace"], literal=True)
    pattern, replacement = _pattern(rule)
    return expr.str.replace_all(pattern, replacement)


def _expr(column: str, rules: list[dict]) -> pl.Expr:
    expr = pl.col(column)
    for rule in rules:
        if rule["enabled"]:
            expr = _rule_expr(expr, rule)
    return expr


def apply_find_replace(frame: Frame, settings: dict) -> pl.LazyFrame:
    s = {**DEFAULTS, **(settings or {})}
    lf = as_lazy(frame)
    schema = schema_of(lf)
    columns = list(s["columns"] or [])
    if not columns:
        raise ShapingError("TD-SHAPE-001", "Pick at least one text column")
    require_columns(schema, columns)
    bad = [name for name in columns if schema[name] != pl.String]
    if bad:
        raise ShapingError(
            "TD-SHAPE-044",
            f"Column(s) must be text: {', '.join(bad)}",
            bad,
        )
    rules = validate_rules(list(s["rules"] or []))
    suffix = str(s["suffix"] or "")
    targets = [f"{name}{suffix}" for name in columns]
    if suffix:
        clashes = [name for name in targets if name in schema]
        if len(set(targets)) != len(targets) or clashes:
            raise ShapingError(
                "TD-SHAPE-002",
                "New column name already exists or repeats",
                clashes,
            )
    if not any(rule["enabled"] for rule in rules):
        return lf
    return lf.with_columns(
        [_expr(source, rules).alias(target) for source, target in zip(columns, targets)]
    )


def changed_cell_counts(frame: Frame, settings: dict) -> dict[str, int]:
    s = {**DEFAULTS, **(settings or {})}
    lf = as_lazy(frame)
    columns = list(s["columns"] or [])
    rules = validate_rules(list(s["rules"] or []))
    if not columns or not any(rule["enabled"] for rule in rules):
        return {}
    suffix = str(s["suffix"] or "")
    head = lf.head(10_000)
    try:
        original = head.select(columns).collect()
        changed = (
            head.with_columns(
                [
                    _expr(column, rules).alias(f"__chg_{i}")
                    for i, column in enumerate(columns)
                ]
            )
            .select([f"__chg_{i}" for i in range(len(columns))])
            .collect()
        )
    except Exception:  # noqa: BLE001
        return {}
    return {
        f"{column}{suffix}": int(
            original[column].ne_missing(changed[f"__chg_{i}"]).sum()
        )
        for i, column in enumerate(columns)
    }


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    try:
        counts = changed_cell_counts(frames[0], settings)
    except Exception:  # noqa: BLE001
        return []
    total = sum(counts.values())
    if not total:
        return [("No cells change in the first 10,000 rows", "warning")]
    return [(f"{total} cells change (first 10,000 rows)", "accent")]


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return [apply_find_replace(frames[0], settings)]
