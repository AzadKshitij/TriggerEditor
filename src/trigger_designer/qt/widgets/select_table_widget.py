from qtpy.QtWidgets import QTableWidget, QTableWidgetItem, QCheckBox, QComboBox, QLineEdit, QVBoxLayout, QWidget, QHeaderView
from qtpy.QtCore import Qt, Signal
import pandas as pd


class SelectTableWidget(QWidget):
    dataChanged = Signal(list)

    def __init__(self, parent=None, data=None, changes=None):
        super().__init__(parent)
        self.data = data
        self.changes = changes or {
            'selected_columns': [],
            'rename_mapping': {},
            'dtype_mapping': {}
        }
        self.initUI()
        self.setupConnections()

    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(self)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Status", "Column Name", "Data Type", "Rename"])
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
        row_count = len(self.data)

        for i in range(row_count):
            self.table.insertRow(i)
            column_name = self.data[i]['column_name']

            # Checkbox for isSelected
            checkbox = QCheckBox()
            checkbox.setChecked(
                column_name in self.changes['selected_columns'])
            self.table.setCellWidget(i, 0, checkbox)

            # Column name (non-editable)
            column_name_item = QTableWidgetItem(column_name)
            column_name_item.setFlags(
                column_name_item.flags() ^ ~Qt.ItemIsEditable)
            self.table.setItem(i, 1, column_name_item)

            # Dropdown for data_type
            combo_box = QComboBox()
            combo_box.addItems(data_types)
            # Set saved dtype if exists, otherwise use original
            saved_dtype = self.changes['dtype_mapping'].get(column_name)
            current_dtype = saved_dtype if saved_dtype else str(
                self.data[i]['dtype'])
            combo_box.setCurrentText(current_dtype)
            self.table.setCellWidget(i, 2, combo_box)

            # Line edit for rename
            rename_item = QLineEdit()
            # Set saved rename if exists
            saved_rename = self.changes['rename_mapping'].get(column_name, "")
            rename_item.setText(saved_rename)
            self.table.setCellWidget(i, 3, rename_item)

    def onDataChanged(self):
        # Emit the updated data whenever changes occur
        data = self.getData()
        self.dataChanged.emit(data)

    def update_from_changes(self, changes):
        """Update table state from changes dictionary"""
        for row in range(self.table.rowCount()):
            # Changed from 0 to 1 for column name
            column_name = self.table.item(row, 1).text()

            # Update selection checkbox
            # Changed from 1 to 0 for checkbox
            checkbox = self.table.cellWidget(row, 0)
            checkbox.setChecked(column_name in changes['selected_columns'])

            # Update data type combobox
            dtype_combo = self.table.cellWidget(row, 2)
            if column_name in changes['dtype_mapping']:
                index = dtype_combo.findText(
                    changes['dtype_mapping'][column_name])
                if index >= 0:
                    dtype_combo.setCurrentIndex(index)

            # Update rename field
            rename_edit = self.table.cellWidget(row, 3)
            new_name = changes['rename_mapping'].get(column_name, '')
            rename_edit.setText(new_name)

    def get_renamed_columns(self):
        """Extract renamed columns from the table widget."""
        rename_dict = {}

        for row in range(self.table.rowCount()):  # Changed from table_widget to table
            original_name = self.table.item(row, 1).text()
            rename_edit = self.table.cellWidget(row, 3)

            if rename_edit:  # Check if rename widget exists
                new_name = rename_edit.text().strip()
                if new_name and new_name != original_name:
                    # Store rename mapping
                    rename_dict[original_name] = new_name

        return rename_dict

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
