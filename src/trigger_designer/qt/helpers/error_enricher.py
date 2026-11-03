"""Run enrichment off the GUI thread and post the result back."""

from __future__ import annotations

from collections.abc import Callable

from qtpy.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot

from trigger_designer.core.errors import EnrichJob, EnrichResult, enrich_error

_ACTIVE: set[tuple[object, object]] = set()


class _Signals(QObject):
    done = Signal(object)


class _Bridge(QObject):
    def __init__(self, callback: Callable[[EnrichResult], None]) -> None:
        super().__init__()
        self._callback = callback

    @Slot(object)
    def handle(self, result: EnrichResult) -> None:
        self._callback(result)


class ErrorEnricher(QRunnable):
    def __init__(self, job: EnrichJob) -> None:
        super().__init__()
        self.job = job
        self.signals = _Signals()

    def run(self) -> None:
        try:
            result = enrich_error(self.job)
        except Exception:  # noqa: BLE001 - enrichment never fails a run
            result = EnrichResult(
                root=self.job.error,
                knock_on=None,
                culprit_node_id=self.job.error.culprit_node_id,
            )
        self.signals.done.emit(result)


def start_enrichment(
    job: EnrichJob,
    on_done: Callable[[EnrichResult], None],
    *,
    timeout_s: float = 10.0,
) -> None:
    runner = ErrorEnricher(job)
    state = {"done": False}

    def finish(result: EnrichResult) -> None:
        if state["done"]:
            return
        state["done"] = True
        _ACTIVE.discard((runner, bridge))
        on_done(result)

    bridge = _Bridge(finish)
    runner.signals.done.connect(bridge.handle)
    runner._bridge = bridge  # type: ignore[attr-defined]
    _ACTIVE.add((runner, bridge))
    QThreadPool.globalInstance().start(runner)

    def abandon() -> None:
        if state["done"]:
            return
        finish(
            EnrichResult(
                root=job.error.with_updates(locate_status="timeout"),
                knock_on=None,
                culprit_node_id=job.error.culprit_node_id,
            )
        )

    QTimer.singleShot(int(timeout_s * 1000), abandon)
