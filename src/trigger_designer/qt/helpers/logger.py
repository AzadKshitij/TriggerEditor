from typing import TYPE_CHECKING
from enum import StrEnum
from loguru import logger
import queue
import threading
import time

import loguru


if TYPE_CHECKING:
    from trigger_designer.qt.docks.result import ResultDock


class LogLevel(StrEnum):
    SUCCESS = "TSUCCESS"
    ENGINE = "ENGINE"
    INFO = "TINFO"
    WARNING = "TWARNING"
    ERROR = "TERROR"
    CONVERSION = "CONVERSIONERROR"


class Logger:
    def __init__(self) -> None:
        self.logs: list[dict] = list()
        self.result_dock: 'ResultDock'
        self.log_queue: queue.Queue[loguru.Record] = queue.Queue()
        self.add_log_levels()
        logger.add(self.custom_log_sink, format="{message}")

    def start_logging(self):
        self.viewer_thread = threading.Thread(
            target=self.log_viewer_thread, daemon=True)
        self.viewer_thread.start()

    def custom_log_sink(self, message: 'loguru.Message') -> None:
        """ Custom sink function to update the log viewer UI """
        # self.log_queue.put(message.record)
        self.log(message.record['message'], message.record['level'].name)

    def set_result_dock(self, result_dock: 'ResultDock') -> None:
        self.result_dock = result_dock

    def log(self, message: str, log_type: str = 'info') -> None:
        if self.result_dock:
            self.result_dock.add_log(message, log_type)

    def get_logs(self):
        return "\n".join([f"[{log['type'].upper()}] {log['message']}" for log in self.logs])

    def clear_logs(self) -> None:
        self.logs = []
        if self.result_dock:
            self.result_dock.clear_logs()

    def add_log_levels(self):

        # Define your custom log levels
        logger.level(LogLevel.SUCCESS, 65, color="<green>", icon="✅")
        logger.level(LogLevel.ENGINE, 15, color="<magenta>")
        logger.level(LogLevel.INFO, 25, color="<blue>")
        logger.level(LogLevel.WARNING, 35, color="<yellow>")
        logger.level(LogLevel.ERROR, 45, color="<red>")
        logger.level(LogLevel.CONVERSION, 55, color="<red><bold>")

    def log_viewer_thread(self):

        while True:
            try:
                log_record = self.log_queue.get(timeout=1)
                if not self.result_dock:
                    print(
                        f"Custom Viewer: {log_record['level'].name} - {log_record['message']}")
                else:
                    self.result_dock.add_log(
                        log_record['message'], {log_record['level'].name})
            except queue.Empty:
                pass
            except Exception as e:
                print(f"Error in log viewer thread: {e}")
                break
