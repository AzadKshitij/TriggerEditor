"""Preload the first DuckDB/Polars Arrow exchange while the splash is shown.

No Qt objects are touched here. A fresh file load otherwise pays for pandas
and pyarrow's lazy imports synchronously on the GUI thread at its first SQL
Filter/Formula evaluation.
"""

import duckdb
import polars as pl


def warm_duckdb_polars() -> None:
    frame = pl.DataFrame({"value": [1]})
    with duckdb.connect(":memory:") as connection:
        connection.register("warmup_frame", frame)
        result = connection.execute("SELECT value FROM warmup_frame").pl()
        if result["value"].to_list() != [1]:
            raise RuntimeError("DuckDB/Polars warm-up returned unexpected data")
