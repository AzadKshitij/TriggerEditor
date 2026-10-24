"""Capture crash evidence that never reaches Python's exception machinery.

Qt and its native dependencies fail in C++: Windows ends the process with an
access violation (0xC0000005), or Qt calls ``qFatal()`` and fail-fasts with
0xC0000409. Neither path raises a Python exception, so nothing reaches the
console or the log file and the app looks like it vanished without a reason.

``faulthandler`` writes every thread's Python stack to the log when the
process faults. The exception hooks below cover the paths that do run Python
code (a slot, a worker thread), and the Qt message handler keeps the warning
Qt prints immediately before a fatal abort, such as "QThread: Destroyed while
thread is still running".
"""

from __future__ import annotations

import faulthandler
import sys
import threading
from pathlib import Path
from types import TracebackType
from typing import IO, Any

from loguru import logger
from qtpy.QtCore import QtMsgType, qInstallMessageHandler

_QT_LEVELS = {
    QtMsgType.QtDebugMsg: "DEBUG",
    QtMsgType.QtInfoMsg: "INFO",
    QtMsgType.QtWarningMsg: "WARNING",
    QtMsgType.QtCriticalMsg: "ERROR",
    QtMsgType.QtFatalMsg: "CRITICAL",
}

#: faulthandler writes to a raw file descriptor, so the handle must outlive
#: this call. Keeping it module-level also stops the loguru sink from being
#: the only owner of the crash output.
_fault_file: IO[bytes] | None = None


def flush_logs() -> None:
    """Push everything written so far to disk; a crash gives no second chance."""
    try:
        logger.complete()
    except Exception:  # noqa: BLE001, S110 - flushing must never fail the caller
        pass
    handle = _fault_file
    if handle is not None:
        try:
            handle.flush()
        except Exception:  # noqa: BLE001, S110 - the descriptor may already be gone
            pass
    try:
        if sys.__stderr__ is not None:
            sys.__stderr__.flush()
    except Exception:  # noqa: BLE001, S110 - a closed console is not an error here
        pass


def _log_uncaught(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    """``sys.excepthook``: Python exception that escaped the application."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    try:
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical(
            "Unhandled exception"
        )
    finally:
        flush_logs()


def _log_thread_exception(args: Any) -> None:
    """``threading.excepthook``: exception in a plain Python worker thread.

    The node executor and the startup warm-up run on ``threading.Thread``;
    without this hook their failures only reach stderr, which a windowed
    build does not have.
    """
    if args.exc_type is SystemExit:
        return
    thread_name = args.thread.name if args.thread is not None else "unknown"
    try:
        logger.opt(
            exception=(args.exc_type, args.exc_value, args.exc_traceback)
        ).critical("Unhandled exception in thread '{}'", thread_name)
    finally:
        flush_logs()


def _log_qt_message(mode: QtMsgType, context: Any, message: str) -> None:
    """``qInstallMessageHandler``: Qt's own warnings, including qFatal's."""
    level = _QT_LEVELS.get(mode, "DEBUG")
    where = ""
    try:
        if context is not None and getattr(context, "file", None):
            where = f" ({context.file}:{context.line})"
        logger.log(level, "Qt: {}{}", message, where)
        if mode == QtMsgType.QtFatalMsg:
            # qFatal() aborts as soon as this handler returns.
            flush_logs()
    except Exception:  # noqa: BLE001, S110 - never recurse into a failing logger
        pass


def install_crash_capture(log_path: Path) -> bool:
    """Attach faulthandler, Python hooks and a Qt message handler.

    Returns ``True`` when faulthandler could be armed. Safe to call more than
    once: a later call replaces the previous hooks and fault file.
    """
    global _fault_file

    if _fault_file is not None:
        faulthandler.disable()
        try:
            _fault_file.close()
        except OSError:
            pass
        _fault_file = None

    try:
        handle: IO[bytes] | None = open(  # noqa: SIM115 - must outlive the call
            log_path, "ab", buffering=0
        )
    except OSError as exc:
        logger.warning("Crash capture disabled: cannot open {}: {}", log_path, exc)
        handle = None

    armed = False
    if handle is not None:
        _fault_file = handle
        try:
            faulthandler.enable(file=handle, all_threads=True)
            armed = True
        except (OSError, ValueError, RuntimeError) as exc:
            logger.warning("faulthandler could not be enabled: {}", exc)

    sys.excepthook = _log_uncaught
    threading.excepthook = _log_thread_exception
    qInstallMessageHandler(_log_qt_message)
    return armed
