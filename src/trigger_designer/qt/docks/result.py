from qtpy.QtWidgets import QVBoxLayout, QLabel, QWidget, QLayout, QPushButton, QHBoxLayout, QTextEdit, QDockWidget
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QPixmap, QIcon, QDrag, QPainter, QColor, QFont, QCursor, QMouseEvent

from trigger_designer.qt.helpers.logger import Logger
from typing import Optional


class ResultDock(QDockWidget):
    def __init__(self, parent: Optional[QWidget]=None) -> None:
        super().__init__(parent)
        self.logs: list[dict] = []
        self.filtered_logs: list[dict] = []
        self.current_filter = 'all'
        self.logger: Logger
        self.initUI()

    def initUI(self) -> None:
        self.dock_widget = QWidget()
        self.dock_layout = QVBoxLayout()

        # Create top bar with buttons
        self.top_bar = QHBoxLayout()
        self.all_button = QPushButton('All')
        self.warning_button = QPushButton('Warning')
        self.error_button = QPushButton('Error')
        self.debug_button = QPushButton('Debug')

        self.all_button.clicked.connect(lambda: self.filter_logs('all'))
        self.warning_button.clicked.connect(
            lambda: self.filter_logs('warning'))
        self.error_button.clicked.connect(lambda: self.filter_logs('error'))
        self.debug_button.clicked.connect(lambda: self.filter_logs('debug'))

        self.top_bar.addWidget(self.all_button)
        self.top_bar.addWidget(self.warning_button)
        self.top_bar.addWidget(self.error_button)
        self.top_bar.addWidget(self.debug_button)

        self.dock_layout.addLayout(self.top_bar)

        # Create text area for logs
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.dock_layout.addWidget(self.log_area)

        self.dock_widget.setLayout(self.dock_layout)
        self.setWidget(self.dock_widget)
        self.setFloating(False)
        self.setFeatures(QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)

    def add_log(self, message, log_type: str='info') -> None:
        log_entry = {'message': message, 'type': log_type}
        self.logs.append(log_entry)
        self.update_log_area()

    def clear_logs(self) -> None:
        self.logs = []
        self.update_log_area()

    def filter_logs(self, log_type) -> None:
        self.current_filter = log_type
        self.update_log_area()

    def update_log_area(self) -> None:
        self.log_area.clear()
        self.filtered_logs = [log for log in self.logs if self.current_filter ==
                              'all' or log['type'] == self.current_filter]
        for log in self.filtered_logs:
            self.log_area.append(f"[{log['type'].upper()}] {log['message']}")
