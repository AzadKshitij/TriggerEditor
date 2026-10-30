"""The shared read-only SQL guard: text rules plus a locked engine."""

from __future__ import annotations

import duckdb
import polars as pl
import pytest

from trigger_designer.core.shaping.common import ShapingError
from trigger_designer.core.sql_guard import (
    MAX_SQL_CHARS,
    check_select_only,
    infer_schema,
    make_locked_connection,
    mask,
    run_select,
)

ALLOWED = [
    "SELECT 1",
    "select * from t1",
    "SELECT a, b FROM t1 WHERE a > 1 AND b IN (1, 2)",
    "SELECT * FROM t1 WHERE NOT (a = 3)",
    "SELECT * FROM t1;",
    "SELECT * FROM t1 ;  ",
    "WITH s AS (SELECT * FROM t1) SELECT * FROM s",
    'WITH df_step_0 AS (SELECT *, a * 2 AS "b" FROM df_for_duck) SELECT * FROM df_step_0',
    "FROM t1 SELECT a",
    "VALUES (1), (2)",
    "TABLE t1",
    "(SELECT 1) UNION ALL (SELECT 2)",
    "SELECT 'DROP TABLE x' AS s",
    "SELECT 'read_csv(''x'')' AS s",
    "SELECT a FROM t1 -- ; COPY t1 TO 'x'",
    "SELECT a /* ATTACH 'x'; */ FROM t1",
    'SELECT "my col" FROM t1',
    'SELECT "a;b" FROM t1',
    "SELECT * FROM t1 WHERE s LIKE '%;%'",
    "SELECT a\nFROM t1\n-- trailing comment",
    "SELECT CAST(a AS BIGINT), strftime(d, '%Y') FROM t1",
    "SELECT * REPLACE (a * 2 AS a) FROM t1",
    # a quoted name that merely contains a denied call is just a column name
    'SELECT "read_x(a)" FROM t1',
    'SELECT "net read_x(1)", "random (x)" FROM t1',
    'SELECT "glob(" AS "query(" FROM t1',
    'SELECT "a ""read_csv(""" FROM t1',
]

REJECTED = [
    # (sql, code)
    ("", "TD-SHAPE-001"),
    ("   \n ", "TD-SHAPE-001"),
    ("-- only a comment", "TD-SHAPE-001"),
    ("ATTACH 'x.db'", "TD-SHAPE-111"),
    ("attach database 'x.db' as x", "TD-SHAPE-111"),
    ("COPY t1 TO 'x.csv'", "TD-SHAPE-111"),
    ("COPY (SELECT 1) TO 'x.csv'", "TD-SHAPE-111"),
    ("INSTALL httpfs", "TD-SHAPE-111"),
    ("LOAD httpfs", "TD-SHAPE-111"),
    ("PRAGMA version", "TD-SHAPE-111"),
    ("PRAGMA database_list", "TD-SHAPE-111"),
    ("DESCRIBE t1", "TD-SHAPE-111"),
    ("SUMMARIZE t1", "TD-SHAPE-111"),
    ("SHOW TABLES", "TD-SHAPE-111"),
    ("EXPLAIN SELECT 1", "TD-SHAPE-111"),
    ("SET enable_external_access = true", "TD-SHAPE-111"),
    ("CALL pragma_version()", "TD-SHAPE-111"),
    ("CREATE TABLE x AS SELECT 1", "TD-SHAPE-111"),
    ("DROP TABLE t1", "TD-SHAPE-111"),
    ("DELETE FROM t1", "TD-SHAPE-111"),
    ("INSERT INTO t1 VALUES (1)", "TD-SHAPE-111"),
    ("UPDATE t1 SET a = 1", "TD-SHAPE-111"),
    ("WITH d AS (SELECT 1) DELETE FROM t1", "TD-SHAPE-111"),
    ("WITH d AS (SELECT 1) INSERT INTO t1 SELECT * FROM d", "TD-SHAPE-111"),
    ("SELECT 1; SELECT 2", "TD-SHAPE-110"),
    ("SELECT 1; COPY t1 TO 'x.csv'", "TD-SHAPE-110"),
    ("SELECT 1;\n-- c\nATTACH 'x'", "TD-SHAPE-110"),
    ("SELECT 1 /* x */ ; /* y */ DROP TABLE t1", "TD-SHAPE-110"),
    ("SELECT 1 /* /* */ ; ATTACH 'x' /* */ */", "TD-SHAPE-110"),
    ("SELECT * FROM read_csv('x.csv')", "TD-SHAPE-112"),
    ("SELECT * FROM READ_CSV ('x.csv')", "TD-SHAPE-112"),
    ("SELECT * FROM read_csv_auto('x.csv')", "TD-SHAPE-112"),
    ("SELECT * FROM read_parquet('x.parquet')", "TD-SHAPE-112"),
    ("SELECT * FROM read_json('x.json')", "TD-SHAPE-112"),
    ("SELECT * FROM read_text('x.txt')", "TD-SHAPE-112"),
    ("SELECT * FROM read_blob('x.bin')", "TD-SHAPE-112"),
    ("SELECT * FROM glob('*')", "TD-SHAPE-112"),
    ("SELECT * FROM parquet_scan('x')", "TD-SHAPE-112"),
    ("SELECT * FROM sqlite_scan('x', 't')", "TD-SHAPE-112"),
    ("SELECT * FROM sniff_csv('x')", "TD-SHAPE-112"),
    ("SELECT * FROM query('select 1')", "TD-SHAPE-112"),
    ("SELECT * FROM query_table('t1')", "TD-SHAPE-112"),
    ("SELECT * FROM duckdb_settings()", "TD-SHAPE-112"),
    ("SELECT * FROM duckdb_tables()", "TD-SHAPE-112"),
    ("SELECT * FROM pragma_database_list()", "TD-SHAPE-112"),
    ("SELECT current_setting('threads')", "TD-SHAPE-112"),
    ("SELECT random()", "TD-SHAPE-112"),
    ("SELECT uuid()", "TD-SHAPE-112"),
    ("SELECT gen_random_uuid()", "TD-SHAPE-112"),
    ("SELECT setseed(0.5)", "TD-SHAPE-112"),
    ("SELECT getenv('PATH')", "TD-SHAPE-112"),
    # evasion: whitespace, comments, quoting, qualification, case, unicode
    ("SELECT * FROM read_csv\n\t ('x.csv')", "TD-SHAPE-112"),
    ("SELECT * FROM read_csv/**/('x.csv')", "TD-SHAPE-112"),
    ("SELECT * FROM read_csv -- c\n('x.csv')", "TD-SHAPE-112"),
    ("SELECT * FROM \"read_csv\"('x.csv')", "TD-SHAPE-112"),
    ("SELECT * FROM main.read_csv('x.csv')", "TD-SHAPE-112"),
    ("SELECT * FROM main.\"read_csv\"('x.csv')", "TD-SHAPE-112"),
    ("SELECT * FROM \"READ_CSV\" ('x.csv')", "TD-SHAPE-112"),
    ('SELECT "x", random() FROM t1', "TD-SHAPE-112"),
    ("SELECT * FROM rEaD_CsV('x.csv')", "TD-SHAPE-112"),
    ("SELECT * FROM ｒｅａｄ_csv('x.csv')", "TD-SHAPE-112"),
    ("SELECT 1 WHERE EXISTS (SELECT * FROM read_csv('x'))", "TD-SHAPE-112"),
    ("SELECT * FROM 'x.csv'", "TD-SHAPE-112"),
    ("SELECT * FROM  'x.csv'", "TD-SHAPE-112"),
    ("SELECT * FROM t1 JOIN 'x.csv' ON true", "TD-SHAPE-112"),
    ('SELECT * FROM "x.csv"', "TD-SHAPE-112"),
    ('SELECT * FROM "dir/x"', "TD-SHAPE-112"),
    ('SELECT * FROM "*.parquet"', "TD-SHAPE-112"),
    # unsupported quoting forms that could hide text from the masker
    ("SELECT $$ ' $$ ; COPY t1 TO 'x' -- '", "TD-SHAPE-112"),
    ("SELECT $tag$ x $tag$", "TD-SHAPE-112"),
    ("SELECT E'a\\'b'", "TD-SHAPE-112"),
    ("SELECT 1\x00; DROP TABLE t1", "TD-SHAPE-112"),
    ("SELEC 1", "TD-SHAPE-111"),
    ("SELECT FROM WHERE", "TD-SHAPE-113"),
    ("SELECT 1 " + "x" * MAX_SQL_CHARS, "TD-SHAPE-114"),
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_allowed_queries_pass(sql: str) -> None:
    assert check_select_only(sql) is None


@pytest.mark.parametrize(("sql", "code"), REJECTED)
def test_rejected_queries(sql: str, code: str) -> None:
    with pytest.raises(ShapingError) as info:
        check_select_only(sql)
    assert info.value.code == code, str(info.value)
    assert isinstance(info.value, ValueError)


def test_allow_unparsable_defers_to_the_engine() -> None:
    assert check_select_only("SELECT FROM WHERE", allow_unparsable=True) is None
    # ...but only for text that does not parse: everything else is still checked
    with pytest.raises(ShapingError):
        check_select_only("SELECT 1; SELECT 2", allow_unparsable=True)
    with pytest.raises(ShapingError):
        check_select_only("SELECT * FROM read_csv('x') WHERE", allow_unparsable=True)


def test_non_string_is_rejected() -> None:
    with pytest.raises(ShapingError):
        check_select_only(None)  # type: ignore[arg-type]


def test_length_limit_boundary() -> None:
    ok = "SELECT '" + "x" * (MAX_SQL_CHARS - 10) + "'"
    assert len(ok) <= MAX_SQL_CHARS
    check_select_only(ok)
    with pytest.raises(ShapingError) as info:
        check_select_only(ok + " " * 20)
    assert info.value.code == "TD-SHAPE-114"


def test_mask_blanks_comments_and_strings_but_keeps_length() -> None:
    sql = "SELECT 'a;b' -- x;\n, /* y; */ \"c;d\" FROM t"
    masked = mask(sql)
    assert len(masked) == len(sql)
    assert ";" not in masked
    assert ";" in mask('SELECT "a;b"', keep_identifiers=True)


# --- the engine lock, tested without the text rules --------------------------


@pytest.fixture
def locked():
    con = make_locked_connection({"t": pl.DataFrame({"a": [1, 2, 3]})})
    yield con
    con.close()


@pytest.mark.parametrize(
    "statement",
    [
        "SET enable_external_access=true",
        "SET lock_configuration=false",
        "SET allow_unsigned_extensions=true",
        "COPY (SELECT 1) TO 'sql_guard_probe.csv'",
        "COPY t TO 'sql_guard_probe.csv'",
        "SELECT * FROM read_csv('sql_guard_probe.csv')",
        "SELECT * FROM 'sql_guard_probe.csv'",
        'SELECT * FROM "sql_guard_probe.csv"',
        "ATTACH 'sql_guard_probe.db'",
        "INSTALL httpfs",
        "LOAD httpfs",
    ],
)
def test_engine_blocks_even_without_text_rules(locked, statement: str) -> None:
    with pytest.raises(duckdb.Error):
        locked.execute(statement)


def test_locked_connection_still_runs_selects_and_register(locked) -> None:
    assert locked.execute("SELECT sum(a) FROM t").fetchall() == [(6,)]
    locked.register("later", pl.LazyFrame({"b": [1]}))
    assert locked.execute("SELECT b FROM later").fetchall() == [(1,)]


def test_locked_connection_accepts_lazy_frames_and_validates_names() -> None:
    con = make_locked_connection({"lz": pl.LazyFrame({"a": [5]})})
    try:
        assert con.execute("SELECT a FROM lz").fetchall() == [(5,)]
    finally:
        con.close()
    with pytest.raises(ShapingError) as info:
        make_locked_connection({"bad name": pl.DataFrame({"a": [1]})})
    assert info.value.code == "TD-SHAPE-004"
    make_locked_connection().close()


def test_in_memory_ddl_does_not_outlive_the_connection() -> None:
    first = make_locked_connection()
    first.execute("CREATE TABLE leak AS SELECT 1 AS a")
    first.close()
    second = make_locked_connection()
    try:
        with pytest.raises(duckdb.Error):
            second.execute("SELECT * FROM leak")
    finally:
        second.close()


# --- run_select / infer_schema -----------------------------------------------


def test_run_select_returns_a_frame() -> None:
    out = run_select(
        "SELECT a * 2 AS b FROM t1 ORDER BY a",
        {"t1": pl.LazyFrame({"a": [2, 1]})},
    )
    assert out.to_dict(as_series=False) == {"b": [2, 4]}


def test_run_select_rejects_before_running(tmp_path) -> None:
    target = tmp_path / "out.csv"
    with pytest.raises(ShapingError):
        run_select(f"COPY (SELECT 1) TO '{target.as_posix()}'", {})
    assert not target.exists()


def test_run_select_maps_engine_errors() -> None:
    with pytest.raises(ShapingError) as info:
        run_select("SELECT nope FROM t1", {"t1": pl.DataFrame({"a": [1]})})
    assert info.value.code == "TD-SHAPE-113"


def test_run_select_times_out() -> None:
    with pytest.raises(ShapingError) as info:
        run_select(
            "SELECT count(*) FROM range(100000000000) a, range(100000000000) b",
            {},
            timeout_s=0.3,
        )
    assert info.value.code == "TD-SHAPE-115"


def test_infer_schema() -> None:
    schema = infer_schema(
        "SELECT a, a * 2.5 AS b FROM t1 -- trailing",
        {"t1": {"a": pl.Int64}},
    )
    assert list(schema) == ["a", "b"]
    assert schema["a"] == pl.Int64
    with pytest.raises(ShapingError) as info:
        infer_schema("SELECT zzz FROM t1", {"t1": {"a": pl.Int64}})
    assert info.value.code == "TD-SHAPE-113"
    with pytest.raises(ShapingError):
        infer_schema("SELECT * FROM read_csv('x')", {})
