from typing import TYPE_CHECKING, Dict, List, Optional
from enum import StrEnum
from loguru import logger
import queue
import threading
import time

import loguru


if TYPE_CHECKING:
    from trigger_designer.qt.docks.result import ResultDock
    from trigger_designer.qt.design_window import TriggerSubWindow


class LogLevel(StrEnum):
    SUCCESS = "TSUCCESS"
    ENGINE = "ENGINE"
    INFO = "TINFO"
    WARNING = "TWARNING"
    ERROR = "TERROR"
    CONVERSION = "CONVERSIONERROR"


class Logger:
    _log_levels_added = False
    # _thread_local = threading.local()

    def __init__(self, parent: "TriggerSubWindow") -> None:
        self.logs: Dict[str, List[dict]] = {}
        self.design_window_id: Optional[str] = "global"
        # self.result_dock: 'ResultDock' = parent.result_dock
        self.ensure_log_levels()
        logger.add(self.custom_log_sink, format="{message}")

    @classmethod
    def ensure_log_levels(cls):
        """Ensure custom log levels are added only once."""
        if not cls._log_levels_added:
            cls.add_log_levels()
            cls._log_levels_added = True

    def set_context(self, design_window_id: str) -> None:
        """Set the current design_window context."""
        logger.info(f"Setting context to design_window_id: {design_window_id}")
        self.design_window_id = design_window_id

    def clear_context(self) -> None:
        """Clear the current design_window context."""
        self.design_window_id = None

    # @classmethod
    # def get_context(cls) -> str:
    #     """Get the current design_window context."""
    #     return getattr(cls._thread_local, "design_window_id", "global")

    def custom_log_sink(self, message: "loguru.Message") -> None:
        """Custom sink function to update the log viewer UI"""
        # self.log_queue.put(message.record)
        # self.log(message.record['message'], message.record['level'].name)
        if not self.design_window_id == "global":
            self.log(
                self.design_window_id,
                message.record["message"],
                message.record["level"].name,
            )

    def set_result_dock(self, result_dock: "ResultDock", desing_window_id: str) -> None:
        self.result_dock = result_dock
        self.result_dock.current_design_window_id = desing_window_id

    def log(self, design_window_id: str, message: str, log_type: str) -> None:
        """Log a message for a specific design_window."""
        print(f"Logging message: {message} for design_window_id: {design_window_id}")
        # logger.warning(
        #     f"Logging message: {message} for design_window_id: {design_window_id}")
        if design_window_id not in self.logs:
            self.logs[design_window_id] = []
        self.logs[design_window_id].append({"message": message, "type": log_type})
        # if self.result_dock:
        self.result_dock.add_log(design_window_id, message, log_type)

    def get_logs(self):
        return "\n".join(
            [f"[{log['type'].upper()}] {log['message']}" for log in self.logs]
        )

    def clear_logs(self) -> None:
        self.logs = []
        if self.result_dock:
            self.result_dock.clear_logs()

    @staticmethod
    def add_log_levels():
        """Define custom log levels."""
        try:
            logger.level(LogLevel.SUCCESS, 65, color="<green>", icon="✅")
            logger.level(LogLevel.ENGINE, 15, color="<magenta>")
            logger.level(LogLevel.INFO, 25, color="<blue>")
            logger.level(LogLevel.WARNING, 35, color="<yellow>")
            logger.level(LogLevel.ERROR, 45, color="<red>")
            logger.level(LogLevel.CONVERSION, 55, color="<red><bold>")
        except ValueError as e:
            # Log levels already exist, ignore the error
            print(f"Log levels already defined: {e}")

    def log_viewer_thread(self):

        while True:
            try:
                log_record = self.log_queue.get(timeout=1)
                if not self.result_dock:
                    print(
                        f"Custom Viewer: {log_record['level'].name} - {log_record['message']}"
                    )
                else:
                    self.result_dock.add_log(
                        log_record["message"], {log_record["level"].name}
                    )
            except queue.Empty:
                pass
            except Exception as e:
                print(f"Error in log viewer thread: {e}")
                break
