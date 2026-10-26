"""One central exception-to-NodeError translator.

Qt-free and total: every path returns a NodeError. The ordered rules follow
the catalogue table; raw engine text is only ever kept in ``technical``.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass

from trigger_designer.core.errors.catalogue import CATALOGUE, render_entry
from trigger_designer.core.errors.model import (
    ErrorContext,
    NodeError,
    SuggestedFix,
    normalise_path,
    shorten,
)
from trigger_designer.core.errors.redact import redact_error
from trigger_designer.core.errors.suggest import suggest_names

_ANY = None
_CODE_RE = re.compile(r"(?:^|\[)(?P<code>TD-[A-Z]+-\d{3})(?:\]|:)")
_OS_RE = re.compile(r"\(os error (?P<n>\d+)\)(?::\s*(?P<path>.+?))?\s*$", re.DOTALL)
_NUMERIC = re.compile(r"^(?:[iu]\d+|f\d+)$")
_DUCK_NUMERIC = re.compile(r"^[A-Z0-9_]+$")
_PLAN_NOISE = (
    "Resolved plan",
    "Candidate bindings",
    "LINE ",
    "Context:",
    "Sheet ",
)


@dataclass(frozen=True)
class Facts:
    names: tuple[str, ...]
    text: str
    first_line: str
    exc: BaseException | str | None


@dataclass(frozen=True)
class Rule:
    id: int
    codes: tuple[str, ...]
    names: frozenset[str] | None
    pattern: re.Pattern[str] | None
    build: Callable[[Facts, ErrorContext, re.Match[str] | None], tuple | None]


class _TextError(Exception):
    pass


def _safe_str(exc: object) -> str:
    try:
        text = str(exc)
    except Exception:  # noqa: BLE001 - a broken __str__ must not break us
        try:
            return repr(type(exc))
        except Exception:  # noqa: BLE001
            return "<unprintable exception>"
    return text


def _names(exc: object) -> tuple[str, ...]:
    try:
        return tuple(cls.__name__ for cls in type(exc).__mro__)
    except Exception:  # noqa: BLE001
        return ()


def _facts(exc: BaseException | str | None) -> Facts:
    if exc is None:
        text = ""
    elif isinstance(exc, str):
        text = exc
    else:
        text = _safe_str(exc)
    return Facts(
        names=_names(exc),
        text=text[:20_000],
        first_line=next(
            (line.strip() for line in text.splitlines() if line.strip()), ""
        ),
        exc=exc,
    )


def _unwrap(exc: BaseException | str | None):
    seen: set[int] = set()
    current = exc
    for _ in range(5):
        if current is None or isinstance(current, str):
            return current
        ident = id(current)
        if ident in seen:
            return current
        seen.add(ident)
        name = type(current).__name__
        if name in ("ExecutionTimeoutError", "ExecutionMemoryError"):
            return current
        nxt = getattr(current, "original_exception", None)
        if nxt is None:
            return current
        current = nxt
    return current


def _reason(text: str, limit: int = 160) -> str:
    for line in str(text or "").splitlines():
        value = line.strip()
        if not value:
            continue
        if value.startswith(_PLAN_NOISE):
            continue
        return shorten(value, limit)
    return ""


def _parse_quoted_list(text: str) -> list[str]:
    values = re.findall(r'"((?:[^"\\]|\\.)*)"', text or "")
    if values:
        return [item.replace('\\"', '"') for item in values]
    return [item.strip() for item in str(text or "").split(",") if item.strip()]


def _parse_values(text: str) -> list[str]:
    values = re.findall(r'"((?:[^"\\]|\\.)*)"', text or "")
    if values:
        return [item.replace('\\"', '"') for item in values]
    values = re.findall(r"'((?:[^'\\]|\\.)*)'", text or "")
    if values:
        return [item.replace("\\'", "'") for item in values]
    return [item.strip() for item in str(text or "").split(",") if item.strip()]


def _target_pair(target: str) -> tuple[str, str, str]:
    value = (target or "").strip()
    low = value.lower()
    if re.match(r"^[iu]\d+$", low) or low in {
        "tinyint",
        "smallint",
        "int32",
        "integer",
        "int64",
        "bigint",
    }:
        return "a whole number", "whole numbers", "INTEGER"
    if re.match(r"^f\d+$", low) or low in {"float", "double"}:
        return "a number", "numbers", "DOUBLE"
    if low.startswith("decimal"):
        return "a decimal number", "decimal numbers", "DECIMAL(18,2)"
    if low in {"date"}:
        return "a date", "dates", "DATE"
    if low.startswith("datetime") or low in {"timestamp"}:
        return "a date and time", "dates and times", "TIMESTAMP"
    if low in {"time"}:
        return "a time", "times", "TIME"
    if low in {"bool", "boolean"}:
        return "a true/false value", "true/false values", "BOOLEAN"
    return value or "the target type", value or "the target type", "DOUBLE"


def _op_past(value: str) -> str:
    return {
        "sum": "summed",
        "mean": "averaged",
        "cum_sum": "added up",
        "min": "compared",
        "max": "compared",
        "median": "averaged",
        "std": "averaged",
        "var": "averaged",
    }.get(value, "used in this calculation")


def _single_input_path(ctx: ErrorContext) -> str:
    if len(ctx.input_paths) == 1:
        return next(iter(ctx.input_paths))
    return ""


def _io_rule(
    facts: Facts, ctx: ErrorContext, number: int, path: str
) -> tuple[str, dict] | None:
    path = re.sub(r"\s*\(set POLARS_VERBOSE=1 to see full path\)\s*$", "", path or "")
    normalized = normalise_path(path) if path else ""
    dirname = os.path.dirname(normalized) if normalized else ""
    output_dirs = {os.path.dirname(item) for item in ctx.output_paths if item}
    input_owner = ctx.input_paths.get(normalized)
    output_owner = ctx.output_paths.get(normalized)
    if input_owner is None and normalized:
        basename = os.path.basename(normalized)
        input_owner = next(
            (
                node_id
                for candidate, node_id in ctx.input_paths.items()
                if os.path.basename(candidate) == basename
            ),
            None,
        )
    if output_owner is None and normalized:
        basename = os.path.basename(normalized)
        output_owner = next(
            (
                node_id
                for candidate, node_id in ctx.output_paths.items()
                if os.path.basename(candidate) == basename
            ),
            None,
        )
    if output_owner is not None or (dirname and dirname in output_dirs):
        role = "out"
    elif input_owner is not None:
        role = "in"
    else:
        role = "out" if (ctx.op or "").endswith("file_output") else "in"

    table = {
        (2, "in"): "TD-IN-001",
        (3, "in"): "TD-IN-001",
        (21, "in"): "TD-IN-001",
        (2, "out"): "TD-OUT-001",
        (3, "out"): "TD-OUT-001",
        (21, "out"): "TD-OUT-004",
        (5, "in"): "TD-IN-002",
        (13, "in"): "TD-IN-002",
        (5, "out"): "TD-OUT-002",
        (13, "out"): "TD-OUT-002",
        (32, "in"): "TD-IN-002",
        (32, "out"): "TD-OUT-002",
        (123, "in"): "TD-IN-001",
        (206, "in"): "TD-IN-001",
        (123, "out"): "TD-OUT-004",
        (206, "out"): "TD-OUT-004",
        (112, "in"): "TD-IN-002",
        (28, "in"): "TD-IN-002",
        (112, "out"): "TD-OUT-005",
        (28, "out"): "TD-OUT-005",
    }
    code = table.get((number, role))
    if code is None:
        return None
    params: dict = {
        "path": path,
        "path_name": os.path.basename(path) if path else "",
        "reason": _reason(facts.text),
    }
    owner = output_owner if role == "out" else input_owner
    if owner is not None:
        params["culprit_node_id"] = owner
        label = ctx.node_labels.get(owner)
        if label:
            params["culprit_label"] = label
    return code, params


def _rule_io(facts: Facts, ctx: ErrorContext, match) -> tuple | None:
    number = None
    if match is not None:
        number = int(match.group("n"))
    path = ""
    if match is not None:
        path = (match.group("path") or "").strip()
    if not path:
        match_os = _OS_RE.search(facts.text)
        if match_os:
            number = number if number is not None else int(match_os.group("n"))
            path = (match_os.group("path") or "").strip()
    exc = facts.exc
    if not path:
        try:
            path = getattr(exc, "filename", None) or ""
        except Exception:  # noqa: BLE001
            path = ""
    if number is None:
        number = {
            "FileNotFoundError": 2,
            "PermissionError": 5,
            "IsADirectoryError": 21,
        }.get(type(exc).__name__)
    if number is None:
        return None
    return _io_rule(facts, ctx, int(number), str(path))


def _rule_1(facts, ctx, _m):
    match = re.search(r"timed out after ([\d.]+) seconds", facts.text)
    seconds = match.group(1) if match else ""
    seconds = seconds.removesuffix(".0")
    return "TD-RUN-001", {"seconds": seconds}


def _rule_2(facts, ctx, _m):
    match = re.search(r"Memory usage exceeded limit: ([\d.]+)MB", facts.text)
    reason = (
        f"Limit exceeded by {match.group(1)} MB."
        if match
        else "No more memory could be allocated."
    )
    return "TD-RUN-002", {"reason": reason}


def _rule_3(facts, ctx, _m):
    return "TD-SYS-998", {"reason": _reason(facts.text)}


def _rule_4(facts, ctx, _m):
    return "TD-OUT-003", {"reason": _reason(facts.text)}


def _rule_5(facts, ctx, _m):
    return "TD-OUT-006", {}


def _rule_6(facts, ctx, _m):
    sheet = ""
    named = re.search(r'sheet with name "([^"]+)" not found', facts.text)
    indexed = re.search(r"Sheet index (\d+) is out of range", facts.text)
    if named:
        sheet = named.group(1)
    elif indexed:
        sheet = indexed.group(1)
    available_match = re.search(
        r"Available sheets:\s*(.+?)(?:\.|\n|$)", facts.text, re.DOTALL
    )
    available = _parse_quoted_list(available_match.group(1)) if available_match else []
    suggestion = suggest_names(sheet, available)[:1]
    return "TD-IN-003", {
        "sheet": sheet,
        "available": ", ".join(available),
        "suggestion": suggestion[0] if suggestion else "",
        "__samples": tuple(suggestion),
        "path_name": os.path.basename(_single_input_path(ctx)),
    }


def _rule_9(facts, ctx, _m):
    if "UnicodeDecodeError" not in facts.names and "invalid utf-8" not in facts.text:
        return None
    path = _single_input_path(ctx)
    reason = ""
    exc = facts.exc
    if isinstance(exc, UnicodeDecodeError):
        reason = f"The bytes at position {exc.start} are not valid UTF-8."
    return "TD-IN-004", {
        "path": path,
        "path_name": os.path.basename(path) if path else "",
        "reason": reason or _reason(facts.text),
    }


def _rule_10(facts, ctx, _m):
    path = _single_input_path(ctx)
    return "TD-IN-005", {
        "path": path,
        "path_name": os.path.basename(path) if path else "",
    }


def _rule_11(facts, ctx, _m):
    return "TD-IN-007", {}


def _rule_12(facts, ctx, _m):
    path = _single_input_path(ctx)
    return "TD-IN-006", {
        "path": path,
        "path_name": os.path.basename(path) if path else "",
        "reason": _reason(facts.text),
    }


def _rule_13(facts, ctx, _m):
    match = re.search(
        r"conversion from `(?P<src>[^`]+)` to `(?P<dst>[^`]+)` failed in column "
        r"'(?P<col>.+?)' for (?P<n>\d+) out of (?P<m>\d+) values: "
        r"\[(?P<vals>.*?)\]\s*$",
        facts.text,
        re.DOTALL | re.MULTILINE,
    )
    if not match:
        return None
    values = _parse_values(match.group("vals"))
    src, dst = match.group("src"), match.group("dst")
    overflow = bool(_NUMERIC.match(src) and _NUMERIC.match(dst))
    return ("TD-TYP-005" if overflow else "TD-TYP-001"), {
        "column": match.group("col"),
        "target": dst,
        "source": src,
        "value": values[0] if values else "",
        "__samples": tuple(values),
        "__failing_count": int(match.group("n")) if ctx.phase == "live" else None,
        "reason": _reason(facts.text),
    }


def _rule_14(facts, ctx, _m):
    match = re.search(
        r"strict integer parsing failed for (?P<n>\d+) value\(s\): "
        r"\[(?P<vals>.*?)\]",
        facts.text,
        re.DOTALL,
    )
    if not match:
        return None
    values = _parse_values(match.group("vals"))
    column = next(
        (
            name
            for name in ctx.referenced_columns
            if ctx.input_dtypes.get(name) == "String"
        ),
        "",
    )
    return "TD-TYP-001", {
        "column": column,
        "target": "i64",
        "value": values[0] if values else "",
        "__samples": tuple(values),
        "reason": _reason(facts.text),
    }


def _rule_15(facts, ctx, _m):
    pattern = re.compile(
        r"Could not convert string (?P<q>['\"])(?P<val>.*?)(?P=q) to "
        r"(?P<dst>[A-Z0-9_(),\s]+?)(?: when casting from source column "
        r"(?P<col>.+?))?\s*(?:\n|$)",
        re.DOTALL,
    )
    match = pattern.search(facts.text)
    if match:
        return "TD-TYP-001", {
            "column": (match.group("col") or "").strip(),
            "target": match.group("dst").strip(),
            "value": match.group("val"),
            "__samples": (match.group("val"),),
            "engine_duckdb": "1",
            "reason": _reason(facts.text),
        }
    date_match = re.search(
        r'invalid date field format: "(?P<val>.*?)", expected format is '
        r".*?(?: when casting from source column (?P<col>.+?))?\s*(?:\n|$)",
        facts.text,
        re.DOTALL,
    )
    if date_match:
        return "TD-TYP-001", {
            "column": (date_match.group("col") or "").strip(),
            "target": "DATE",
            "value": date_match.group("val"),
            "__samples": (date_match.group("val"),),
            "engine_duckdb": "1",
            "reason": _reason(facts.text),
        }
    parse_match = re.search(
        r'Could not parse string "(?P<val>.*?)" according to format specifier '
        r'"(?P<fmt>.*?)"',
        facts.text,
        re.DOTALL,
    )
    if parse_match:
        column = ctx.referenced_columns[0] if ctx.referenced_columns else ""
        return "TD-TYP-001", {
            "column": column,
            "target": "DATE",
            "date_format": parse_match.group("fmt"),
            "value": parse_match.group("val"),
            "__samples": (parse_match.group("val"),),
            "engine_duckdb": "1",
            "reason": _reason(facts.text),
        }
    if "Conversion Error:" in facts.text:
        return "TD-TYP-001", {
            "column": "",
            "target": "",
            "engine_duckdb": "1",
            "reason": _reason(facts.text),
        }
    return None


def _rule_17(facts, ctx, _m):
    match = re.search(
        r"datatypes of join keys don't match - `(?P<left_key>[^`]+)`: "
        r"(?P<left_type>\S+) on left does not match `(?P<right_key>[^`]+)`: "
        r"(?P<right_type>\S+) on right",
        facts.text,
        re.DOTALL,
    )
    if not match:
        return None
    return "TD-TYP-002", {
        **match.groupdict(),
        "columns": (match.group("left_key"), match.group("right_key")),
    }


def _schema_map(text: str) -> dict[str, str]:
    return {
        name: dtype.strip()
        for name, dtype in re.findall(r'"([^"]+)":\s*([A-Za-z0-9_\[\]\(\), ]+)', text)
    }


def _rule_18(facts, ctx, _m):
    match = re.search(
        r"Schema \{ fields: \{(?P<a>.*?)\}, metadata.*?\} and\s+"
        r"Schema \{ fields: \{(?P<b>.*?)\}, metadata",
        facts.text,
        re.DOTALL,
    )
    if not match:
        return None
    left, right = _schema_map(match.group("a")), _schema_map(match.group("b"))
    missing = [name for name in left if name not in right]
    extra = [name for name in right if name not in left]
    differing = [
        f"{name} ({left[name]} vs {right[name]})"
        for name in left.keys() & right.keys()
        if left[name] != right[name]
    ]
    bits = []
    if missing:
        bits.append("missing in right: " + ", ".join(missing))
    if extra:
        bits.append("only in right: " + ", ".join(extra))
    if differing:
        bits.append("type differs: " + ", ".join(differing))
    return "TD-SCH-004", {"differences": "; ".join(bits) or _reason(facts.text)}


def _rule_19(facts, ctx, _m):
    match = re.search(r"'([^']+)'", facts.text)
    return "TD-SCH-002", {"column": match.group(1) if match else ""}


def _rule_20(facts, ctx, _m):
    match = re.search(
        r'unable to find column "(?P<col>.*?)"; valid columns: '
        r"\[(?P<valid>.*?)\]",
        facts.text,
        re.DOTALL,
    )
    if match:
        column = match.group("col")
        available = _parse_quoted_list(match.group("valid"))
    else:
        match = re.search(r'^"?(?P<col>[^"\n]+)"? not found', facts.text)
        if not match:
            match = re.search(r"^`?(?P<col>[^`\n]+)`?$", facts.first_line)
        column = match.group("col").strip() if match else facts.first_line
        available = list(ctx.input_columns)
    suggestion = suggest_names(column, available)
    return "TD-SCH-001", {
        "column": column,
        "available": ", ".join(available),
        "suggestion": suggestion[0] if suggestion else "",
        "__suggestions": suggestion,
        "__samples": suggestion,
    }


def _rule_21(facts, ctx, _m):
    match = re.search(
        r'Referenced column "(?P<col>.*?)" not found in FROM clause!'
        r"(?:\s*Candidate bindings: (?P<cands>.*?)\n)?",
        facts.text,
        re.DOTALL,
    )
    if not match:
        match = re.search(r'does not have a column named "(?P<col>.*?)"', facts.text)
        cands = ""
        if not match:
            return None
    else:
        cands = match.group("cands") or ""
    column = match.group("col")
    available = _parse_quoted_list(cands) if cands else list(ctx.input_columns)
    suggestion = suggest_names(column, available)
    return "TD-SCH-001", {
        "column": column,
        "available": ", ".join(available),
        "suggestion": suggestion[0] if suggestion else "",
        "__suggestions": suggestion,
        "__samples": suggestion,
        "engine_duckdb": "1",
    }


def _rule_22(facts, ctx, _m):
    op = ""
    dtype = ""
    match = re.search(
        r"`(?P<op>\w+)` operation not supported for dtype `(?P<dtype>[^`]+)`",
        facts.text,
    )
    if match:
        op, dtype = match.group("op"), match.group("dtype")
    else:
        match = re.search(
            r"No function matches the given name and argument types "
            r"'(?P<fn>[^(']+)\((?P<args>[^)]*)\)'",
            facts.text,
        )
        if not match:
            return None
        op, dtype = match.group("fn"), match.group("args")
        if "VARCHAR" not in dtype and "STRING" not in dtype.upper():
            return None
    if dtype.lower() not in {"str", "string", "varchar"} and "VARCHAR" not in dtype:
        return None
    candidates = [
        name
        for name in ctx.referenced_columns
        if ctx.input_dtypes.get(name) == "String"
    ]
    if not candidates:
        candidates = [
            name for name in ctx.input_columns if ctx.input_dtypes.get(name) == "String"
        ][:5]
    return "TD-TYP-003", {
        "column": candidates[0] if candidates else "",
        "columns": tuple(candidates),
        "op_past": _op_past(op),
        "sum_mode": "1",
        "engine_duckdb": "1" if "No function matches" in facts.text else "",
        "reason": _reason(facts.text),
    }


def _rule_23(facts, ctx, _m):
    match = re.search(
        r"Cannot compare values of type (?P<a>\w+) and type (?P<b>\w+)",
        facts.text,
    )
    reason = (
        f"Cannot compare {match.group('a')} with {match.group('b')}."
        if match
        else _reason(facts.text)
    )
    return "TD-TYP-004", {"reason": reason}


def _rule_24(facts, ctx, _m):
    match = re.search(
        r"filter predicate must be of type `Boolean`, got `(?P<got>[^`]+)`",
        facts.text,
    )
    return "TD-TYP-007", {"got": match.group("got") if match else ""}


def _rule_25(facts, ctx, _m):
    match = re.search(
        r"invalid dtype: expected '(?P<expected>[^']+)', got '(?P<got>[^']+)' "
        r"for '(?P<column>[^']+)'",
        facts.text,
    )
    if not match:
        return None
    return "TD-TYP-006", {
        **match.groupdict(),
        "columns": (match.group("column"),),
    }


def _rule_26(facts, ctx, _m):
    return "TD-SCH-005", {"reason": _reason(facts.text)}


def _syntax_reason(text: str) -> str:
    value = _reason(text)
    low = value.lower()
    if re.search(r"[+\-*/]\s+AS\b", text, re.IGNORECASE):
        return (
            "The expression ends too early. Add the missing value after the operator."
        )
    if "unterminated quoted string" in low:
        return "A text value is missing its closing quote."
    if "syntax error at end of input" in low:
        return "The expression ends too early."
    match = re.search(r'syntax error at or near "(?P<x>[^"]+)"', value)
    if match:
        return f"Unexpected '{match.group('x')}'."
    return value


def _rule_27(facts, ctx, _m):
    return "TD-EXP-001", {"reason": _syntax_reason(facts.text)}


def _rule_28(facts, ctx, _m):
    match = re.search(
        r"(?:Scalar|Aggregate|Table) Function with name (?P<function>\S+) "
        r"does not exist!(?:\s*Did you mean \"(?P<sug>[^\"]+)\"?)?",
        facts.text,
    )
    if not match:
        return None
    function = match.group("function").strip('"')
    suggestion = match.group("sug") or ""
    if not suggestion:
        candidates = [
            "length",
            "lower",
            "upper",
            "trim",
            "coalesce",
            "round",
            "substr",
            "replace",
            "concat",
            "strptime",
            "strftime",
            "try_cast",
        ]
        found = suggest_names(function, candidates)
        suggestion = found[0] if found else ""
    return "TD-EXP-002", {
        "function": function,
        "suggestion": suggestion,
        "__suggestions": (suggestion,) if suggestion else (),
        "__samples": (suggestion,) if suggestion else (),
    }


def _rule_29(facts, ctx, _m):
    matches = re.findall(r"error: ([^\n]+)", facts.text)
    reason = matches[-1] if matches else _reason(facts.text)
    return "TD-EXP-004", {"reason": shorten(reason, 160)}


def _rule_30(facts, ctx, _m):
    return "TD-EXP-003", {"reason": _reason(facts.text)}


def _rule_31(facts, ctx, _m):
    return "TD-EXP-005", {"reason": _reason(facts.text)}


def _rule_sqlglot_syntax(facts, ctx, _m):
    return "TD-EXP-001", {
        "reason": (
            "The expression ends too early. Add the missing value after the operator."
        )
    }


def _rule_33(facts, ctx, _m):
    match = re.search(r"name '(?P<var>[^']+)' is not defined", facts.text)
    variable = match.group("var") if match else ""
    owner = ctx.variable_owners.get(variable)
    params = {"var": variable, "reason": _reason(facts.text)}
    if owner is not None:
        params["culprit_node_id"] = owner
        label = ctx.node_labels.get(owner)
        if label:
            params["culprit_label"] = label
    return "TD-RUN-006", params


def _rule_34(facts, ctx, _m):
    module = ""
    try:
        module = type(facts.exc).__module__
    except Exception:  # noqa: BLE001, S110
        pass
    if module.startswith("polars") or "OutOfBoundsError" in facts.names:
        return "TD-SYS-100", {"reason": _reason(facts.text)}
    return "TD-SYS-001", {"message": shorten(facts.text, 160)}


def _rule_35(facts, ctx, _m):
    try:
        if type(facts.exc).__module__.startswith("polars"):
            return "TD-SYS-100", {"reason": _reason(facts.text)}
    except Exception:  # noqa: BLE001, S110
        pass
    return None


def _rule_36(facts, ctx, _m):
    return "TD-SYS-999", {"reason": shorten(facts.text or repr(facts.exc), 160)}


def _build_rules() -> tuple[Rule, ...]:
    def rule(rid, codes, names, build, pattern=None):
        return Rule(
            rid, tuple(codes), frozenset(names) if names else None, pattern, build
        )

    return (
        rule(1, ("TD-RUN-001",), {"ExecutionTimeoutError"}, _rule_1),
        rule(
            2,
            ("TD-RUN-002",),
            {"ExecutionMemoryError", "MemoryError", "OutOfMemoryException"},
            _rule_2,
        ),
        rule(3, ("TD-SYS-998",), {"PanicException"}, _rule_3),
        rule(
            4,
            ("TD-OUT-003",),
            {"ModuleNotFoundError", "ImportError"},
            _rule_4,
            re.compile(r"xlsxwriter"),
        ),
        rule(
            5,
            ("TD-OUT-006",),
            {"ValueError"},
            _rule_5,
            re.compile(r"no incoming data - connect an input"),
        ),
        rule(6, ("TD-IN-003",), {"SheetNotFoundError"}, _rule_6),
        rule(
            7,
            ("TD-IN-006",),
            {"CalamineError", "FastExcelError"},
            _rule_io,
            re.compile(r"\(os error (?P<n>\d+)\)"),
        ),
        rule(
            8,
            (
                "TD-IN-001",
                "TD-IN-002",
                "TD-OUT-001",
                "TD-OUT-002",
                "TD-OUT-004",
                "TD-OUT-005",
            ),
            {
                "FileNotFoundError",
                "PermissionError",
                "IsADirectoryError",
                "NotADirectoryError",
                "OSError",
                "CalamineError",
            },
            _rule_io,
            _OS_RE,
        ),
        rule(9, ("TD-IN-004",), {"UnicodeDecodeError", "ComputeError"}, _rule_9),
        rule(10, ("TD-IN-005",), {"NoDataError"}, _rule_10, re.compile(r"empty CSV")),
        rule(
            11,
            ("TD-IN-007",),
            {"ComputeError"},
            _rule_11,
            re.compile(r"found more fields than defined in 'Schema'"),
        ),
        rule(
            12,
            ("TD-IN-006",),
            {"CalamineError", "FastExcelError"},
            _rule_12,
            re.compile(r"Zip error|invalid Zip archive|calamine error", re.DOTALL),
        ),
        rule(
            13,
            ("TD-TYP-001", "TD-TYP-005"),
            {"InvalidOperationError", "ComputeError"},
            _rule_13,
            re.compile(r"conversion from `", re.DOTALL),
        ),
        rule(
            14,
            ("TD-TYP-001",),
            {"ComputeError"},
            _rule_14,
            re.compile(r"strict integer parsing failed", re.DOTALL),
        ),
        rule(
            15,
            ("TD-TYP-001",),
            {"ConversionException", "InvalidInputException"},
            _rule_15,
        ),
        rule(
            17,
            ("TD-TYP-002",),
            {"SchemaError"},
            _rule_17,
            re.compile(r"datatypes of join keys don't match", re.DOTALL),
        ),
        rule(
            18,
            ("TD-SCH-004",),
            {"InvalidOperationError", "SchemaError"},
            _rule_18,
            re.compile(r"should all have the same schema", re.DOTALL),
        ),
        rule(19, ("TD-SCH-002",), {"DuplicateError"}, _rule_19),
        rule(
            20,
            ("TD-SCH-001",),
            {
                "ColumnNotFoundError",
                "StructFieldNotFoundError",
                "SchemaFieldNotFoundError",
            },
            _rule_20,
        ),
        rule(
            21,
            ("TD-SCH-001",),
            {"BinderException"},
            _rule_21,
            re.compile(
                r"not found in FROM clause|does not have a column named", re.DOTALL
            ),
        ),
        rule(
            22,
            ("TD-TYP-003",),
            {"InvalidOperationError", "BinderException"},
            _rule_22,
            re.compile(
                r"operation not supported for dtype|No function matches", re.DOTALL
            ),
        ),
        rule(
            23,
            ("TD-TYP-004",),
            {"ComputeError", "BinderException"},
            _rule_23,
            re.compile(
                r"cannot compare string with numeric type|Cannot compare values of type",
                re.DOTALL,
            ),
        ),
        rule(
            24,
            ("TD-TYP-007",),
            {"InvalidOperationError"},
            _rule_24,
            re.compile(r"filter predicate must be of type", re.DOTALL),
        ),
        rule(
            25,
            ("TD-TYP-006",),
            {"InvalidOperationError"},
            _rule_25,
            re.compile(r"invalid dtype: expected", re.DOTALL),
        ),
        rule(26, ("TD-SCH-005",), {"ShapeError"}, _rule_26),
        rule(
            27,
            ("TD-EXP-001",),
            {"ParserException", "SQLSyntaxError", "SQLInterfaceError"},
            _rule_27,
        ),
        rule(
            28,
            ("TD-EXP-002",),
            {"CatalogException"},
            _rule_28,
            re.compile(r"Function with name .* does not exist", re.DOTALL),
        ),
        rule(
            29,
            ("TD-EXP-004",),
            {"ComputeError"},
            _rule_29,
            re.compile(r"regex error|regex parse error", re.DOTALL),
        ),
        rule(30, ("TD-EXP-003",), {"BinderException", "CatalogException"}, _rule_30),
        rule(
            31,
            ("TD-EXP-005",),
            {"InvalidInputException", "ConversionException"},
            _rule_31,
        ),
        rule(
            32,
            ("TD-EXP-001",),
            None,
            _rule_sqlglot_syntax,
            re.compile(r"Required keyword: 'expression' missing for"),
        ),
        rule(
            33,
            ("TD-RUN-006",),
            {"NameError", "UnboundLocalError"},
            _rule_33,
            re.compile(r"name '[^']+' is not defined"),
        ),
        rule(
            34,
            ("TD-SYS-100", "TD-SYS-001"),
            {
                "InvalidOperationError",
                "ComputeError",
                "OutOfBoundsError",
                "PolarsError",
                "ValueError",
                "TypeError",
            },
            _rule_34,
        ),
        rule(35, ("TD-SYS-100",), None, _rule_35),
        rule(36, ("TD-SYS-999",), None, _rule_36),
    )


RULES: tuple[Rule, ...] = _build_rules()


def _owner_for_path(path: str | None, ctx: ErrorContext) -> int | None:
    if not path:
        return None
    normalized = normalise_path(path)
    if normalized in ctx.input_paths:
        return ctx.input_paths[normalized]
    if normalized in ctx.output_paths:
        return ctx.output_paths[normalized]
    basename = os.path.basename(normalized)
    for mapping in (ctx.input_paths, ctx.output_paths):
        for candidate, node_id in mapping.items():
            if os.path.basename(candidate) == basename:
                return node_id
    return None


def _passthrough(exc, ctx: ErrorContext) -> NodeError | None:
    candidates = []
    current = exc
    for _ in range(5):
        if current is None or isinstance(current, str):
            break
        candidates.append(current)
        nxt = getattr(current, "original_exception", None)
        if nxt is None or nxt is current:
            break
        current = nxt
    code = None
    source = exc
    text = _safe_str(exc)
    for candidate in candidates:
        value = getattr(candidate, "code", None)
        if isinstance(value, str) and value.startswith("TD-"):
            code, source, text = value, candidate, _safe_str(candidate)
            break
    if code is None:
        match = _CODE_RE.search(text)
        if match:
            code = match.group("code")
    if not code:
        return None

    message = text
    message = re.sub(r"^\s*\[TD-[A-Z]+-\d{3}\]\s*", "", message)
    message = re.sub(r"^\s*TD-[A-Z]+-\d{3}:\s*", "", message)
    entry = CATALOGUE.get(code)
    if entry is None:
        return NodeError(
            code=code,
            title=shorten(message or "Unknown error", 90),
            technical=text[:100_000],
            exc_type=type(source).__name__ if not isinstance(source, str) else "",
            node_id=ctx.node_id,
            node_title=ctx.node_title,
            op=ctx.op,
            phase=ctx.phase,
            node_label=ctx.node_label,
        )
    path = getattr(source, "path", None)
    owner = _owner_for_path(path, ctx)
    columns = tuple(getattr(source, "columns", ()) or ())
    single_column = getattr(source, "column", None)
    if single_column and not columns:
        columns = (str(single_column),)
    if entry.get("passthrough"):
        hint = entry.get("hint", "")
        return NodeError(
            code=code,
            title=shorten(message or entry.get("title", ""), 90),
            hint=hint,
            technical=text[:100_000],
            exc_type=type(source).__name__ if not isinstance(source, str) else "",
            exc_module=type(source).__module__ if not isinstance(source, str) else "",
            severity=entry.get("severity", "error"),
            node_id=ctx.node_id,
            node_title=ctx.node_title,
            op=ctx.op,
            node_label=ctx.node_label,
            phase=ctx.phase,
            columns=columns,
            path=str(path) if path else None,
            suggested_fixes=(SuggestedFix(text=hint),) if hint else (),
            culprit_node_id=owner,
            culprit_node_title=ctx.node_labels.get(owner) if owner else None,
        )
    params = dict(getattr(source, "params", {}) or {})
    path = getattr(source, "path", None) or params.get("path")
    if path:
        params.setdefault("path", path)
        params.setdefault("path_name", os.path.basename(str(path)))
    for key in ("sheet", "column", "kind"):
        value = getattr(source, key, None)
        if value:
            params.setdefault(key, value)
    if message:
        params.setdefault("message", message)
        params.setdefault("reason", _reason(message))
    params.setdefault("node_label", ctx.node_label)
    title, detail, fixes = render_entry(code, params, located=False)
    return NodeError(
        code=code,
        title=title,
        detail=detail,
        hint=fixes[0] if fixes else entry.get("hint", ""),
        technical=text[:100_000],
        exc_type=type(source).__name__ if not isinstance(source, str) else "",
        severity=entry.get("severity", "error"),
        node_id=ctx.node_id,
        node_title=ctx.node_title,
        op=ctx.op,
        path=str(path) if path else None,
        phase=ctx.phase,
        node_label=ctx.node_label,
        columns=columns,
        suggested_fixes=tuple(SuggestedFix(text=item) for item in fixes),
        culprit_node_id=owner,
        culprit_node_title=ctx.node_labels.get(owner) if owner else None,
        params={key: str(value) for key, value in params.items()},
    )


def _finish(
    code: str,
    params: dict,
    facts: Facts,
    ctx: ErrorContext,
    redact: bool,
    traceback_text: str,
) -> NodeError:
    row = params.pop("__row", None)
    samples = tuple(params.pop("__samples", ()) or ())
    failing = params.pop("__failing_count", None)
    suggestions = tuple(params.pop("__suggestions", ()) or ())
    columns = tuple(params.get("columns") or ())
    if isinstance(columns, str):
        columns = (columns,)
    if "column" in params and params["column"] and not columns:
        columns = (str(params["column"]),)
    params.setdefault("node_label", ctx.node_label)
    target = str(params.get("target", ""))
    if target:
        one, human, sql = _target_pair(target)
        params.setdefault("target_one", one)
        params.setdefault("target_human", human)
        params.setdefault("target_sql", sql)
    path = params.get("path")
    if path and "path_name" not in params:
        params["path_name"] = os.path.basename(str(path))
    if row is not None:
        params["row"] = int(row)
        params["row_hint"] = f" (row {int(row):,})"
    if samples:
        params.setdefault("value", samples[0])
        params["values"] = ", ".join(samples)
        if len(samples) > 1:
            rest = ", ".join(samples[1:])
            params["others_sentence"] = (
                f"{len(samples) - 1} more value(s) are also invalid, "
                f"for example {rest}."
            )
    suggestion = str(params.get("suggestion", ""))
    if suggestion:
        params["suggestion_sentence"] = f" Did you mean '{suggestion}'?"
    located = row is not None
    title, detail, fixes = render_entry(code, params, located=located)
    entry = CATALOGUE.get(code) or {}
    severity = entry.get("severity", "error")
    suggested: list[SuggestedFix] = []
    for index, text in enumerate(fixes):
        if index == 0 and suggestion and code in {"TD-SCH-001", "TD-IN-003"}:
            suggested.append(
                SuggestedFix(
                    text=text,
                    kind="rename_column",
                    params={
                        "from": str(params.get("column", params.get("sheet", ""))),
                        "to": suggestion,
                    },
                )
            )
        else:
            suggested.append(SuggestedFix(text=text))
    technical = facts.text[:100_000]
    exc = facts.exc
    exc_type = "" if isinstance(exc, str) or exc is None else type(exc).__name__
    exc_module = "" if isinstance(exc, str) or exc is None else type(exc).__module__
    error = NodeError(
        code=code,
        title=title,
        detail=detail,
        hint=fixes[0] if fixes else entry.get("hint", ""),
        technical=technical,
        exc_type=exc_type,
        exc_module=exc_module,
        severity=severity,
        node_id=ctx.node_id,
        node_title=ctx.node_title,
        op=ctx.op,
        columns=columns,
        path=str(path) if path else None,
        phase=ctx.phase,
        node_label=ctx.node_label,
        traceback=traceback_text[:100_000],
        suggested_fixes=tuple(suggested),
        row_index=int(row) if row is not None else None,
        sample_values=samples,
        failing_count=failing,
        did_you_mean=suggestions or ((suggestion,) if suggestion else ()),
        culprit_node_id=params.get("culprit_node_id"),
        culprit_node_title=params.get("culprit_label"),
        locate_status="found" if row is not None else "",
        params={
            key: str(value)
            for key, value in params.items()
            if key
            not in {
                "columns",
                "culprit_node_id",
                "culprit_label",
                "suggestion_sentence",
                "row_hint",
            }
        },
    )
    return redact_error(error) if redact else error


def translate_exception(
    exc: BaseException | str | None,
    *,
    node: object | None = None,
    phase: str = "run",
    ctx: ErrorContext | None = None,
    redact: bool = False,
    traceback_text: str = "",
) -> NodeError:
    """Translate any exception (or text) into a NodeError; never raises."""
    try:
        context = ctx or ErrorContext.from_node(node, phase)
        passthrough = _passthrough(exc, context)
        if passthrough is not None:
            return redact_error(passthrough) if redact else passthrough
        source = _unwrap(exc)
        facts = _facts(source)
        for rule in RULES:
            if rule.names is not None and not (set(facts.names) & rule.names):
                continue
            match = rule.pattern.search(facts.text) if rule.pattern else None
            if rule.pattern is not None and match is None:
                continue
            hit = rule.build(facts, context, match)
            if hit:
                code, params = hit
                return _finish(code, params, facts, context, redact, traceback_text)
        return _finish(
            "TD-SYS-999",
            {"reason": shorten(facts.text, 160)},
            facts,
            context,
            redact,
            traceback_text,
        )
    except Exception as boom:  # noqa: BLE001 - translator is total
        text = _safe_str(exc)
        return NodeError(
            code="TD-SYS-999",
            title="Something unexpected went wrong.",
            detail=f"The error message could not be translated: {shorten(str(boom), 120)}",
            technical=text[:100_000],
            exc_type=type(exc).__name__ if not isinstance(exc, str) else "",
            params={"reason": shorten(text, 160)},
        )


def translate_sql_diagnostic(
    exc: BaseException,
    formula_text: str,
    ctx: ErrorContext | None = None,
) -> dict:
    del formula_text
    error = translate_exception(exc, ctx=ctx, phase="live")
    name = type(exc).__name__
    if name in {"ParserException", "SQLSyntaxError", "SQLInterfaceError"}:
        return {
            "message": _safe_str(exc),
            "category": "syntax",
            "code": "TD-EXP-001",
            "hint": error.hint,
        }
    message = shorten(error.title + (f" {error.hint}" if error.hint else ""), 160)
    return {
        "message": message,
        "category": "execution",
        "code": error.code,
        "hint": error.hint,
    }
