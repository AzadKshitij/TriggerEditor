"""Cancel, timeout and memory supervision for a CLI run (plan 08 3.7, S5)."""

from __future__ import annotations

import os
import signal
import threading
import time
from collections.abc import Callable

from trigger_designer.core.headless.exit_codes import ExitCode

POLL_S = 0.25


class Supervisor:
    """Owns the cancel flag (checked between nodes) and the forced exits.

    The wall-clock ``deadline_s`` starts at construction, which is when the
    run begins (after argument parsing and imports, not at process start);
    ``max_memory_mb`` is an absolute RSS ceiling.
    """

    def __init__(
        self,
        *,
        deadline_s: float | None,
        max_memory_mb: float | None,
        cancel_grace_s: float,
        emit: Callable[..., object],
        on_force: Callable[[ExitCode, str], None],
        exit_fn: Callable[[int], None] = os._exit,
    ) -> None:
        self.cancel = threading.Event()
        self.deadline_s = deadline_s or None
        self.max_memory_mb = max_memory_mb or None
        self.cancel_grace_s = cancel_grace_s
        self.emit = emit
        self.on_force = on_force
        self._exit = exit_fn
        self._signals = 0
        self._t0 = time.monotonic()
        self._cancel_at: float | None = None
        self._forcing = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- signals ------------------------------------------------------------
    def install_signal_handlers(self) -> None:
        for name in ("SIGINT", "SIGBREAK", "SIGTERM"):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), self._on_signal)

    def _on_signal(self, signum, frame) -> None:
        self.request_cancel("signal")

    def request_cancel(self, reason: str = "requested") -> None:
        self._signals += 1
        self.cancel.set()
        if self._cancel_at is None:
            self._cancel_at = time.monotonic()
            self.emit(
                "run.cancelling",
                level="WARNING",
                reason=reason,
                elapsed_s=round(self.elapsed(), 3),
            )
        if self._signals >= 2:
            self.force_exit(ExitCode.CANCELLED, "cancel_forced")

    # -- watchdog -----------------------------------------------------------
    def elapsed(self) -> float:
        return time.monotonic() - self._t0

    def rss_mb(self) -> float:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)

    def check_once(self) -> None:
        """One watchdog pass (the thread loops over this; tests call it)."""
        if self.deadline_s and self.elapsed() > self.deadline_s:
            self.force_exit(ExitCode.TIMEOUT, "timeout")
        if self.max_memory_mb:
            rss = self.rss_mb()
            if rss > self.max_memory_mb:
                self.force_exit(ExitCode.MEMORY, "memory_exceeded", rss_mb=rss)
        if (
            self._cancel_at is not None
            and time.monotonic() - self._cancel_at > self.cancel_grace_s
        ):
            self.force_exit(ExitCode.CANCELLED, "cancel_forced")

    def start_watchdog(self) -> None:
        def loop() -> None:
            while not self._stop.wait(POLL_S):
                try:
                    self.check_once()
                except Exception:  # noqa: BLE001, S110 - the watchdog must live on
                    pass

        self._thread = threading.Thread(target=loop, daemon=True, name="td-watchdog")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def poll(self, runner: threading.Thread) -> None:
        """Main thread: ``time.sleep`` polling lets Python run signal handlers."""
        while runner.is_alive():
            time.sleep(0.2)

    # -- forced exit --------------------------------------------------------
    def force_exit(self, code: ExitCode, reason: str, **fields) -> None:
        if not self._forcing.acquire(blocking=False):
            return
        event = {
            "timeout": "run.timeout",
            "memory_exceeded": "run.memory_exceeded",
            "cancel_forced": "run.cancel_forced",
        }.get(reason, f"run.{reason}")
        try:
            self.emit(
                event,
                level="ERROR",
                reason=reason,
                elapsed_s=round(self.elapsed(), 3),
                **fields,
            )
            self.on_force(code, reason)
        finally:
            self._exit(int(code))
