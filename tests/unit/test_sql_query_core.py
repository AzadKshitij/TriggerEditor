"""SQL Query core: hand-computed results, error codes and read-only attacks.

The attack tests go through ``sql_query.run_node`` (the function live
evaluation, Run and the generated code all call). Each one plants a real file,
and the assertions are on the file system as much as on the exception: nothing
may be read into a result and nothing may be created.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date

import polars as pl
import pytest

from trigger_designer.core import sql_guard
from trigger_designer.core.shaping import sql_query
from trigger_designer.core.shaping.common import ShapingError

T1 = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
T2 = pl.DataFrame({"a": [2, 3, 4], "c": [20.0, 30.0, 40.0]})
T3 = pl.DataFrame({"a": [3, 4, 5], "d": ["p", "q", "r"]})

JOIN = "SELECT t1.a, t1.b, t2.c FROM t1 JOIN t2 USING (a) ORDER BY t1.a"


def run(sql: str, frames=None) -> pl.DataFrame:
    frames = [T1.lazy(), None, None] if frames is None else frames
    (out,) = sql_query.run_node(frames, {"sql": sql})
    assert isinstance(out, pl.LazyFrame)
    return out.collect()


def code_of(sql: str, frames=None) -> str:
    with pytest.raises(ShapingError) as info:
        run(sql, frames)
    return info.value.code


# ---- results ---------------------------------------------------------------


def test_default_query_returns_the_input_unchanged() -> None:
    (out,) = sql_query.run_node([T1.lazy(), None, None], dict(sql_query.DEFAULTS))
    assert out.collect().equals(T1)


def test_missing_sql_key_uses_the_default() -> None:
    (out,) = sql_query.run_node([T1.lazy(), None, None], {})
    assert out.collect().equals(T1)


def test_join_two_inputs_third_unconnected() -> None:
    out = run(JOIN, [T1.lazy(), T2.lazy(), None])
    assert out.columns == ["a", "b", "c"]
    assert out.rows() == [(2, "y", 20.0), (3, "z", 30.0)]


def test_three_inputs_chain() -> None:
    sql = "SELECT t1.a, c, d FROM t1 JOIN t2 USING (a) JOIN t3 USING (a) ORDER BY t1.a"
    out = run(sql, [T1.lazy(), T2.lazy(), T3.lazy()])
    assert out.rows() == [(3, 30.0, "p")]


def test_dataframe_and_lazyframe_inputs_agree() -> None:
    lazy = run(JOIN, [T1.lazy(), T2.lazy(), None])
    eager = run(JOIN, [T1, T2, None])
    assert lazy.equals(eager)


def test_t3_wired_without_t2_is_still_t3() -> None:
    out = run("SELECT d FROM t3 ORDER BY d", [T1.lazy(), None, T3.lazy()])
    assert out["d"].to_list() == ["p", "q", "r"]


def test_aggregate_and_row_order_follow_the_query() -> None:
    out = run("SELECT b, a * 10 AS tens FROM t1 ORDER BY a DESC")
    assert out.rows() == [("z", 30), ("y", 20), ("x", 10)]


def test_without_order_by_a_simple_select_keeps_input_order() -> None:
    frame = pl.DataFrame({"v": list(range(1000, 0, -1))})
    out = run("SELECT v FROM t1 WHERE v % 2 = 0", [frame.lazy(), None, None])
    assert out["v"].to_list() == list(range(1000, 0, -2))


def test_with_clause_and_window_function() -> None:
    sql = (
        "WITH s AS (SELECT a, b FROM t1 WHERE a >= 2) "
        "SELECT a, row_number() OVER (ORDER BY a) AS n FROM s ORDER BY a"
    )
    assert run(sql).rows() == [(2, 1), (3, 2)]


def test_text_column_aggregate_over_csv_style_strings() -> None:
    frame = pl.DataFrame({"acct": ["A", "A", "B"], "amt": ["1.5", "2.5", "x"]})
    out = run(
        "SELECT acct, sum(try_cast(amt AS DOUBLE)) AS total FROM t1 "
        "GROUP BY acct ORDER BY acct",
        [frame.lazy(), None, None],
    )
    assert out.rows() == [("A", 4.0), ("B", None)]


def test_trailing_semicolon_and_comments_are_fine() -> None:
    out = run("-- header\nSELECT a FROM t1 -- tail\n;")
    assert out["a"].to_list() == [1, 2, 3]


def test_duplicate_output_names_are_renamed_by_duckdb() -> None:
    out = run("SELECT a, a FROM t1")
    assert out.columns == ["a", "a_1"]


def test_empty_result_keeps_column_types() -> None:
    out = run("SELECT a, b FROM t1 WHERE a > 99")
    assert out.height == 0
    assert dict(out.schema) == {"a": pl.Int64, "b": pl.String}


def test_zero_row_input_gives_typed_empty_output() -> None:
    empty = pl.DataFrame(schema={"a": pl.Int64, "b": pl.String})
    out = run("SELECT * FROM t1", [empty.lazy(), None, None])
    assert out.height == 0
    assert dict(out.schema) == {"a": pl.Int64, "b": pl.String}


def test_result_dtypes_are_normalised() -> None:
    out = run("SELECT 1::UTINYINT AS u, DATE '2020-01-02' AS d FROM t1 LIMIT 1")
    assert out.schema["u"] == pl.Int64
    assert out["d"].to_list() == [date(2020, 1, 2)]


def test_null_cells_never_raise() -> None:
    frame = pl.DataFrame({"a": [None, 1], "b": [None, "x"]})
    out = run("SELECT a, upper(b) AS ub FROM t1", [frame.lazy(), None, None])
    assert out.rows() == [(None, None), (1, "X")]


def test_quoted_column_with_space_and_unicode() -> None:
    frame = pl.DataFrame({"my col": [1], "café": ["x"]})
    out = run('SELECT "my col", "café" FROM t1', [frame.lazy(), None, None])
    assert out.columns == ["my col", "café"]


# ---- errors ----------------------------------------------------------------


def test_unconnected_t2_is_a_catalog_error() -> None:
    with pytest.raises(ShapingError) as info:
        run("SELECT * FROM t2")
    assert info.value.code == "TD-SHAPE-113"
    assert "t2" in str(info.value)


def test_missing_first_input_is_005() -> None:
    assert code_of("SELECT 1", [None, T2.lazy(), None]) == "TD-SHAPE-005"
    assert code_of("SELECT 1", []) == "TD-SHAPE-005"


@pytest.mark.parametrize("sql", ["", "   \n ", "-- only a comment", None])
def test_empty_sql_is_001(sql) -> None:
    assert code_of(sql) == "TD-SHAPE-001"


def test_unknown_column_is_113_with_the_engine_message() -> None:
    with pytest.raises(ShapingError) as info:
        run("SELECT zzz FROM t1")
    assert info.value.code == "TD-SHAPE-113"
    assert "zzz" in info.value.detail


def test_unparsable_sql_is_113() -> None:
    assert code_of("SELECT FROM WHERE") == "TD-SHAPE-113"


def test_20001_character_query_is_114() -> None:
    assert code_of("SELECT 1 " + "x" * 20_000) == "TD-SHAPE-114"
    assert sql_guard.MAX_SQL_CHARS == 20_000


def test_long_running_query_is_115(monkeypatch) -> None:
    real = sql_guard.run_select
    monkeypatch.setattr(
        sql_query, "run_select", lambda sql, inputs: real(sql, inputs, 1.0)
    )
    assert code_of("SELECT count(*) FROM range(100000000000)") == "TD-SHAPE-115"


def test_every_error_code_this_node_raises_is_in_the_catalogue() -> None:
    from trigger_designer.core.errors.catalogue import CATALOGUE
    from trigger_designer.core.shaping.common import ERROR_CODES

    for code in (
        "TD-SHAPE-001",
        "TD-SHAPE-005",
        "TD-SHAPE-110",
        "TD-SHAPE-111",
        "TD-SHAPE-112",
        "TD-SHAPE-113",
        "TD-SHAPE-114",
        "TD-SHAPE-115",
    ):
        assert code in ERROR_CODES
        assert code in CATALOGUE


# ---- diagnostics (editor error line) ----------------------------------------


def test_diagnostics_valid_query_has_no_errors() -> None:
    schemas = {"t1": dict(T1.schema)}
    assert sql_query.diagnostics("SELECT a, b FROM t1", schemas) == []


def test_diagnostics_report_the_engine_message_as_execution() -> None:
    schemas = {"t1": dict(T1.schema)}
    (error,) = sql_query.diagnostics("select zzz from t1", schemas)
    assert error["category"] == "execution"
    assert "zzz" in error["message"]


def test_diagnostics_reject_forbidden_sql_without_touching_a_file(tmp_path) -> None:
    secret = tmp_path / "s.csv"
    secret.write_text("a\n1\n")
    schemas = {"t1": dict(T1.schema)}
    (error,) = sql_query.diagnostics(
        f"SELECT * FROM read_csv('{secret.as_posix()}')", schemas
    )
    assert "not allowed" in error["message"]


def test_diagnostics_use_zero_row_inputs_only() -> None:
    schemas = {"t1": dict(T1.schema)}
    assert sql_guard.infer_schema("SELECT a, b FROM t1", schemas) == {
        "a": pl.Int64,
        "b": pl.String,
    }
    # a trailing line comment must not swallow the closing parenthesis
    assert sql_query.diagnostics("SELECT a FROM t1 -- note", schemas) == []


def test_output_schema_matches_the_real_result() -> None:
    frames = [T1.lazy(), T2.lazy(), None]
    schema = sql_query.output_schema(frames, {"sql": JOIN})
    assert schema == dict(run(JOIN, frames).schema)


# ---- read-only attacks -------------------------------------------------------


@pytest.fixture
def lab(tmp_path, monkeypatch):
    """A working directory holding a secret CSV; attacks must leave it alone."""
    monkeypatch.chdir(tmp_path)
    secret = tmp_path / "secret.csv"
    secret.write_text("password\nhunter2\n")
    before = {p.name for p in tmp_path.iterdir()}
    yield tmp_path, secret, before


def _assert_nothing_written(tmp_path, before) -> None:
    assert {p.name for p in tmp_path.iterdir()} == before


FILE_READS = [
    "SELECT * FROM read_csv('secret.csv')",
    "SELECT * FROM read_csv_auto('{abs}')",
    "SELECT * FROM READ_CSV ('secret.csv')",
    "SELECT * FROM read_text('secret.csv')",
    "SELECT * FROM read_blob('secret.csv')",
    "SELECT * FROM read_json('secret.csv')",
    "SELECT * FROM read_parquet('secret.csv')",
    "SELECT * FROM glob('*')",
    "SELECT * FROM glob('{abs}')",
    "SELECT * FROM sniff_csv('secret.csv')",
    "SELECT * FROM parquet_scan('secret.csv')",
    "SELECT * FROM 'secret.csv'",
    "SELECT * FROM t1 JOIN 'secret.csv' ON true",
    'SELECT * FROM "secret.csv"',
    "SELECT * FROM query('SELECT * FROM read_csv(''secret.csv'')')",
    "SELECT * FROM query_table('secret.csv')",
    "SELECT * FROM read_csv\n\t('secret.csv')",
    "SELECT * FROM read_csv/* c */('secret.csv')",
    "SELECT * FROM read_csv -- c\n('secret.csv')",
    "SELECT * FROM \"read_csv\"('secret.csv')",
    "SELECT * FROM main.read_csv('secret.csv')",
    "SELECT * FROM rEaD_CsV('secret.csv')",
    "SELECT * FROM ｒｅａｄ_csv('secret.csv')",
    "SELECT * FROM t1 WHERE a IN (SELECT 1 FROM read_csv('secret.csv'))",
    "WITH s AS (SELECT * FROM read_csv('secret.csv')) SELECT * FROM s",
    "SELECT (SELECT password FROM read_csv('secret.csv') LIMIT 1) AS p",
]

NOT_SELECTS = [
    "COPY t1 TO 'out.csv'",
    "COPY (SELECT * FROM t1) TO 'out.csv' (FORMAT CSV)",
    "COPY t1 FROM 'secret.csv'",
    "EXPORT DATABASE 'dump'",
    "ATTACH 'new.db'",
    "ATTACH 'new.db' AS other (READ_ONLY)",
    "ATTACH DATABASE ':memory:' AS m",
    "DETACH DATABASE x",
    "INSTALL httpfs",
    "INSTALL 'x.duckdb_extension'",
    "LOAD httpfs",
    "LOAD 'x.duckdb_extension'",
    "FORCE INSTALL httpfs",
    "PRAGMA version",
    "PRAGMA database_list",
    "PRAGMA enable_external_access",
    "CALL pragma_version()",
    "SET enable_external_access = true",
    "SET lock_configuration = false",
    "RESET enable_external_access",
    "SET file_search_path = '.'",
    "DESCRIBE t1",
    "SUMMARIZE t1",
    "SHOW TABLES",
    "EXPLAIN SELECT 1",
    "EXPLAIN ANALYZE SELECT 1",
    "CREATE TABLE x AS SELECT 1",
    "CREATE VIEW v AS SELECT 1",
    "CREATE SECRET s (TYPE S3)",
    "DROP TABLE t1",
    "DELETE FROM t1",
    "INSERT INTO t1 VALUES (9, 'q')",
    "UPDATE t1 SET a = 9",
    "ALTER TABLE t1 ADD COLUMN z INT",
    "VACUUM",
    "CHECKPOINT",
    "WITH d AS (SELECT 1) DELETE FROM t1",
    "WITH d AS (SELECT 1) INSERT INTO t1 SELECT * FROM d",
    "WITH d AS (SELECT 1) UPDATE t1 SET a = 2",
    "WITH d AS (SELECT 1) COPY t1 TO 'out.csv'",
    "BEGIN TRANSACTION",
    "USE memory",
    "IMPORT DATABASE 'dump'",
]

SYSTEM_AND_RANDOM = [
    "SELECT * FROM duckdb_settings()",
    "SELECT * FROM duckdb_tables()",
    "SELECT * FROM duckdb_extensions()",
    "SELECT * FROM duckdb_secrets()",
    "SELECT * FROM pragma_database_list()",
    "SELECT current_setting('threads')",
    "SELECT current_setting('enable_external_access')",
    "SELECT getenv('PATH')",
    "SELECT random()",
    "SELECT uuid()",
    "SELECT gen_random_uuid()",
    "SELECT setseed(0.5)",
    "SELECT a, random() AS r FROM t1",
]

MULTI_STATEMENT = [
    "SELECT 1; SELECT 2",
    "SELECT 1; COPY t1 TO 'out.csv'",
    "SELECT 1;\n-- c\nATTACH 'new.db'",
    "SELECT 1 /* x */ ; /* y */ DROP TABLE t1",
    "SELECT 1 /* /* nested */ ; ATTACH 'new.db' /* */ */",
    "SELECT 1;;COPY t1 TO 'out.csv'",
    "SELECT 1 ;\n\n\nINSERT INTO t1 VALUES (1, 'x')",
]

EVASION = [
    "SELECT $$ ' $$ ; COPY t1 TO 'out.csv' -- '",
    "SELECT $tag$ x $tag$",
    "SELECT E'a\\'b'",
    "SELECT 1\x00; DROP TABLE t1",
    "SELECT 1\x1b; DROP TABLE t1",
    # full-width and compatibility characters must not dodge the rules
    "ＳＥＬＥＣＴ 1; DROP TABLE t1",
    "SELECT * FROM ｒｅａｄ_ｃｓｖ('secret.csv')",
    "ＣＯＰＹ t1 TO 'out.csv'",
]


@pytest.mark.parametrize("sql", FILE_READS)
def test_file_reading_forms_are_refused(sql, lab) -> None:
    tmp_path, secret, before = lab
    sql = sql.replace("{abs}", secret.as_posix())
    with pytest.raises(ShapingError) as info:
        run(sql)
    assert info.value.code in {"TD-SHAPE-112", "TD-SHAPE-113"}, str(info.value)
    assert "hunter2" not in str(info.value)
    _assert_nothing_written(tmp_path, before)
    assert secret.read_text() == "password\nhunter2\n"


@pytest.mark.parametrize("sql", NOT_SELECTS)
def test_statements_other_than_select_are_refused(sql, lab) -> None:
    tmp_path, _secret, before = lab
    with pytest.raises(ShapingError) as info:
        run(sql)
    assert info.value.code in {"TD-SHAPE-111", "TD-SHAPE-113"}, str(info.value)
    _assert_nothing_written(tmp_path, before)


@pytest.mark.parametrize("sql", SYSTEM_AND_RANDOM)
def test_system_and_random_functions_are_refused(sql, lab) -> None:
    assert code_of(sql) == "TD-SHAPE-112"


@pytest.mark.parametrize("sql", MULTI_STATEMENT)
def test_several_statements_are_refused(sql, lab) -> None:
    tmp_path, _secret, before = lab
    assert code_of(sql) == "TD-SHAPE-110"
    _assert_nothing_written(tmp_path, before)


@pytest.mark.parametrize("sql", EVASION)
def test_evasion_attempts_are_refused(sql, lab) -> None:
    tmp_path, _secret, before = lab
    with pytest.raises(ShapingError):
        run(sql)
    _assert_nothing_written(tmp_path, before)


def test_text_that_only_looks_dangerous_is_data(lab) -> None:
    sql = (
        "SELECT 'DROP TABLE t1; COPY t1 TO ''x''' AS s, 'read_csv(''x'')' AS r "
        "FROM t1 -- ; ATTACH 'x'\n"
        "/* PRAGMA version; */"
    )
    out = run(sql)
    assert out.height == 3
    assert out["s"][0] == "DROP TABLE t1; COPY t1 TO 'x'"


def test_query_cannot_change_the_inputs_for_the_next_run() -> None:
    t1 = T1.lazy()
    with pytest.raises(ShapingError):
        run("DELETE FROM t1", [t1, None, None])
    with pytest.raises(ShapingError):
        run("SELECT 1; DROP TABLE t1", [t1, None, None])
    assert run("SELECT count(*) AS n FROM t1", [t1, None, None])["n"][0] == 3


def test_engine_is_locked_even_if_the_checker_were_bypassed(lab, monkeypatch) -> None:
    """Defence in depth: with the text rules off, the engine itself refuses."""
    tmp_path, _secret, before = lab
    monkeypatch.setattr(sql_guard, "check_select_only", lambda *a, **k: None)
    attacks = [
        "SELECT * FROM read_csv('secret.csv')",
        "SELECT * FROM read_text('secret.csv')",
        "SELECT * FROM glob('*')",
        "SELECT * FROM 'secret.csv'",
        "COPY (SELECT 1) TO 'out.csv'",
        "COPY t1 TO 'out.csv'",
        "ATTACH 'new.db'",
        "INSTALL httpfs",
        "LOAD httpfs",
        "SET enable_external_access = true",
        "SET lock_configuration = false",
        "EXPORT DATABASE 'dump'",
    ]
    for sql in attacks:
        with pytest.raises(ShapingError) as info:
            run(sql)
        assert info.value.code == "TD-SHAPE-113", (sql, str(info.value))
        assert "hunter2" not in str(info.value)
    _assert_nothing_written(tmp_path, before)


def test_the_guard_function_is_the_one_node_uses() -> None:
    assert sql_query.run_select is sql_guard.run_select


def test_core_imports_no_qt() -> None:
    code = (
        "import sys\n"
        "import trigger_designer.core.shaping.sql_query\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "{'PyQt5','PyQt6','PySide2','PySide6','qtpy','nodeeditor'}]\n"
        "assert not bad, bad\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
