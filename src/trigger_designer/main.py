"""Main entry point for Trigger Designer application."""

import datetime
from pathlib import Path
import os
import re
import sys
import threading
from typing import Optional, TextIO

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger
from qtpy.QtCore import QSettings
from qtpy.QtGui import QIcon, QGuiApplication, QScreen
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.splash import Splash

_LOG_STREAM_LOCK = threading.Lock()
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _strip_ansi_escape_sequences(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text)


def _should_flush(text: str) -> bool:
    return "\n" in text or "\r" in text


class _TeeStream:
    def __init__(self, terminal_stream: TextIO, log_stream: TextIO) -> None:
        self._terminal_stream = terminal_stream
        self._log_stream = log_stream

    def write(self, text: str) -> int:
        if not text:
            return 0

        with _LOG_STREAM_LOCK:
            self._terminal_stream.write(text)
            self._log_stream.write(_strip_ansi_escape_sequences(text))
            if _should_flush(text):
                self._terminal_stream.flush()
                self._log_stream.flush()

        return len(text)

    def flush(self) -> None:
        with _LOG_STREAM_LOCK:
            self._terminal_stream.flush()
            self._log_stream.flush()

    def isatty(self) -> bool:
        return self._terminal_stream.isatty()

    def __getattr__(self, name: str) -> object:
        return getattr(self._terminal_stream, name)


class _LogFileSink:
    def __init__(self, log_stream: TextIO) -> None:
        self._log_stream = log_stream

    def write(self, text: str) -> int:
        if not text:
            return 0

        with _LOG_STREAM_LOCK:
            self._log_stream.write(text)
            if _should_flush(text):
                self._log_stream.flush()

        return len(text)

    def flush(self) -> None:
        with _LOG_STREAM_LOCK:
            self._log_stream.flush()


def _log_dir() -> Path:
    # ponytail: frozen logs go to user scope; Program Files is not writable
    if getattr(sys, "frozen", False):
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "Trigger Designer" / "logs"
        return Path.home() / ".trigger_designer" / "logs"
    return Path(__file__).resolve().parents[2] / "logs"


def _configure_logging() -> None:
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir / f"trigger_designer_{time}.log"

    try:
        log_file_handle = log_file_path.open("a", encoding="utf-8")
    except OSError as exc:
        logger.remove()
        logger.add(
            original_stderr,
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
        )
        logger.warning(f"Unable to open log file {log_file_path}: {exc}")
        return

    sys.stdout = _TeeStream(original_stdout, log_file_handle)
    sys.stderr = _TeeStream(original_stderr, log_file_handle)

    logger.remove()
    logger.add(
        original_stderr,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
    )
    logger.add(
        _LogFileSink(log_file_handle),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
        colorize=False,
    )


_configure_logging()


def main() -> None:
    file_path: Optional[str] = sys.argv[1] if len(sys.argv) > 1 else None

    logger.info("Starting Trigger Designer...")
    logger.info(f"System arguments: {sys.argv}")

    # Initialize application first so the splash paints before heavy imports
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Application configuration
    name_company = "Trigger"
    name_product = "Trigger Designer"
    app.setApplicationName(name_company)
    app.setApplicationDisplayName(name_product)

    # Initialize resource manager and set up application
    resource_manager = ResourceManager()
    app.setWindowIcon(QIcon(str(resource_manager.get_full_path("app_icon"))))

    # Show splash screen BEFORE importing the main window (imports
    # nodeeditor + all dock/node machinery, ~0.4s on importtime profile)
    primary_screen: Optional[QScreen] = QGuiApplication.primaryScreen()
    screen_width = primary_screen.geometry().width() if primary_screen else 800
    splash = Splash(
        resource_manager=resource_manager,
        screen_width=screen_width,
        splash_name="splash_screen",
        device_ratio=app.devicePixelRatio(),
    )
    splash.show()
    app.processEvents()

    # Heavy imports deferred until the splash is visible
    import trigger_designer.qt.darkstyle_rc  # noqa: F401
    import trigger_designer.resources.icons_rc  # noqa: F401
    from trigger_designer.qt.main_window import TriggerWindow
    from trigger_designer.qt.node_editor_colors import (
        apply_node_editor_colors,
        load_node_editor_colors,
    )

    # Load settings and theme
    settings = QSettings(name_company, name_product)
    logger.debug(f"Available settings keys: {settings.allKeys()}")

    theme_qss = resource_manager.load_theme(settings.value("theme", "dark"))
    if theme_qss:
        app.setStyleSheet(theme_qss)
    app.processEvents()

    # Apply saved edge/socket colors before any workflow scene is created, so
    # every node/edge/socket is built with the user's colors from the start.
    apply_node_editor_colors(load_node_editor_colors())

    # Create and show main window
    main_window = TriggerWindow(
        file_path=file_path,
        name_company=name_company,
        name_product=name_product,
    )
    main_window.show()
    main_window.activateWindow()

    # Hide splash screen
    splash.finish(main_window)

    if not file_path:
        try:
            main_window.showWelcomeDialogIfNeeded()
        except Exception as exc:
            logger.warning(f"Welcome dialog skipped: {exc}")

    logger.info("Trigger Designer started successfully")
    sys.exit(app.exec())


if __name__ == "__main__":
    import multiprocessing

    sys.dont_write_bytecode = True
    multiprocessing.freeze_support()
    main()
