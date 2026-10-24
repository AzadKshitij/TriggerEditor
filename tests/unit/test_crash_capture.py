"""Crash capture: Python and Qt failures reach the log instead of vanishing."""

from __future__ import annotations

import faulthandler
import sys
import threading

import pytest
from loguru import logger
from qtpy.QtCore import QtMsgType, qInstallMessageHandler

from trigger_designer.qt.helpers import crash_capture


@pytest.fixture()
def messages():
    captured: list[str] = []
    sink_id = logger.add(lambda message: captured.append(str(message)), level="DEBUG")
    yield captured
    logger.remove(sink_id)


def test_uncaught_exception_is_logged(messages) -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        crash_capture._log_uncaught(*sys.exc_info())

    joined = "\n".join(messages)
    assert "Unhandled exception" in joined
    assert "RuntimeError: boom" in joined


def test_thread_exception_names_the_thread(messages) -> None:
    args = threading.ExceptHookArgs(
        (
            RuntimeError,
            RuntimeError("thread boom"),
            None,
            threading.current_thread(),
        )
    )

    crash_capture._log_thread_exception(args)

    joined = "\n".join(messages)
    assert "thread 'MainThread'" in joined
    assert "RuntimeError: thread boom" in joined


def test_qt_fatal_message_is_logged(messages) -> None:
    crash_capture._log_qt_message(
        QtMsgType.QtFatalMsg,
        None,
        "QThread: Destroyed while thread is still running",
    )

    assert any("QThread: Destroyed" in message for message in messages)


def test_install_arms_faulthandler_and_hooks(tmp_path) -> None:
    original_excepthook = sys.excepthook
    original_thread_hook = threading.excepthook
    log_path = tmp_path / "crash.log"

    try:
        assert crash_capture.install_crash_capture(log_path) is True

        assert faulthandler.is_enabled()
        assert sys.excepthook is crash_capture._log_uncaught
        assert threading.excepthook is crash_capture._log_thread_exception
        assert log_path.exists()
    finally:
        faulthandler.disable()
        if crash_capture._fault_file is not None:
            crash_capture._fault_file.close()
            crash_capture._fault_file = None
        sys.excepthook = original_excepthook
        threading.excepthook = original_thread_hook
        qInstallMessageHandler(None)
