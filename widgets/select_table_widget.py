from qtpy.QtWidgets import QTableWidget, QTableWidgetItem, QCheckBox, QComboBox, QVBoxLayout, QWidget, QHeaderView
from qtpy.QtCore import Qt
import pandas as pd


class TableWidget(QWidget):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        # self.incoming_columns = incoming_columns
        # self.old_columns = old_columns
        self.data = data
        print(data)
        self.initUI()

    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Status", "Column Name", "Data Type", "Rename"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.layout.addWidget(self.table)
        self.setLayout(self.layout)
        self.populateTable()

    def populateTable(self):
        data_types = ['object', 'int64', 'float64', 'bool', 'datetime64']
        # row_count = len(self.incoming_columns) if self.incoming_columns else len(
        #     self.old_columns)
        row_count = len(self.data)

        for i in range(row_count):  # Example: 5 rows
            self.table.insertRow(i)

            # Checkbox for isSelected
            checkbox = QCheckBox()
            self.table.setCellWidget(i, 0, checkbox)

            # Editable line edit for column_name
            column_name_item = QTableWidgetItem(self.data[i]['column_name'])
            column_name_item.setFlags(
                column_name_item.flags() ^ ~Qt.ItemIsEditable)
            self.table.setItem(i, 1, column_name_item)

            # Dropdown for data_type
            combo_box = QComboBox()
            combo_box.addItems(data_types)
            combo_box.setCurrentText(str(self.data[i]['dtype']))
            self.table.setCellWidget(i, 2, combo_box)

            # Line edit for rename
            rename_item = QTableWidgetItem("")
            self.table.setItem(i, 3, rename_item)

    def getData(self):
        data = []
        for row in range(self.table.rowCount()):
            is_selected = self.table.cellWidget(row, 0).isChecked()
            column_name = self.table.item(row, 1).text()
            data_type = self.table.cellWidget(row, 2).currentText()
            rename = self.table.item(row, 3).text()
            data.append((is_selected, column_name, data_type, rename))
        return data
