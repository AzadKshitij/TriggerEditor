from qtpy.QtWidgets import QVBoxLayout, QLabel, QWidget, QLayout, QPushButton, QHBoxLayout, QTextEdit, QDockWidget, QTableWidget, QTableWidgetItem
from qtpy.QtCore import QSize, Qt, QDateTime, QRectF, QPointF
from qtpy.QtGui import QPixmap, QIcon, QDrag, QPainter, QColor, QFont, QCursor, QMouseEvent

from trigger_designer.qt.helpers.logger import Logger
from trigger_designer.qt.helpers.signal_handler import SignalHandler
from typing import Dict, List, Optional


class ResultDock(QDockWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.logs: Dict[str, List[dict]] = {}
        self.filtered_logs: list[dict] = []
        self.current_filter = 'all'
        self.current_design_window_id = None
        self.logger: Logger
        SignalHandler.instance().sub_window_activated.connect(self.update_log_area)
        # Connect to the global signal

        self.initUI()

    def initUI(self) -> None:
        self.dock_widget = QWidget()
        self.dock_layout = QVBoxLayout()

        # Create top bar with filter buttons
        self.top_bar = QHBoxLayout()
        self.all_button = QPushButton('All (0)')
        self.error_button = QPushButton('Errors (0)')
        self.warning_button = QPushButton('Warnings (0)')
        self.info_button = QPushButton('Info (0)')

        self.all_button.clicked.connect(lambda: self.filter_logs('all'))
        self.error_button.clicked.connect(lambda: self.filter_logs('error'))
        self.warning_button.clicked.connect(
            lambda: self.filter_logs('warning'))
        self.info_button.clicked.connect(lambda: self.filter_logs('info'))

        self.top_bar.addWidget(self.all_button)
        self.top_bar.addWidget(self.error_button)
        self.top_bar.addWidget(self.warning_button)
        self.top_bar.addWidget(self.info_button)

        self.dock_layout.addLayout(self.top_bar)

        # Create table for logs
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(3)
        self.log_table.setHorizontalHeaderLabels(
            ['Timestamp', 'Type', 'Message'])
        self.log_table.horizontalHeader().setStretchLastSection(True)  # type: ignore
        self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.log_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.log_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection)
        self.dock_layout.addWidget(self.log_table)

        # Add action buttons
        self.action_bar = QHBoxLayout()
        self.last_run_button = QPushButton('Last Run')
        self.config_button = QPushButton('Configuration')
        self.action_bar.addWidget(self.last_run_button)
        self.action_bar.addWidget(self.config_button)
        self.dock_layout.addLayout(self.action_bar)

        self.dock_widget.setLayout(self.dock_layout)
        self.setWidget(self.dock_widget)
        self.setFloating(False)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                         QDockWidget.DockWidgetFeature.DockWidgetFloatable)

    def add_log(self, design_window_id: str, message: str, log_type: str = 'info') -> None:
        """Add a log entry to the log viewer."""
        if design_window_id not in self.logs:
            self.logs[design_window_id] = []

        log_entry = {
            'timestamp': QDateTime.currentDateTime().toString('yyyy-MM-dd HH:mm:ss'),
            'type': log_type,
            'message': message
        }
        self.logs[design_window_id].append(log_entry)

        print("🐍 File: docks/result.py:71 | initUI ~ design_window_id",
              design_window_id)
        # Update the log area if this is the active design window
        if design_window_id == self.current_design_window_id:
            self.update_log_area(design_window_id)

    def clear_logs(self) -> None:
        self.logs = {}
        self.update_log_area()

    def filter_logs(self, log_type: str) -> None:
        self.current_filter = log_type
        self.update_log_area()

    # update this to match new log format
    def update_log_area(self, design_window_id: str) -> None:
        print("🐍 File: docks/result.py:71 | initUI ~ design_window_id",
              design_window_id)
        if design_window_id not in self.logs:
            self.logs[design_window_id] = []

        self.log_table.setRowCount(0)
        self.filtered_logs = []

        # for design_window_id, logs in self.logs.items():
        for log in self.logs[design_window_id]:
            if self.current_filter == 'all' or log['type'] == self.current_filter:
                self.filtered_logs.append(log)

        # self.filtered_logs = [log for log in self.logs if self.current_filter ==
        #                       'all' or log['type'] == self.current_filter]

        for log in self.filtered_logs:
            row_position = self.log_table.rowCount()
            self.log_table.insertRow(row_position)
            self.log_table.setItem(
                row_position, 0, QTableWidgetItem(log['timestamp']))
            self.log_table.setItem(
                row_position, 1, QTableWidgetItem(log['type'].capitalize()))
            self.log_table.setItem(
                row_position, 2, QTableWidgetItem(log['message']))

        # for log in self.filtered_logs:
        #     row_position = self.log_table.rowCount()
        #     self.log_table.insertRow(row_position)
        #     self.log_table.setItem(
        #         row_position, 0, QTableWidgetItem(log['timestamp']))
        #     self.log_table.setItem(
        #         row_position, 1, QTableWidgetItem(log['type'].capitalize()))
        #     self.log_table.setItem(
        #         row_position, 2, QTableWidgetItem(log['message']))

        # Update button labels with counts
        # self.all_button.setText(f"All ({len(self.logs)})")
        # self.error_button.setText(
        #     f"Errors ({len([log for log in self.logs if log['type'] == 'error'])})")
        # self.warning_button.setText(
        #     f"Warnings ({len([log for log in self.logs if log['type'] == 'warning'])})")
        # self.info_button.setText(
        #     f"Info ({len([log for log in self.logs if log['type'] == 'info'])})")
