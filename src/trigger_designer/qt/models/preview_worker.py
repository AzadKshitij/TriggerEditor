"""Qt workers behind the Data Preview surfaces.

Collecting a preview window and counting a lazy source are the two operations
that can block, so both run on their own `QThread` and the panel only ever
sees finished results through signals. A running Polars scan cannot be
cancelled, so `PreviewRequestController` never tries: it checks every result
against the newest request id and drops superseded ones, and while one collect
is in flight it keeps only the newest pending payload.
"""

from functools import partial
from typing import Any

import polars as pl
from loguru import logger
from qtpy.QtCore import QObject, QThread, Signal

from trigger_designer.qt.models.preview_sampling import (
    PreviewWindow,
    collect_preview,
)


class PreviewCollectWorker(QThread):
    """Collects a bounded preview of a payload off the GUI thread."""

    finished_ok = Signal(object)  # PreviewWindow
    failed = Signal(str)  # reason

    def __init__(
        self,
        payload: Any,
        request_id: int = 0,
        max_rows: int = 1000,
        max_size_mb: float = 2.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.payload = payload
        self.request_id = request_id
        self.max_rows = max_rows
        self.max_size_mb = max_size_mb

    def run(self) -> None:
        try:
            window = collect_preview(
                self.payload,
                max_rows=self.max_rows,
                max_size_mb=self.max_size_mb,
            )
        except Exception as e:  # noqa: BLE001 - the worker boundary reports failure
            logger.warning(f"Preview collect failed: {e}")
            self.failed.emit(str(e))
            return
        self.finished_ok.emit(window)


class PreviewCountWorker(QThread):
    """Counts the rows of a lazy payload on its own thread."""

    finished_ok = Signal(int)  # total rows
    failed = Signal(str)  # reason

    def __init__(
        self,
        payload: Any,
        request_id: int = 0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.payload = payload
        self.request_id = request_id

    def run(self) -> None:
        try:
            count = int(self.payload.select(pl.len()).collect().item())
        except Exception as e:  # noqa: BLE001 - the worker boundary reports failure
            logger.debug(f"Preview count failed: {e}")
            self.failed.emit(str(e))
            return
        self.finished_ok.emit(count)


class PreviewRequestController(QObject):
    """Serialises preview collects: one in flight, the newest request wins.

    ``request()`` returns the new id. While one collect runs, only the newest
    payload is kept pending and started when the current finishes; results are
    checked against the newest id, so a superseded collect (or count) is
    dropped instead of showing stale data. A truncated lazy collect starts a
    count worker for the same id - counting runs on its own thread and never
    delays a collect.
    """

    previewReady = Signal(object)  # PreviewWindow of the newest request
    countReady = Signal(int)  # total rows, or -1 when counting failed
    failed = Signal(str)  # collect failure for the newest request
    busyChanged = Signal(bool)

    def __init__(
        self,
        max_rows: int = 1000,
        max_size_mb: float = 2.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.max_rows = max_rows
        self.max_size_mb = max_size_mb

        self._next_id = 0
        self._newest_id = 0
        self._newest_payload: Any = None
        self._pending: tuple[int, Any] | None = None
        self._collect_worker: PreviewCollectWorker | None = None
        self._count_workers: list[PreviewCountWorker] = []
        self._busy = False

    @property
    def busy(self) -> bool:
        """Whether a collect is in flight or a payload is waiting to run."""
        return self._busy

    def request(self, payload: Any) -> int:
        """Queue ``payload`` as the newest preview request; returns its id."""
        self._next_id += 1
        self._newest_id = self._next_id
        self._newest_payload = payload
        self._pending = (self._newest_id, payload)
        self._refresh_busy()
        self._start_next_collect()
        return self._newest_id

    def _start_next_collect(self) -> None:
        if self._collect_worker is not None or self._pending is None:
            return
        request_id, payload = self._pending
        self._pending = None
        worker = PreviewCollectWorker(
            payload, request_id, self.max_rows, self.max_size_mb
        )
        worker.finished_ok.connect(partial(self._on_collect_ok, request_id))
        worker.failed.connect(partial(self._on_collect_failed, request_id))
        worker.finished.connect(partial(self._reap_collect_worker, worker))
        self._collect_worker = worker
        worker.start()

    def _reap_collect_worker(self, worker: PreviewCollectWorker) -> None:
        if self._collect_worker is worker:
            self._collect_worker = None
        worker.deleteLater()
        self._start_next_collect()
        self._refresh_busy()

    def _on_collect_ok(self, request_id: int, window: PreviewWindow) -> None:
        if request_id != self._newest_id:
            return  # superseded by a newer request; drop silently
        self.previewReady.emit(window)
        if window.limited and window.is_lazy:
            self._start_count(request_id, self._newest_payload)

    def _on_collect_failed(self, request_id: int, message: str) -> None:
        if request_id != self._newest_id:
            return
        self.failed.emit(message)

    def _start_count(self, request_id: int, payload: Any) -> None:
        worker = PreviewCountWorker(payload, request_id)
        worker.finished_ok.connect(partial(self._on_count_ok, request_id))
        worker.failed.connect(partial(self._on_count_failed, request_id))
        worker.finished.connect(partial(self._reap_count_worker, worker))
        self._count_workers.append(worker)
        worker.start()

    def _reap_count_worker(self, worker: PreviewCountWorker) -> None:
        if worker in self._count_workers:
            self._count_workers.remove(worker)
        worker.deleteLater()

    def _on_count_ok(self, request_id: int, count: int) -> None:
        if request_id != self._newest_id:
            return
        self.countReady.emit(int(count))

    def _on_count_failed(self, request_id: int, message: str) -> None:
        logger.debug(f"Preview count failed for request {request_id}: {message}")
        if request_id != self._newest_id:
            return
        self.countReady.emit(-1)

    def _refresh_busy(self) -> None:
        busy = self._collect_worker is not None or self._pending is not None
        if busy != self._busy:
            self._busy = busy
            self.busyChanged.emit(busy)
