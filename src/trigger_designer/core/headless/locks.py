"""Per-workflow run lock with stale-run recovery (plan 08 S5). Qt-free."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import socket
import time
from datetime import UTC, datetime
from pathlib import Path

from trigger_designer.core.headless.atomic import write_bytes_atomic
from trigger_designer.core.headless.exit_codes import CliError, ExitCode


def lock_path(state: Path, workflow: str) -> Path:
    key = os.path.normcase(os.path.abspath(workflow))
    digest = hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:16]
    return Path(state) / "locks" / f"{digest}.lock"


def _create_time(pid: int) -> float | None:
    import psutil

    try:
        return psutil.Process(pid).create_time()
    except psutil.Error:
        return None


def _owner_alive(info: dict) -> bool:
    import psutil

    pid = info.get("pid")
    if not isinstance(pid, int) or not psutil.pid_exists(pid):
        return False
    started = _create_time(pid)
    recorded = info.get("create_time")
    if started is None:
        return False
    return not (
        isinstance(recorded, (int, float)) and abs(started - float(recorded)) >= 1.0
    )


class RunLock:
    """``acquire()`` raises ``CliError(BUSY)`` while another live run holds it."""

    def __init__(self, path: Path, run_id: str) -> None:
        self.path = Path(path)
        self.run_id = run_id
        self._held = False
        self._staged: list[dict] = []

    # -- helpers ---------------------------------------------------------
    def _payload(self) -> bytes:
        return json.dumps(
            {
                "pid": os.getpid(),
                "create_time": _create_time(os.getpid()),
                "run_id": self.run_id,
                "started_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "host": socket.gethostname(),
                "staged": self._staged,
            }
        ).encode("utf-8")

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except OSError, ValueError:
            return {}

    @staticmethod
    def sweep(info: dict) -> None:
        """Clean what a dead run left: staged files go, a parked previous output
        is put back when the final file is missing (killed mid-commit)."""
        for entry in info.get("staged", []):
            if not isinstance(entry, dict):
                continue
            final, backup = entry.get("final"), entry.get("backup")
            leftovers = [entry.get("staged")]
            if final:
                leftovers.append(
                    os.path.join(
                        os.path.dirname(final),
                        f".{os.path.basename(final)}.tdtmp-copy",
                    )
                )
            if backup and os.path.exists(backup):
                if final and not os.path.exists(final):
                    with contextlib.suppress(OSError):
                        os.replace(backup, final)
                else:
                    leftovers.append(backup)
            for path in leftovers:
                if path:
                    with contextlib.suppress(OSError):
                        os.unlink(path)

    # -- API --------------------------------------------------------------
    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in (0, 1):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                info = self._read()
                if _owner_alive(info) and attempt == 0:
                    raise CliError(
                        ExitCode.BUSY,
                        "TD-CLI-012",
                        f"This workflow is already running (pid {info.get('pid')}, "
                        f"run {str(info.get('run_id'))[:8]}).",
                        "Wait for the other run to finish; if none is running, run "
                        "again (stale locks clear themselves).",
                    ) from None
                self.sweep(info)
                with contextlib.suppress(OSError):
                    self.path.unlink()
                time.sleep(0.05)
                continue
            with os.fdopen(fd, "wb") as handle:
                handle.write(self._payload())
            self._held = True
            return
        raise CliError(ExitCode.BUSY, "TD-CLI-012", "The run lock could not be taken.")

    def note_staged(self, entries: list[dict]) -> None:
        """Record staged/backup/final paths so a crash can be cleaned up."""
        self._staged = list(entries)
        if self._held:
            write_bytes_atomic(self.path, self._payload())

    def release(self) -> None:
        if self._held:
            with contextlib.suppress(OSError):
                self.path.unlink()
            self._held = False
