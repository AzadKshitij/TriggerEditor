"""JSON-lines events and the private stdout channel (plan 08 3.9, X9). Qt-free."""

from __future__ import annotations

import contextlib
import os
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

MAX_LOG_BYTES = 10 * 1024 * 1024
LOG_BACKUPS = 3


def utc_ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def capture_stdout_channel() -> IO[bytes]:
    """Keep the real stdout for our JSON lines; everything that ``print``s goes
    to stderr (vendored code and node code write to stdout)."""
    out = os.fdopen(os.dup(1), "wb", 0)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return out


def rotate(
    path: Path, max_bytes: int = MAX_LOG_BYTES, backups: int = LOG_BACKUPS
) -> None:
    """``FILE`` -> ``FILE.1`` -> ... -> ``FILE.<backups>`` when it grew past ``max_bytes``."""
    try:
        if path.stat().st_size <= max_bytes:
            return
    except OSError:
        return
    oldest = path.with_name(f"{path.name}.{backups}")
    with contextlib.suppress(OSError):
        oldest.unlink()
    for index in range(backups - 1, 0, -1):
        src = path.with_name(f"{path.name}.{index}")
        if src.exists():
            with contextlib.suppress(OSError):
                os.replace(src, path.with_name(f"{path.name}.{index + 1}"))
    with contextlib.suppress(OSError):
        os.replace(path, path.with_name(f"{path.name}.1"))


class Emitter:
    """One object per run: JSON lines on ``stream`` (json) or text on stderr."""

    def __init__(
        self,
        fmt: str = "text",
        log_file: str | os.PathLike | None = None,
        *,
        stream: IO[bytes] | None = None,
        run_id: str = "",
        quiet: bool = False,
        max_bytes: int = MAX_LOG_BYTES,
    ) -> None:
        self.fmt = fmt
        self.run_id = run_id
        self.quiet = quiet
        self._stream = stream
        self._lock = threading.Lock()
        self._stream_broken = False
        self._file: IO[bytes] | None = None
        self.events: list[dict] = []
        if log_file:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            rotate(path, max_bytes)
            self._file = open(path, "ab")  # noqa: SIM115 - closed in close()

    def _write_stdout(self, data: bytes) -> None:
        if self._stream_broken:
            return
        try:
            if self._stream is not None:
                self._stream.write(data)
                self._stream.flush()
            else:
                sys.stdout.write(data.decode("utf-8"))
                sys.stdout.flush()
        except BrokenPipeError, OSError, ValueError:
            self._stream_broken = True

    def emit(self, event: str, level: str = "INFO", **fields: Any) -> dict:
        import orjson

        record: dict[str, Any] = {
            "ts": utc_ts(),
            "level": level,
            "event": event,
            "run_id": self.run_id,
            **fields,
        }
        line = orjson.dumps(record, option=orjson.OPT_NON_STR_KEYS, default=str) + b"\n"
        with self._lock:
            self.events.append(record)
            if self._file is not None:
                with contextlib.suppress(OSError, ValueError):
                    self._file.write(line)
                    self._file.flush()
            if self.fmt == "json":
                self._write_stdout(line)
            else:
                important = level in ("WARNING", "ERROR", "CRITICAL") or event in (
                    "run.started",
                    "run.finished",
                )
                if not self.quiet or important:
                    extras = " ".join(
                        f"{k}={_short(v)}"
                        for k, v in fields.items()
                        if v not in (None, [], {}, "")
                    )
                    text = f"{record['ts'][11:19]} {level:<7} {event} {extras}\n"
                    with contextlib.suppress(OSError, ValueError):
                        sys.stderr.write(text)
                        sys.stderr.flush()
        return record

    def close(self) -> None:
        with self._lock:
            if self._file is not None:
                with contextlib.suppress(OSError):
                    self._file.close()
                self._file = None


def _short(value: Any) -> str:
    text = str(value)
    return text if len(text) <= 160 else text[:157] + "..."


def attach_loguru_bridge(emitter: Emitter, level: str = "WARNING") -> int | None:
    """Route loguru records into ``log`` events (removes loguru's own sinks)."""
    try:
        from loguru import logger
    except ImportError:
        return None
    logger.remove()

    def sink(message) -> None:
        record = message.record
        emitter.emit(
            "log",
            level=record["level"].name,
            source=record["name"],
            message=record["message"],
        )

    return logger.add(sink, level=level)
