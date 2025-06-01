from qtpy.QtWidgets import QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from qtpy.QtCore import Qt
import pandas as pd
import numpy as np


class DataPreviewWindow(QMainWindow):
    def __init__(self, data, title="Data Preview", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 600)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create table widget
        self.table = QTableWidget()
        layout.addWidget(self.table)

        # Display the data
        self.display_data(data)

    def display_data(self, data):
        if isinstance(data, pd.DataFrame):
            self.display_dataframe(data)
        elif isinstance(data, (list, tuple)):
            self.display_list(data)
        elif isinstance(data, dict):
            self.display_dict(data)
        else:
            self.display_simple_value(data)

    def display_dataframe(self, df):
        # Set up the table
        self.table.setRowCount(len(df.index))
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels(df.columns)

        # Fill the table
        for row in range(len(df.index)):
            for col in range(len(df.columns)):
                value = df.iloc[row, col]
                item = QTableWidgetItem(str(value))
                # Make read-only
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)

        # Adjust column widths
        self.table.resizeColumnsToContents()

    def display_list(self, data):
        self.table.setRowCount(len(data))
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Value"])

        for row, value in enumerate(data):
            item = QTableWidgetItem(str(value))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item)

    def display_dict(self, data):
        self.table.setRowCount(len(data))
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Key", "Value"])

        for row, (key, value) in enumerate(data.items()):
            key_item = QTableWidgetItem(str(key))
            value_item = QTableWidgetItem(str(value))
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            value_item.setFlags(value_item.flags() & ~
                                Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, key_item)
            self.table.setItem(row, 1, value_item)

    def display_simple_value(self, value):
        self.table.setRowCount(1)
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Value"])

        item = QTableWidgetItem(str(value))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(0, 0, item)
