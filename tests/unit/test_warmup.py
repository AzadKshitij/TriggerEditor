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


# --- readiness, so work that needs the libraries can wait for them -----------


def _fresh_state(monkeypatch):
    import threading

    from trigger_designer.core import warmup

    monkeypatch.setattr(warmup, "_started", False)
    monkeypatch.setattr(warmup, "_READY", threading.Event())
    return warmup


def test_a_process_that_never_starts_a_warmup_counts_as_ready(monkeypatch):
    warmup = _fresh_state(monkeypatch)
    assert warmup.is_ready() is True


def test_ready_only_after_the_background_warmup_finishes(monkeypatch):
    import threading

    warmup = _fresh_state(monkeypatch)
    release = threading.Event()
    monkeypatch.setattr(warmup, "warm_duckdb_polars", lambda: release.wait(10))

    warmup.start_in_background()
    assert warmup.is_ready() is False  # started, still working
    release.set()
    assert warmup._READY.wait(10)
    assert warmup.is_ready() is True


def test_a_failed_warmup_still_releases_the_waiters(monkeypatch):
    warmup = _fresh_state(monkeypatch)

    def boom() -> None:
        raise RuntimeError("no libraries for you")

    monkeypatch.setattr(warmup, "warm_duckdb_polars", boom)
    warmup.start_in_background()
    assert warmup._READY.wait(10)
    assert warmup.is_ready() is True


def test_starting_twice_runs_one_warmup(monkeypatch):
    warmup = _fresh_state(monkeypatch)
    calls: list[int] = []
    monkeypatch.setattr(warmup, "warm_duckdb_polars", lambda: calls.append(1))

    warmup.start_in_background()
    warmup.start_in_background()
    assert warmup._READY.wait(10)
    assert calls == [1]
