from loguru import logger
import queue
import threading
import time
from enum import StrEnum


class LogLevel(StrEnum):
    SUCCESS = "TSUCCESS"
    ENGINE = "ENGINE"
    INFO = "TINFO"
    WARNING = "TWARNING"
    ERROR = "TERROR"
    CONVERSION = "CONVERSIONERROR"


# Define your custom log levels
logger.level(LogLevel.SUCCESS, 65, color="<green>", icon="✅")
logger.level(LogLevel.ENGINE, 15, color="<magenta>")
logger.level(LogLevel.INFO, 25, color="<blue>")
logger.level(LogLevel.WARNING, 35, color="<yellow>")
logger.level(LogLevel.ERROR, 45, color="<red>")
logger.level(LogLevel.CONVERSION, 55, color="<red><bold>")

log_queue: queue.Queue = queue.Queue()


def custom_log_sink(message):
    log_queue.put(message.record)


logger.add(custom_log_sink, format="{message}")


def log_viewer_thread():
    while True:
        try:
            log_record = log_queue.get(timeout=1)
            print(
                "🐍 File: TriggerEditor/test_log_sink.py | Line: 32 | log_viewer_thread ~ log_record", log_record)
            # print([f"{k}:{v}" for k, v in log_record.items()])

            print(
                f"Custom Viewer: {log_record['level'].name} - {log_record['message']}")
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error in log viewer thread: {e}")
            break


viewer_thread = threading.Thread(target=log_viewer_thread, daemon=True)
viewer_thread.start()

logger.log(LogLevel.SUCCESS, "This is a success message")
time.sleep(0.2)
logger.log(LogLevel.ENGINE, "This is an engine message")
time.sleep(0.2)
logger.log(LogLevel.INFO, "This is an info message")
time.sleep(0.2)
logger.log(LogLevel.WARNING, "This is a warning message")
time.sleep(0.2)
logger.log(LogLevel.ERROR, "This is an error message")
time.sleep(0.2)
logger.log(LogLevel.CONVERSION, "This is a conversion error message")
time.sleep(0.2)


time.sleep(2)
