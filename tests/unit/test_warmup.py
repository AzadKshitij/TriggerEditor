"""The startup warm-up must be safe to run on a background thread."""

import sys
from pathlib import Path
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

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
