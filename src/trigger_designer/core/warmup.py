"""Load the data libraries in the background once the window is on screen.

Polars, DuckDB and Arrow take a second or more to import, and nothing needed
to draw the first window uses them. The editor shows its window first and
calls :func:`start_in_background` right after, so the cost is paid while the
user is already looking at the application. Work that needs the libraries
(evaluating a freshly opened workflow) waits for :func:`is_ready` instead of
blocking the interface on the import.

No Qt objects are touched here. This module itself imports nothing heavy, so
reading :func:`is_ready` from the GUI thread is free.
"""

import threading

from loguru import logger

_READY = threading.Event()
_started = False


def warm_duckdb_polars() -> None:
    """Import both libraries and do the first Arrow exchange between them."""
    import duckdb
    import polars as pl

    frame = pl.DataFrame({"value": [1]})
    with duckdb.connect(":memory:") as connection:
        connection.register("warmup_frame", frame)
        result = connection.sql("SELECT value FROM warmup_frame").pl()
        if result["value"].to_list() != [1]:
            raise RuntimeError("DuckDB/Polars warm-up returned unexpected data")


def _run() -> None:
    try:
        warm_duckdb_polars()
    except Exception as exc:  # noqa: BLE001 - warm-up is only an optimisation
        logger.debug(f"Data backend warm-up skipped: {exc}")
    finally:
        # Never leave a waiter hanging: if the warm-up failed, the first real
        # use pays for the import instead, exactly as without a warm-up.
        _READY.set()


def start_in_background() -> None:
    """Start the warm-up on its own thread; calling it again does nothing."""
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_run, daemon=True, name="data-warmup").start()


def is_ready() -> bool:
    """True once the warm-up has finished, or when none was ever started.

    A process that never starts a warm-up (the CLI, tests) has nothing to wait
    for, so it counts as ready.
    """
    return (not _started) or _READY.is_set()
