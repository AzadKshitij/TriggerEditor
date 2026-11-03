"""The startup warm-up must be safe to run on a background thread."""

from threading import Thread

from trigger_designer.core.warmup import warm_duckdb_polars


def test_data_bridge_can_initialize_on_worker_thread() -> None:
    errors = []

    def warm() -> None:
        try:
            warm_duckdb_polars()
        except Exception as exc:  # noqa: BLE001 - propagate worker errors to test
            errors.append(exc)

    worker = Thread(target=warm)
    worker.start()
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert not errors
