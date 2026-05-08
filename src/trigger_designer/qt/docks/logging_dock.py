from __future__ import annotations

import datetime
from qtpy.QtWidgets import (
    QDockWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QTextEdit,
    QPushButton,
    QComboBox,
    QLabel,
    QCheckBox,
    QLineEdit,
)
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QFont, QTextCursor
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from trigger_designer.qt.design_window import TriggerSubWindow


class LogLevel:
    """Log level constants with colors"""

    TRACE = {"name": "TRACE", "color": "#808080"}  # Gray
    DEBUG = {"name": "DEBUG", "color": "#00AA00"}  # Green
    INFO = {"name": "INFO", "color": "#0066CC"}  # Blue
    WARNING = {"name": "WARNING", "color": "#FF8800"}  # Orange
    ERROR = {"name": "ERROR", "color": "#CC0000"}  # Red
    CRITICAL = {"name": "CRITICAL", "color": "#800080"}  # Purple

    ALL_LEVELS = [TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL]


class LogEntry:
    """Represents a single log entry"""

    def __init__(
        self, level: str, message: str, timestamp: Optional[datetime.datetime] = None
    ):
        self.level = level
        self.message = message
        self.timestamp = timestamp or datetime.datetime.now()

    def to_html(self) -> str:
        """Convert log entry to HTML format"""
        level_info = next(
            (l for l in LogLevel.ALL_LEVELS if l["name"] == self.level), LogLevel.INFO
        )
        timestamp_str = self.timestamp.strftime("%H:%M:%S.%f")[
            :-3
        ]  # Remove microseconds, keep milliseconds

        return (
            f'<div style="margin: 2px 0;">'
            f'<span style="color: #666; font-family: monospace;">[{timestamp_str}]</span> '
            f'<span style="color: {level_info["color"]}; font-weight: bold;">{self.level}</span>: '
            f'<span style="color: #88929f;">{self.message}</span>'
            f"</div>"
        )


class LoggingDock(QDockWidget):
    """Logging dock widget that displays logs for the currently active design window"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Logs", parent)

        # Store logs per design window ID
        self.logs_per_window: dict[str, list[LogEntry]] = {}
        self.current_design_window_id: Optional[str] = None
        self.filtered_logs: list[LogEntry] = []
        self.current_filter_level = "TRACE"
        self.filter_text = ""
        self.auto_scroll = True
        self.max_logs = 1000  # Maximum number of logs to keep in memory per window

        self.initUI()
        self.setupAutoUpdate()

    def initUI(self) -> None:
        """Initialize the user interface"""
        self.dock_widget = QWidget()
        self.dock_widget.setObjectName("LoggingDockWidget")
        self.dock_widget.setMinimumWidth(400)
        self.dock_widget.setMinimumHeight(200)

        # Main layout
        main_layout = QVBoxLayout()

        # Controls layout
        controls_layout = QHBoxLayout()

        # Log level filter
        controls_layout.addWidget(QLabel("Level:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems([level["name"] for level in LogLevel.ALL_LEVELS])
        self.level_combo.setCurrentText("TRACE")
        self.level_combo.currentTextChanged.connect(self.on_level_filter_changed)
        controls_layout.addWidget(self.level_combo)

        # Text filter
        controls_layout.addWidget(QLabel("Filter:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter messages...")
        self.filter_input.textChanged.connect(self.on_text_filter_changed)
        controls_layout.addWidget(self.filter_input)

        # Auto-scroll checkbox
        self.auto_scroll_checkbox = QCheckBox("Auto-scroll")
        self.auto_scroll_checkbox.setChecked(True)
        self.auto_scroll_checkbox.toggled.connect(self.on_auto_scroll_changed)
        controls_layout.addWidget(self.auto_scroll_checkbox)

        # Clear button
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_logs)
        controls_layout.addWidget(clear_button)

        main_layout.addLayout(controls_layout)

        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 9))  # Monospace font
        self.log_display.setHtml("")
        main_layout.addWidget(self.log_display)

        self.dock_widget.setLayout(main_layout)
        self.setWidget(self.dock_widget)

        # Dock widget features
        self.setFloating(False)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

    def setupAutoUpdate(self) -> None:
        """Setup timer for auto-updating the display"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh_display)
        self.update_timer.start(100)  # Update every 100ms

    def log(
        self, level: str, message: str, design_window_id: Optional[str] = None
    ) -> None:
        """Add a log entry for a specific design window"""
        if design_window_id is None:
            design_window_id = self.current_design_window_id

        if design_window_id is None:
            return  # No active design window

        entry = LogEntry(level.upper(), message)

        # Initialize logs for this window if needed
        if design_window_id not in self.logs_per_window:
            self.logs_per_window[design_window_id] = []

        self.logs_per_window[design_window_id].append(entry)

        # Limit the number of logs to prevent memory issues
        if len(self.logs_per_window[design_window_id]) > self.max_logs:
            self.logs_per_window[design_window_id] = self.logs_per_window[
                design_window_id
            ][-self.max_logs :]

        # Only apply filters if this is the current active window
        if design_window_id == self.current_design_window_id:
            self.apply_filters()

    def apply_filters(self) -> None:
        """Apply current filters to the logs of the current active window"""
        # Get logs for current window
        current_logs = []
        if (
            self.current_design_window_id
            and self.current_design_window_id in self.logs_per_window
        ):
            current_logs = self.logs_per_window[self.current_design_window_id]

        # Get level priority for filtering
        level_priorities = {
            level["name"]: i for i, level in enumerate(LogLevel.ALL_LEVELS)
        }
        current_priority = level_priorities.get(self.current_filter_level, 0)

        self.filtered_logs = []
        for log_entry in current_logs:
            # Level filter
            entry_priority = level_priorities.get(log_entry.level, 0)
            if entry_priority < current_priority:
                continue

            # Text filter
            if (
                self.filter_text
                and self.filter_text.lower() not in log_entry.message.lower()
            ):
                continue

            self.filtered_logs.append(log_entry)

    def refresh_display(self) -> None:
        """Refresh the log display"""
        if not hasattr(self, "last_log_count"):
            self.last_log_count = 0

        # Check if we need to update (new logs or count changed)
        current_log_count = len(self.filtered_logs)
        if current_log_count == self.last_log_count:
            return

        # Store current scroll position
        scrollbar = self.log_display.verticalScrollBar()
        was_at_bottom = scrollbar.value() == scrollbar.maximum()

        # Generate HTML for all filtered logs
        if current_log_count == 0:
            # Clear display if no logs
            self.log_display.clear()
        else:
            html_content = ""
            for log_entry in self.filtered_logs:
                html_content += log_entry.to_html()

            self.log_display.setHtml(html_content)

            # Restore scroll position or auto-scroll
            if self.auto_scroll and (was_at_bottom or self.last_log_count == 0):
                scrollbar.setValue(scrollbar.maximum())

        self.last_log_count = current_log_count

    def on_level_filter_changed(self, level: str) -> None:
        """Handle log level filter change"""
        self.current_filter_level = level
        self.apply_filters()

    def on_text_filter_changed(self, text: str) -> None:
        """Handle text filter change"""
        self.filter_text = text
        self.apply_filters()

    def on_auto_scroll_changed(self, checked: bool) -> None:
        """Handle auto-scroll checkbox change"""
        self.auto_scroll = checked

    def clear_logs(self) -> None:
        """Clear logs for the current active window"""
        if (
            self.current_design_window_id
            and self.current_design_window_id in self.logs_per_window
        ):
            self.logs_per_window[self.current_design_window_id].clear()
        self.filtered_logs.clear()
        self.log_display.clear()
        self.last_log_count = 0

    def switch_to_design_window(self, design_window: "TriggerSubWindow") -> None:
        """Switch the logging dock to show logs for a specific design window"""
        design_window_id = str(id(design_window))
        self.current_design_window_id = design_window_id

        # Update title
        window_title = design_window.windowTitle() or f"Window {design_window_id}"
        self.setWindowTitle(f"Logs - {window_title}")

        # Initialize logs for this window if needed
        if design_window_id not in self.logs_per_window:
            self.logs_per_window[design_window_id] = []

        # Apply filters to show logs for this window
        self.apply_filters()
        self.last_log_count = 0  # Force refresh

        # If this window has no logs, clear the display immediately
        if not self.logs_per_window[design_window_id]:
            self.log_display.clear()

    def remove_design_window(self, design_window_id: str) -> None:
        """Remove logs for a design window that has been closed"""
        if design_window_id in self.logs_per_window:
            del self.logs_per_window[design_window_id]

        # If this was the current window, clear the display
        if self.current_design_window_id == design_window_id:
            self.current_design_window_id = None
            self.filtered_logs.clear()
            self.log_display.clear()
            self.setWindowTitle("Logs")
            self.last_log_count = 0

    # Convenience methods for different log levels
    def trace(self, message: str, design_window_id: Optional[str] = None) -> None:
        """Log a TRACE message"""
        self.log("TRACE", message, design_window_id)

    def debug(self, message: str, design_window_id: Optional[str] = None) -> None:
        """Log a DEBUG message"""
        self.log("DEBUG", message, design_window_id)

    def info(self, message: str, design_window_id: Optional[str] = None) -> None:
        """Log an INFO message"""
        self.log("INFO", message, design_window_id)

    def warning(self, message: str, design_window_id: Optional[str] = None) -> None:
        """Log a WARNING message"""
        self.log("WARNING", message, design_window_id)

    def error(self, message: str, design_window_id: Optional[str] = None) -> None:
        """Log an ERROR message"""
        self.log("ERROR", message, design_window_id)

    def critical(self, message: str, design_window_id: Optional[str] = None) -> None:
        """Log a CRITICAL message"""
        self.log("CRITICAL", message, design_window_id)
