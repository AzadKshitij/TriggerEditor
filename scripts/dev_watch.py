#!/usr/bin/env python
"""Restart the Trigger Designer app whenever a watched source file changes.

A small development helper. It polls the source tree (``src`` by default) and,
after every settled change to a watched file, stops the running app together
with the ``uv run`` process that started it and starts it again with
``uv run trigger-designer``.

Only the standard library is used, so nothing has to be added to the project
dependencies - ``uv sync`` prunes anything that is not in the lock file. Meta's
Watchman and the ``watchdog`` package are not installed in this project
environment, and adding either would mean touching ``pyproject.toml`` and the
lock file, so the scan is a plain recursive mtime/size poll.

Usage (paths are resolved against the repository root, the working directory
does not matter)::

    uv run --project . python scripts/dev_watch.py
    uv run --project . python scripts/dev_watch.py --ext .py,.qss
    uv run --project . python scripts/dev_watch.py -- "savedfiles/0. All Node- Test.tds"

or simply ``scripts\\watch.bat``.

Behaviour notes:

- A burst of saves counts as one change: the app restarts only after
  ``--debounce`` seconds pass without further edits, so an editor that writes a
  file several times per save causes one restart.
- Ctrl+C stops the watcher and the app it started.
- If the app exits after having run for a while and with a failing exit code
  (a crash), it is started again. If it dies immediately, the watcher waits for
  the next file change instead, so broken code cannot become a restart loop.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WATCH_PATHS = ("src",)
DEFAULT_SUFFIXES = (".py",)
DEFAULT_INTERVAL_SECONDS = 0.5
DEFAULT_DEBOUNCE_SECONDS = 0.6
UV_EXECUTABLE = "uv"
ENTRY_POINT = "trigger-designer"

# An app that exits this early is treated as broken rather than crashed:
# restarting it would only loop on the same error, so the watcher waits for the
# next saved change.
CRASH_RESTART_MIN_UPTIME_SECONDS = 5.0

# Directories that never hold sources worth watching.
SKIP_DIRECTORIES = frozenset(
    {
        "__pycache__",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "node_modules",
    }
)

# path -> (mtime_ns, size) for every file the watcher tracks
Snapshot = dict[Path, tuple[int, int]]


def log(message: str) -> None:
    """Print one watcher line, timestamped and flushed to interleave with app output."""
    print(f"{time.strftime('%H:%M:%S')} [watch] {message}", flush=True)


def label(path: Path) -> str:
    """Shorten a path for the console when it lives under the repository root."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def scan_sources(paths: Sequence[Path], suffixes: frozenset[str]) -> Snapshot:
    """Fingerprint every watched file, keyed by path."""
    snapshot: Snapshot = {}
    for root in paths:
        for directory, dirnames, filenames in root.walk():
            dirnames[:] = sorted(
                name
                for name in dirnames
                if name not in SKIP_DIRECTORIES and not name.startswith(".")
            )
            for name in filenames:
                # Skip editor litter such as ".file.py.swp" or "file.py~".
                if name.startswith(".") or Path(name).suffix not in suffixes:
                    continue
                path = directory / name
                try:
                    stat = path.stat()
                except OSError:
                    continue  # vanished between the listing and the stat
                snapshot[path] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def describe_changes(before: Snapshot, after: Snapshot) -> list[str]:
    """One line per added, modified or removed file."""
    changes: list[str] = []
    for path, stamp in after.items():
        if path not in before:
            changes.append(f"+ {label(path)}")
        elif before[path] != stamp:
            changes.append(f"~ {label(path)}")
    changes.extend(f"- {label(path)}" for path in before if path not in after)
    return changes


class AppProcess:
    """The ``uv run trigger-designer`` child process and its children."""

    def __init__(self, command: Sequence[str]) -> None:
        self._command = list(command)
        self._process: subprocess.Popen[bytes] | None = None
        self._started_at = 0.0
        self._stop_requested = False
        self._exit_reported = False

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def returncode(self) -> int | None:
        return None if self._process is None else self._process.returncode

    def uptime(self) -> float:
        return time.monotonic() - self._started_at

    def exited_on_its_own(self) -> bool:
        """True once, the first time the app stopped without the watcher asking it to."""
        process = self._process
        if process is None or self._stop_requested or self._exit_reported:
            return False
        if process.poll() is None:
            return False
        self._exit_reported = True
        return True

    def start(self) -> None:
        """Start the app, inheriting this console so its logs stay visible."""
        creationflags = 0
        if os.name == "nt":
            # Keep Ctrl+C pointed at the watcher: the app should not see it.
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        self._process = subprocess.Popen(
            self._command,
            cwd=PROJECT_ROOT,
            creationflags=creationflags,
            start_new_session=os.name != "nt",
        )
        self._started_at = time.monotonic()
        self._stop_requested = False
        self._exit_reported = False
        log(f"app started (pid {self._process.pid})")

    def stop(self) -> None:
        """Stop the app and the process tree below it, and wait for it to be gone."""
        process = self._process
        if process is None or process.poll() is not None:
            return
        self._stop_requested = True
        log(f"stopping app (pid {process.pid})")
        if os.name == "nt":
            # `uv run` sits between us and the GUI process, so kill the tree.
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            log("app did not exit in time; forcing it")
            process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                log("warning: the app process is still alive")


def parse_extensions(value: str) -> tuple[str, ...]:
    """argparse type for ``--ext``: ".py,.qss" -> (".py", ".qss")."""
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        raise argparse.ArgumentTypeError(
            "expected at least one extension, e.g. .py,.qss"
        )
    return tuple(part if part.startswith(".") else f".{part}" for part in parts)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dev_watch",
        description=(
            "Restart `uv run trigger-designer` whenever a watched source file changes."
        ),
    )
    parser.add_argument(
        "--path",
        action="append",
        metavar="DIR",
        help=(
            "directory to watch, relative to the repository root; repeatable "
            f"(default: {', '.join(DEFAULT_WATCH_PATHS)})"
        ),
    )
    parser.add_argument(
        "--ext",
        type=parse_extensions,
        default=DEFAULT_SUFFIXES,
        metavar="EXTS",
        help=f"comma-separated extensions to watch (default: {', '.join(DEFAULT_SUFFIXES)})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        metavar="SECONDS",
        help="pause between directory scans (default: %(default)s)",
    )
    parser.add_argument(
        "--debounce",
        type=float,
        default=DEFAULT_DEBOUNCE_SECONDS,
        metavar="SECONDS",
        help="quiet period a save burst must reach before restarting (default: %(default)s)",
    )
    parser.add_argument(
        "app_args",
        nargs="*",
        metavar="APP_ARG",
        help="extra arguments handed to the app, such as a .tds file (put them after `--`)",
    )
    args = parser.parse_args(argv)

    args.watch_paths = [
        PROJECT_ROOT / path for path in (args.path or DEFAULT_WATCH_PATHS)
    ]
    missing = [path for path in args.watch_paths if not path.is_dir()]
    if missing:
        parser.error("watch directory not found: " + ", ".join(str(p) for p in missing))
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    uv = shutil.which(UV_EXECUTABLE)
    if uv is None:
        log("error: `uv` is not on PATH - see https://github.com/astral-sh/uv")
        return 1

    watch_paths: list[Path] = args.watch_paths
    suffixes = frozenset(args.ext)
    command = [
        uv,
        "run",
        "--project",
        str(PROJECT_ROOT),
        ENTRY_POINT,
        *args.app_args,
    ]
    app = AppProcess(command)

    snapshot = scan_sources(watch_paths, suffixes)
    log(
        f"watching {len(snapshot)} file(s) in {', '.join(label(p) for p in watch_paths)}"
    )
    log(
        f"extensions {', '.join(sorted(suffixes))}; "
        f"interval {args.interval:g}s; debounce {args.debounce:g}s"
    )
    log("Ctrl+C stops the watcher and the app")

    restart_at: float | None = None
    app.start()
    try:
        while True:
            if app.exited_on_its_own():
                code = app.returncode()
                uptime = app.uptime()
                log(f"app exited on its own (exit code {code}, after {uptime:.1f}s)")
                if code not in (0, None) and uptime >= CRASH_RESTART_MIN_UPTIME_SECONDS:
                    log("starting it again after the crash")
                    app.start()
                    restart_at = None
                else:
                    log("waiting for a source change to start it again")

            current = scan_sources(watch_paths, suffixes)
            if current != snapshot:
                for change in describe_changes(snapshot, current):
                    log(f"  {change}")
                snapshot = current
                if restart_at is not None:
                    log("still changing - restart postponed")
                else:
                    log("change detected")
                restart_at = time.monotonic() + max(args.debounce, 0.0)

            if restart_at is not None and time.monotonic() >= restart_at:
                restart_at = None
                if app.is_running():
                    app.stop()
                app.start()

            delay = args.interval
            if restart_at is not None:
                # Wake up for the restart even with a long interval.
                delay = min(delay, max(0.02, restart_at - time.monotonic()))
            time.sleep(max(0.02, delay))
    except KeyboardInterrupt:
        print()
        log("interrupted - shutting down")
    finally:
        app.stop()

    log("watcher stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
