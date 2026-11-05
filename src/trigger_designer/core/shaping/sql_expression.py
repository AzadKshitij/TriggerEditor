"""Pure SQL-expression helpers for Filter and Formula (Qt-free)."""

from __future__ import annotations

import re

#: Matches '...' and "..." literals, SQL-style ''/"" escapes included.
STRING_LITERAL_RE = re.compile(r"'([^']|'')*'|\"([^\"]|\"\")*\"")
STRING_OR_BRACKET_RE = re.compile(r"'([^']|'')*'|\"([^\"]|\"\")*\"|\[[^\]]*\]")


def apply_outside_string_literals(
    formula: str, transform, *, skip_brackets: bool = False
) -> str:
    """Apply ``transform`` to the code segments, never inside literals."""
    pattern = STRING_OR_BRACKET_RE if skip_brackets else STRING_LITERAL_RE
    parts: list[str] = []
    current_pos = 0
    for match in pattern.finditer(formula):
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


def resolve_column_references(formula: str, available_columns: list[str]) -> str:
    """Rewrite ``[column]`` references to quoted identifiers, case-insensitively."""
    if not available_columns:
        return formula
    names = sorted(available_columns, key=len, reverse=True)
    pattern = re.compile(
        r"\[\s*(" + "|".join(re.escape(name) for name in names) + r")\s*\]",
        re.IGNORECASE,
    )

    def resolve(match: re.Match[str]) -> str:
        inner = match.group(1)
        if inner in available_columns:
            return quote_identifier(inner)
        for column in available_columns:
            if column.lower() == inner.lower():
                return quote_identifier(column)
        return match.group()

    return apply_outside_string_literals(
        formula, lambda segment: pattern.sub(resolve, segment)
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


def prepare_expression_sql(
    expression_text: str, available_columns: list[str], *, in_between: bool = True
) -> str:
    """Turn a filter/formula expression into a DuckDB SQL expression.

    Formulas pass ``in_between=False``: ``in_between(a, b)`` is a Filter alias.
    """
    sql_expression = normalize_string_literals(expression_text)
    if in_between:
        sql_expression = apply_outside_string_literals(
            sql_expression, translate_in_between
        )
    sql_expression = apply_outside_string_literals(
        sql_expression, translate_function_aliases, skip_brackets=True
    )
    return resolve_column_references(sql_expression, available_columns)


def shorten_error(message: str) -> str:
    """The engine error's key line, without DuckDB's category prefix."""
    text = (message or "").strip().replace("\r\n", "\n")
    match = re.search(r'Referenced column "[^"]+" not found', text)
    if match:
        return match.group()
    first_line = text.split("\n", 1)[0].strip()
    for prefix in (
        "Binder Error:",
        "Catalog Error:",
        "Conversion Error:",
        "Parser Error:",
    ):
        if first_line.startswith(prefix):
            first_line = first_line[len(prefix) :].strip()
    return first_line[:160]
