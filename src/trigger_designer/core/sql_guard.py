"""Read-only DuckDB sandbox shared by every node that runs user SQL (Qt-free).

Why two defences (BUG-029, BUG-030): statement type alone is not a guard
(``PRAGMA``, ``DESCRIBE``, ``FROM 'x'`` and ``read_*()`` are typed ``SELECT``,
and in-memory DDL still runs after ``lock_configuration``). So the text is
checked first (masked-text rules plus DuckDB's own parser) and the query then
runs on a *fresh* in-memory connection with external access switched off and
the configuration locked. Either layer alone would be bypassable; together a
workflow's SQL can neither read a file, write a file, load an extension nor
change the engine's settings.

Public API (stable; the Formula/Filter nodes and the SQL Query node use it):

* :func:`check_select_only` - raises ``ShapingError`` unless exactly one
  read-only SELECT.
* :func:`make_locked_connection` - fresh locked connection with frames
  registered by name; the caller closes it.
* :func:`run_select` - check, run with a timeout, return a ``pl.DataFrame``.
* :func:`infer_schema` - column names/types of a query from zero-row inputs.
"""

from __future__ import annotations

import re
import threading
import unicodedata

import duckdb
import polars as pl

from trigger_designer.core.shaping.common import (
    DUCKDB_THREADS,
    Frame,
    ShapingError,
    schema_of,
)

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
MAX_SQL_CHARS = 20_000
#: below the executor's 30 s so a runaway query fails cleanly instead of timing out
TIMEOUT_S = 25.0
MEMORY_LIMIT = "2GB"
#: statement must start with one of these words (after comments are removed)
ALLOWED_FIRST_WORDS = frozenset({"select", "with", "from", "values", "table"})
#: function / table-function names rejected anywhere in the statement
_DENIED_CALLS = re.compile(
    r'(?<![A-Za-z0-9_])"?(?:read_[a-z0-9_]+|glob|[a-z0-9_]*_scan|sniff_csv|query|'
    r"query_table|duckdb_[a-z0-9_]+|pragma_[a-z0-9_]+|current_setting|"
    r'which_secret|random|uuid|gen_random_uuid|setseed|getenv)"?\s*\(',
    re.IGNORECASE,
)
#: FROM 'file.csv' / JOIN 'file.csv' (a quoted *string* where a table belongs)
_FROM_STRING = re.compile(r"\b(?:from|join)\s*'", re.IGNORECASE)
#: FROM "dir/file.csv": a quoted identifier that looks like a path or glob
_FROM_PATH = re.compile(r'\b(?:from|join)\s*"[^"]*[./\\*][^"]*"', re.IGNORECASE)
#: dollar quoting ($$ ... $$, $tag$ ... $tag$) and E'..' escape strings change how
#: quotes are read, which would let text hide from the masking below
_DOLLAR_QUOTE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")
_ESCAPE_STRING = re.compile(r"(?<![A-Za-z0-9_])[eE]\s*'")
_LEADING_WORD = re.compile(r"[A-Za-z]+|\(")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def mask(sql: str, *, keep_identifiers: bool = False) -> str:
    """Blank out comments and string contents (keeps quotes and length).

    Double-quoted identifiers are blanked too unless ``keep_identifiers``.
    Block comments do not nest here: DuckDB nests them, so anything this
    rejects is a superset of what the engine would run.
    """
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        two = sql[i : i + 2]
        if two == "--":
            j = sql.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        elif two == "/*":
            j = sql.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(" " * (j - i))
            i = j
        elif ch in ("'", '"'):
            j = i + 1
            while j < n:
                if sql[j] == ch:
                    if sql[j + 1 : j + 2] == ch:  # doubled quote = escaped quote
                        j += 2
                        continue
                    break
                j += 1
            if ch == '"' and keep_identifiers:
                out.append(sql[i : j + 1])
            else:
                out.append(ch + " " * max(j - i - 1, 0) + (ch if j < n else ""))
            i = j + 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _tidy(sql: str) -> str:
    return sql.strip().rstrip(";").strip()


def check_select_only(sql: str) -> None:
    """Raise ``ShapingError`` unless ``sql`` is exactly one read-only SELECT.

    Codes: ``TD-SHAPE-001`` empty, ``-110`` several statements, ``-111`` not a
    SELECT, ``-112`` forbidden function/file, ``-113`` unparsable or unsupported
    syntax, ``-114`` too long.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise ShapingError("TD-SHAPE-001", "SQL is empty")
    if len(sql) > MAX_SQL_CHARS:
        raise ShapingError(
            "TD-SHAPE-114", f"SQL is longer than {MAX_SQL_CHARS:,} characters"
        )
    if _CONTROL.search(sql):
        raise ShapingError("TD-SHAPE-113", "SQL contains control characters")
    # Compatibility forms (fullwidth letters, ligatures) must not dodge the rules.
    normal = unicodedata.normalize("NFKC", sql)
    masked = _tidy(mask(normal))
    if not masked:
        raise ShapingError("TD-SHAPE-001", "SQL is empty")
    if _DOLLAR_QUOTE.search(masked) or _ESCAPE_STRING.search(masked):
        raise ShapingError(
            "TD-SHAPE-113", "Dollar-quoted and escape strings are not supported"
        )
    if ";" in masked:
        raise ShapingError("TD-SHAPE-110", "Only one statement is allowed")
    m = _LEADING_WORD.match(masked)
    if not m or (m.group().lower() not in ALLOWED_FIRST_WORDS and m.group() != "("):
        raise ShapingError("TD-SHAPE-111", "Only SELECT queries are allowed")
    with_idents = mask(normal, keep_identifiers=True)
    if _DENIED_CALLS.search(with_idents):
        raise ShapingError(
            "TD-SHAPE-112", "This function is not allowed (files, system or random)"
        )
    if _FROM_STRING.search(masked) or _FROM_PATH.search(with_idents):
        raise ShapingError("TD-SHAPE-112", "Reading files is not allowed")
    # the parser has the last word on what kind of statement this is
    probe = duckdb.connect(":memory:")
    try:
        statements = probe.extract_statements(_tidy(sql))
    except duckdb.Error as exc:
        raise ShapingError(
            "TD-SHAPE-113", f"SQL could not be parsed: {str(exc)[:120]}"
        ) from exc
    finally:
        probe.close()
    if len(statements) != 1:
        raise ShapingError("TD-SHAPE-110", "Only one statement is allowed")
    if statements[0].type != duckdb.StatementType.SELECT:
        raise ShapingError("TD-SHAPE-111", "Only SELECT queries are allowed")


def make_locked_connection(
    inputs: dict[str, Frame] | None = None,
    *,
    threads: int = DUCKDB_THREADS,
    memory_limit: str | None = MEMORY_LIMIT,
) -> duckdb.DuckDBPyConnection:
    """Fresh in-memory connection: no file/network access, config locked.

    ``inputs`` maps a table name to a Polars frame; lazy frames are passed to
    DuckDB as they are. ``threads`` defaults to the shaping nodes' single
    worker (a live evaluation crashed when DuckDB workers entered Polars off
    the Qt thread); ``memory_limit=None`` leaves DuckDB's own limit for nodes
    that process whole tables. The caller closes the connection.
    """
    for name in inputs or {}:
        if not _NAME.fullmatch(name):
            raise ShapingError("TD-SHAPE-004", f"Invalid table name {name!r}")
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"SET threads={int(threads)}")
        if memory_limit:
            con.execute(f"SET memory_limit='{memory_limit}'")
        for stmt in (
            "SET autoinstall_known_extensions=false",
            "SET autoload_known_extensions=false",
            "SET allow_community_extensions=false",
            "SET allow_unsigned_extensions=false",
            "SET enable_external_access=false",
            "SET lock_configuration=true",
        ):
            con.execute(stmt)
        for name, frame in (inputs or {}).items():
            con.register(name, frame)
    except BaseException:
        con.close()
        raise
    return con


def run_select(
    sql: str, inputs: dict[str, Frame], timeout_s: float = TIMEOUT_S
) -> pl.DataFrame:
    """Validate then run ``sql``; the result is a Polars DataFrame."""
    check_select_only(sql)
    cleaned = _tidy(sql)
    con = make_locked_connection(inputs)
    timer = threading.Timer(timeout_s, con.interrupt)
    timer.start()
    try:
        return con.sql(cleaned).pl()
    except duckdb.InterruptException as exc:
        raise ShapingError(
            "TD-SHAPE-115", f"Query took longer than {timeout_s:.0f} s"
        ) from exc
    except duckdb.Error as exc:
        raise ShapingError("TD-SHAPE-113", str(exc).splitlines()[0][:200]) from exc
    finally:
        timer.cancel()
        con.close()


def infer_schema(sql: str, schemas: dict[str, dict]) -> dict:
    """Column names/types of ``sql`` over zero-row inputs described by ``schemas``."""
    check_select_only(sql)
    inputs = {name: pl.DataFrame(schema=schema) for name, schema in schemas.items()}
    # The newline before ")" stops a trailing "--" comment swallowing it.
    wrapped = f"SELECT * FROM (\n{_tidy(sql)}\n) AS _q LIMIT 0"
    con = make_locked_connection(inputs)
    try:
        return dict(schema_of(con.sql(wrapped).pl()))
    except duckdb.Error as exc:
        raise ShapingError("TD-SHAPE-113", str(exc).splitlines()[0][:200]) from exc
    finally:
        con.close()
