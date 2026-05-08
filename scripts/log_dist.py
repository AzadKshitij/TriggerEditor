import sys
import os
import datetime


def setup_logging():
    log_dir = os.path.join(os.path.dirname(sys.executable), "logs")
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"app_{timestamp}.log")

    # Redirect stdout and stderr to the log file
    sys.stdout = open(log_file, "w", encoding="utf-8")
    sys.stderr = sys.stdout


setup_logging()
