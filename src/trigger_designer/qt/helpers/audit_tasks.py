"""Run audit work (verify, check inputs, export) off the GUI thread.

``AuditTask`` wraps one callable ``fn(cancel_event, *args)``. The result comes
back through queued signals, so the Run History dock never reads a big file or
hashes an input on the GUI thread. The owner keeps a reference to the task and
its signals until ``done`` / ``failed`` arrives (Qt would otherwise delete the
QObject mid-flight).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from loguru import logger
from qtpy.QtCore import QObject, QRunnable, Signal


class AuditTaskSignals(QObject):
    done = Signal(object)  # the callable's return value
    failed = Signal(str)  # "ExcType: message"


class AuditTask(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._cancel = threading.Event()
        self.signals = AuditTaskSignals()
        # Python owns the task: the dock holds it until a signal arrives.
        self.setAutoDelete(False)

    @property
    def cancel_event(self) -> threading.Event:
        return self._cancel

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            result = self._fn(self._cancel, *self._args)
        except Exception as exc:  # noqa: BLE001 - reported through the signal
            logger.debug("audit task failed: {}", exc)
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.signals.done.emit(result)
