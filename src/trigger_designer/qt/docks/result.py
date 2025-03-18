import copy
from pprint import pp
from shutil import copy2
from qtpy.QtWidgets import QVBoxLayout, QLabel, QWidget, QLayout, QPushButton, QHBoxLayout, QTextEdit, QDockWidget
from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QPixmap, QIcon, QDrag, QPainter, QColor, QFont, QCursor, QMouseEvent

from utils.logger import Logger


class ResultDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logs = []
        self.filtered_logs = []
        self.current_filter = 'all'
        self.logger: Logger = None
        self.initUI()

    def initUI(self):
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

    def add_log(self, message, log_type='info'):
        log_entry = {'message': message, 'type': log_type}
        self.logs.append(log_entry)
        self.update_log_area()

    def clear_logs(self):
        self.logs = []
        self.update_log_area()

    def filter_logs(self, log_type):
        self.current_filter = log_type
        self.update_log_area()

    def update_log_area(self):
        self.log_area.clear()
        self.filtered_logs = [log for log in self.logs if self.current_filter ==
                              'all' or log['type'] == self.current_filter]
        for log in self.filtered_logs:
            self.log_area.append(f"[{log['type'].upper()}] {log['message']}")
