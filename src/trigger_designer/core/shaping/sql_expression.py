"""Pure SQL-expression helpers for Filter and Formula (Qt-free)."""

from __future__ import annotations

import re

#: Matches '...' and "..." literals, SQL-style ''/"" escapes included.
STRING_LITERAL_RE = re.compile(r"'([^']|'')*'|\"([^\"]|\"\")*\"")


def apply_outside_string_literals(formula: str, transform) -> str:
    """Apply ``transform`` to the code segments, never inside literals."""
    parts: list[str] = []
    current_pos = 0
    for match in STRING_LITERAL_RE.finditer(formula):
        parts.append(transform(formula[current_pos : match.start()]))
        parts.append(match.group())
        current_pos = match.end()
    parts.append(transform(formula[current_pos:]))
    return "".join(parts)


def normalize_string_literals(formula: str) -> str:
    """Rewrite "..." as '...' (only [...] are column references)."""
    token_pattern = re.compile(r"'([^']|'')*'|\"([^\"]|\"\")*\"|\[[^\]]*\]")
    parts: list[str] = []
    current_pos = 0
    for match in token_pattern.finditer(formula):
        parts.append(formula[current_pos : match.start()])
        token = match.group()
        if token.startswith('"'):
            inner = token[1:-1].replace('""', '"').replace("'", "''")
            token = f"'{inner}'"
        parts.append(token)
        current_pos = match.end()
    parts.append(formula[current_pos:])
    return "".join(parts)


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def replace_column_names(formula: str, column_name: str) -> str:
    """Rewrite ``[column]`` references to quoted identifiers, case-insensitively."""
    pattern = rf"\[\s*{re.escape(column_name)}\s*\]"
    replacement = quote_identifier(column_name)
    return apply_outside_string_literals(
        formula,
        lambda segment: re.sub(pattern, replacement, segment, flags=re.IGNORECASE),
    )


def translate_in_between(segment: str) -> str:
    """Alias ``in_between (a, b)`` to SQL ``BETWEEN a AND b``."""
    return re.sub(
        r"(?i)\bin_between\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)",
        r"BETWEEN \1 AND \2",
        segment,
    )


def translate_function_aliases(segment: str) -> str:
    """Rewrite convenience function spellings to DuckDB names."""
    return re.sub(r"(?i)\bstrip\s*\(", "trim(", segment)


def prepare_expression_sql(expression_text: str, available_columns: list[str]) -> str:
    """Turn a filter/formula expression into a DuckDB SQL expression."""
    sql_expression = normalize_string_literals(expression_text)
    sql_expression = apply_outside_string_literals(sql_expression, translate_in_between)
    sql_expression = apply_outside_string_literals(
        sql_expression, translate_function_aliases
    )
    for column_name in available_columns:
        sql_expression = replace_column_names(sql_expression, column_name)
    return sql_expression


def shorten_error(message: str) -> str:
    """First line of an engine error, without DuckDB's category prefix."""
    text = (message or "").strip().replace("\r\n", "\n")
    first_line = text.split("\n", 1)[0].strip()
    for prefix in ("Binder Error:", "Catalog Error:", "Parser Error:"):
        if first_line.startswith(prefix):
            first_line = first_line[len(prefix) :].strip()
    return first_line[:160]
