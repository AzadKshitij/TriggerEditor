from qtpy.QtWidgets import QTableWidget, QTableWidgetItem, QCheckBox, QComboBox, QLineEdit, QVBoxLayout, QWidget, QHeaderView
from qtpy.QtCore import Qt, Signal
import pandas as pd


class TableWidget(QWidget):
    dataChanged = Signal(list)

    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        # self.incoming_columns = incoming_columns
        # self.old_columns = old_columns
        self.data = data
        print(data)
        self.initUI()
        self.setupConnections()

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

    def setupConnections(self):
        # Connect to checkbox state changes
        for row in range(self.table.rowCount()):
            checkbox: QCheckBox = self.table.cellWidget(row, 0)
            checkbox.stateChanged.connect(self.onDataChanged)

            # Connect to combobox changes
            combo_box: QComboBox = self.table.cellWidget(row, 2)
            combo_box.currentTextChanged.connect(self.onDataChanged)

            # Connect to rename field changes
            rename_item: QLineEdit = self.table.cellWidget(row, 3)
            rename_item.textChanged.connect(self.onDataChanged)

    def populateTable(self):
        data_types = ['object', 'int64', 'float64', 'bool', 'datetime64']
        # row_count = len(self.incoming_columns) if self.incoming_columns else len(
        #     self.old_columns)
        row_count = len(self.data)

        for i in range(row_count):
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
            rename_item = QLineEdit("")
            self.table.setCellWidget(i, 3, rename_item)

    def onDataChanged(self):
        # Emit the updated data whenever changes occur
        data = self.getData()
        self.dataChanged.emit(data)

    def getData(self):
        data = []
        for row in range(self.table.rowCount()):
            is_selected = self.table.cellWidget(row, 0).isChecked()
            if is_selected:
                column_name = self.table.item(row, 1).text()
                data_type = self.table.cellWidget(row, 2).currentText()
                rename = self.table.cellWidget(row, 3).text()
                data.append((column_name, data_type, rename))
        return data

    def get_renamed_columns(self):
        """Extract renamed columns from the table widget."""
        rename_dict = {}

        for row in range(self.table_widget.rowCount()):
            original_name = self.table_widget.item(row, 1).text()
            new_name_item = self.table_widget.item(row, 3)

            if new_name_item:  # Check if user entered a rename value
                new_name = new_name_item.text().strip()
                if new_name and new_name != original_name:
                    # Store rename mapping
                    rename_dict[original_name] = new_name

        return rename_dict
