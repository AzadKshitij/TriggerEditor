"""Shaping DuckDB connections keep the Arrow exchange on the caller thread."""

from trigger_designer.core.shaping.common import DUCKDB_THREADS, connect_duckdb


def test_shaping_connection_uses_one_thread() -> None:
    assert DUCKDB_THREADS == 1
    with connect_duckdb() as connection:
        assert (
            connection.execute("SELECT current_setting('threads')").fetchone()[0] == 1
        )
