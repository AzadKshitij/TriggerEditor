"""
Global logging functionality for the Trigger Designer application.

This module provides a global logger that can be used from anywhere in the application
to log messages to the currently active design window's logging dock.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import threading

if TYPE_CHECKING:
    from trigger_designer.qt.main_window import TriggerWindow
    from trigger_designer.qt.design_window import TriggerSubWindow
    from trigger_designer.qt.docks.logging_dock import LoggingDock


class GlobalLogger:
    """Global logger that routes messages to the active design window's logging dock"""

    _instance: Optional["GlobalLogger"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._main_window: Optional["TriggerWindow"] = None

    @classmethod
    def get_instance(cls) -> "GlobalLogger":
        """Get the singleton instance of GlobalLogger"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def set_main_window(self, main_window: "TriggerWindow") -> None:
        """Set the main window reference for logging"""
        self._main_window = main_window

    def get_active_design_window(self) -> Optional["TriggerSubWindow"]:
        """Get the currently active design window"""
        if not self._main_window:
            return None

        try:
            current_widget = self._main_window.getCurrentNodeEditorWidget()
            return current_widget
        except Exception:
            return None

    def get_logging_dock(self) -> Optional["LoggingDock"]:
        """Get the logging dock from the main window"""
        if not self._main_window:
            return None

        try:
            return self._main_window.getLoggingDock()
        except Exception:
            return None

    def log(
        self,
        level: str,
        message: str,
        design_window: Optional["TriggerSubWindow"] = None,
    ) -> None:
        """
        Log a message to the specified design window or the active one.

        Args:
            level: Log level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: The message to log
            design_window: Specific design window to log to (optional, uses active window if None)
        """
        try:
            # Use provided design window or get the active one
            target_window = design_window or self.get_active_design_window()

            if target_window and hasattr(target_window, "log"):
                # Log directly to the design window
                target_window.log(level, message)
            elif self._main_window:
                # Fallback: try to log directly to the logging dock
                logging_dock = self.get_logging_dock()
                if logging_dock:
                    # Get the current active window ID or use a default
                    active_window = self.get_active_design_window()
                    window_id = str(id(active_window)) if active_window else "global"
                    logging_dock.log(level, message, window_id)
                else:
                    # Final fallback: print to console
                    print(f"[GLOBAL-{level}] {message}")
            else:
                # No main window available, print to console
                print(f"[GLOBAL-{level}] {message}")

        except Exception as e:
            # Error in logging system, fallback to print
            print(f"[LOGGING-ERROR] Failed to log message '{message}': {e}")
            print(f"[FALLBACK-{level}] {message}")

    def trace(
        self, message: str, design_window: Optional["TriggerSubWindow"] = None
    ) -> None:
        """Log a TRACE message"""
        self.log("TRACE", message, design_window)

    def debug(
        self, message: str, design_window: Optional["TriggerSubWindow"] = None
    ) -> None:
        """Log a DEBUG message"""
        self.log("DEBUG", message, design_window)

    def info(
        self, message: str, design_window: Optional["TriggerSubWindow"] = None
    ) -> None:
        """Log an INFO message"""
        self.log("INFO", message, design_window)

    def warning(
        self, message: str, design_window: Optional["TriggerSubWindow"] = None
    ) -> None:
        """Log a WARNING message"""
        self.log("WARNING", message, design_window)

    def error(
        self, message: str, design_window: Optional["TriggerSubWindow"] = None
    ) -> None:
        """Log an ERROR message"""
        self.log("ERROR", message, design_window)

    def critical(
        self, message: str, design_window: Optional["TriggerSubWindow"] = None
    ) -> None:
        """Log a CRITICAL message"""
        self.log("CRITICAL", message, design_window)


# Global instance for easy access
_global_logger = GlobalLogger.get_instance()


def set_main_window(main_window: "TriggerWindow") -> None:
    """Set the main window for global logging"""
    _global_logger.set_main_window(main_window)


def log(
    level: str, message: str, design_window: Optional["TriggerSubWindow"] = None
) -> None:
    """
    Global log function - logs to the active design window or specified window.

    Args:
        level: Log level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: The message to log
        design_window: Specific design window to log to (optional)
    """
    _global_logger.log(level, message, design_window)


def trace(message: str, design_window: Optional["TriggerSubWindow"] = None) -> None:
    """Global TRACE logging function"""
    _global_logger.trace(message, design_window)


def debug(message: str, design_window: Optional["TriggerSubWindow"] = None) -> None:
    """Global DEBUG logging function"""
    _global_logger.debug(message, design_window)


def info(message: str, design_window: Optional["TriggerSubWindow"] = None) -> None:
    """Global INFO logging function"""
    _global_logger.info(message, design_window)


def warning(message: str, design_window: Optional["TriggerSubWindow"] = None) -> None:
    """Global WARNING logging function"""
    _global_logger.warning(message, design_window)


def error(message: str, design_window: Optional["TriggerSubWindow"] = None) -> None:
    """Global ERROR logging function"""
    _global_logger.error(message, design_window)


def critical(message: str, design_window: Optional["TriggerSubWindow"] = None) -> None:
    """Global CRITICAL logging function"""
    _global_logger.critical(message, design_window)


# Convenience aliases for shorter function names
log_trace = trace
log_debug = debug
log_info = info
log_warning = warning
log_error = error
log_critical = critical
