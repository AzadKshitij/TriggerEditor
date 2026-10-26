"""Read-only SQLite and DuckDB source tests."""

from __future__ import annotations

import hashlib
import shutil

import duckdb
import pytest

from tests.support.input_fixtures import duckdb_db, sqlite_db
from trigger_designer.core.input_source import build_source, list_db_tables
from trigger_designer.core.inputs import InputReadError


def _state(path, kind: str, **extra) -> dict:
    state = {"filePath": str(path), "file_type": kind}
    state.update(extra)
    return state


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_list_tables_sqlite_and_duckdb(tmp_path) -> None:
    sqlite = sqlite_db(tmp_path)
    duck = duckdb_db(tmp_path)
    assert list_db_tables(str(sqlite), "sqlite") == ["big", "sales"]
    assert list_db_tables(str(duck), "duckdb") == ["sales"]


def test_sqlite_table_read_types(tmp_path) -> None:
    sqlite = sqlite_db(tmp_path)
    frame = build_source(
        _state(sqlite, "sqlite", db_mode="table", db_table="sales")
    ).frame.collect()
    assert frame.schema["id"].is_integer()
    assert frame.schema["amount"].is_float()
    assert frame.height == 3
    assert frame["region"].to_list() == ["N", "S", "N"]


def test_duckdb_table_read_types(tmp_path) -> None:
    duck = duckdb_db(tmp_path)
    frame = build_source(
        _state(duck, "duckdb", db_mode="table", db_table="sales")
    ).frame.collect()
    assert frame.schema["id"].is_integer()
    assert frame.schema["amount"].is_float()
    assert frame.height == 3


@pytest.mark.parametrize("kind", ["sqlite", "duckdb"])
def test_sql_query_mode_both_engines(tmp_path, kind) -> None:
    path = sqlite_db(tmp_path) if kind == "sqlite" else duckdb_db(tmp_path)
    query = (
        "SELECT region, SUM(amount) AS total FROM sales "
        "GROUP BY region ORDER BY region;"
    )
    frame = build_source(
        _state(path, kind, db_mode="query", db_query=query)
    ).frame.collect()
    assert frame.rows() == [("N", 40.75), ("S", 20.0)]

    limited = build_source(
        _state(path, kind, db_mode="query", db_query=query, record_limit=1)
    ).frame.collect()
    assert limited.height == 1


@pytest.mark.parametrize(
    "query",
    [
        "DROP TABLE sales",
        "DELETE FROM sales",
        "INSERT INTO sales VALUES (9,'x',1)",
        "ATTACH 'other.db' AS o",
        "PRAGMA writable_schema=1",
        "SELECT 1; DROP TABLE sales",
    ],
)
def test_sqlite_rejects_writes(tmp_path, query: str) -> None:
    path = sqlite_db(tmp_path)
    before = _sha(path)
    with pytest.raises(InputReadError) as error:
        build_source(
            _state(path, "sqlite", db_mode="query", db_query=query)
        ).frame.collect()
    assert error.value.kind in {"db_forbidden", "db_error"}
    assert _sha(path) == before


@pytest.mark.parametrize(
    "query",
    [
        "DROP TABLE sales",
        "DELETE FROM sales",
        "INSERT INTO sales VALUES (9,'x',1)",
        "ATTACH 'other.db' AS o",
        "COPY sales TO 'x.csv'",
        "SELECT * FROM read_csv('a.csv')",
        "INSTALL httpfs",
        "SELECT 1; DROP TABLE sales",
    ],
)
def test_duckdb_rejects_writes(tmp_path, query: str) -> None:
    path = duckdb_db(tmp_path)
    before = _sha(path)
    with pytest.raises(InputReadError) as error:
        build_source(
            _state(path, "duckdb", db_mode="query", db_query=query)
        ).frame.collect()
    assert error.value.kind in {"db_forbidden", "db_error"}
    assert _sha(path) == before


def test_multiple_statements_rejected(tmp_path) -> None:
    path = sqlite_db(tmp_path)
    with pytest.raises(InputReadError) as error:
        build_source(
            _state(
                path,
                "sqlite",
                db_mode="query",
                db_query="SELECT 1; DROP TABLE sales",
            )
        )
    assert error.value.kind == "db_forbidden"


def test_sqlite_missing_table(tmp_path) -> None:
    path = sqlite_db(tmp_path)
    with pytest.raises(InputReadError) as error:
        build_source(_state(path, "sqlite", db_mode="table", db_table="does_not_exist"))
    assert error.value.kind == "db_error"
    assert "does_not_exist" in str(error.value)


def test_empty_table_name_config_error(tmp_path) -> None:
    path = sqlite_db(tmp_path)
    with pytest.raises(InputReadError) as error:
        build_source(_state(path, "sqlite", db_mode="table", db_table=""))
    assert error.value.kind == "config"


def test_empty_query_config_error(tmp_path) -> None:
    path = sqlite_db(tmp_path)
    with pytest.raises(InputReadError) as error:
        build_source(_state(path, "sqlite", db_mode="query", db_query="   "))
    assert error.value.kind == "config"


def test_db_folder_mode_unsupported(tmp_path) -> None:
    path = sqlite_db(tmp_path)
    with pytest.raises(InputReadError) as error:
        build_source(
            _state(
                path.parent,
                "sqlite",
                db_mode="table",
                db_table="sales",
            )
        )
    assert error.value.kind == "unsupported_source"


def test_sqlite_path_with_special_chars(tmp_path) -> None:
    source = sqlite_db(tmp_path)
    target = tmp_path / "weird # unicode données.sqlite"
    shutil.copy(source, target)
    frame = build_source(
        _state(target, "sqlite", db_mode="table", db_table="sales")
    ).frame.collect()
    assert frame.height == 3


def test_duckdb_locked_by_writer(tmp_path) -> None:
    path = duckdb_db(tmp_path)
    writer = duckdb.connect(str(path))
    writer.execute("select 1").fetchall()
    try:
        try:
            frame = build_source(
                _state(path, "duckdb", db_mode="table", db_table="sales")
            ).frame.collect()
        except InputReadError as error:
            assert error.kind == "locked"
        else:
            assert frame.height == 3
    finally:
        writer.close()
