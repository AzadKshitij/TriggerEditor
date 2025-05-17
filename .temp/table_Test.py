import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableView,
                             QVBoxLayout, QWidget, QPushButton, QCheckBox, QComboBox)
from PyQt6.QtCore import Qt, QVariant, QModelIndex

from qtpy.QtCore import QAbstractTableModel
# Define a custom data structure for each row


class RowData:
    def __init__(self, text, checked, option):
        self.text = text
        self.checked = checked
        self.option = option  # Store the selected option string


class CustomTableModel(QAbstractTableModel):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self._data = data
        self._header_labels = ["Text Data", "Is Checked", "Option"]

    def rowCount(self, parent=QModelIndex()):
        # Return the number of rows in the model
        if parent.isValid():
            return 0
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        # Return the number of columns in the model
        if parent.isValid():
            return 0
        return len(self._header_labels)

    def data(self, index, role=Qt.DisplayRole):
        # Return data based on role
        if not index.isValid():
            return QVariant()

        row = index.row()
        col = index.column()
        row_data = self._data[row]

        if role == Qt.DisplayRole:
            # Display role for showing text
            if col == 0:
                return row_data.text
            elif col == 2:
                # For the combobox column, display the selected option
                return row_data.option
            return QVariant()  # Return empty QVariant for other columns in DisplayRole
        elif role == Qt.CheckStateRole:
            # Check state role for checkboxes (column 1)
            if col == 1:
                return Qt.Checked if row_data.checked else Qt.Unchecked
            return QVariant()
        elif role == Qt.EditRole:
            # Edit role for editing data (e.g., combobox selection)
            if col == 0:
                return row_data.text
            elif col == 2:
                # For the combobox column, return the currently selected option
                return row_data.option
            return QVariant()
        elif role == Qt.UserRole:
            # User role to potentially return the raw data object or specific values
            if col == 2:
                # Return the list of options for the combobox delegate
                return ["Option A", "Option B", "Option C"]

        return QVariant()

    def setData(self, index, value, role=Qt.EditRole):
        # Set data based on role (for editing)
        if not index.isValid():
            return False

        row = index.row()
        col = index.column()
        row_data = self._data[row]

        if role == Qt.EditRole:
            # Handle editing for text and combobox
            if col == 0:
                row_data.text = str(value)
                self.dataChanged.emit(
                    index, index, [Qt.DisplayRole, Qt.EditRole])
                return True
            elif col == 2:
                # Handle combobox selection change
                if isinstance(value, str):
                    row_data.option = value
                    self.dataChanged.emit(
                        index, index, [Qt.DisplayRole, Qt.EditRole])
                    return True
            return False
        elif role == Qt.CheckStateRole:
            # Handle checkbox state change (column 1)
            if col == 1:
                row_data.checked = (value == Qt.Checked)
                self.dataChanged.emit(index, index, [Qt.CheckStateRole])
                return True
            return False

        return False

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        # Return header data
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return self._header_labels[section]
            elif orientation == Qt.Vertical:
                return str(section + 1)  # Row numbers
        return QVariant()

    def flags(self, index):
        # Define item flags (e.g., IsEditable, IsSelectable, IsUserCheckable)
        if not index.isValid():
            return Qt.NoItemFlags

        default_flags = super().flags(index)

        if index.column() == 0:
            # Text column is editable
            return default_flags | Qt.ItemIsEditable
        elif index.column() == 1:
            # Checkbox column is checkable
            return default_flags | Qt.ItemIsUserCheckable
        elif index.column() == 2:
            # Combobox column is editable (to allow delegate to work)
            return default_flags | Qt.ItemIsEditable

        return default_flags

    def swapRows(self, row1, row2):
        # Method to swap rows in the model
        if 0 <= row1 < len(self._data) and 0 <= row2 < len(self._data):
            # Determine source and destination rows for the signal
            source_row = row1
            destination_row = row2

            # If moving a row to an earlier position, the destination index needs adjustment
            if row1 < row2:
                destination_row = row2 + 1  # Signal moving row1 to the position *after* row2

            # Notify the view that rows are about to move
            if self.beginMoveRows(QModelIndex(), source_row, source_row, QModelIndex(), destination_row):
                # Perform the data swap in the model's internal list
                self._data[row1], self._data[row2] = self._data[row2], self._data[row1]
                # End the move operation
                self.endMoveRows()

                # Although begin/endMoveRows should handle the visual update,
                # sometimes explicitly signaling data changed for the affected rows
                # can help ensure all delegates refresh correctly.
                top_left = self.index(min(row1, row2), 0)
                bottom_right = self.index(
                    max(row1, row2), self.columnCount() - 1)
                self.dataChanged.emit(top_left, bottom_right, [
                    Qt.DisplayRole, Qt.EditRole, Qt.CheckStateRole, Qt.UserRole])

                print(f"Swapped Row {row1 + 1} and Row {row2 + 1}")
                return True
            else:
                print("Failed to begin row move operation.")
                return False
        print("Invalid row indices for swapping.")
        return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Model/View Table Swap Example")
        self.setGeometry(100, 100, 700, 400)

        # Create some sample data
        sample_data = [
            RowData("Apple", True, "Option A"),
            RowData("Banana", False, "Option B"),
            RowData("Cherry", True, "Option C"),
            RowData("Date", False, "Option A"),
            RowData("Elderberry", True, "Option B"),
            RowData("Fig", False, "Option C"),
            RowData("Grape", True, "Option A"),
            RowData("Honeydew", False, "Option B"),
            RowData("Kiwi", True, "Option C"),
            RowData("Lemon", False, "Option A"),
        ]

        # Create the custom model and set the data
        self.model = CustomTableModel(sample_data)

        # Create the table view and set the model
        self.tableView = QTableView()
        self.tableView.setModel(self.model)

        # Set delegates for specific columns if needed (e.g., for combobox editor)
        # The default delegate handles checkboxes and text editing.
        # For a combobox editor, you might need a custom delegate if the default isn't sufficient
        # based on the data role (Qt.EditRole and Qt.UserRole are used here to help a delegate).
        # However, for basic display and interaction, the default delegate often works
        # with the correct data roles implemented in the model.

        self.swap_button = QPushButton(
            "Swap Row 3 and Row 7 (Model Indices 2 and 6)")
        # Connect the button to the model's swap method
        self.swap_button.clicked.connect(
            lambda: self.model.swapRows(2, 6))  # Swap row indices 2 and 6

        layout = QVBoxLayout()
        layout.addWidget(self.tableView)
        layout.addWidget(self.swap_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Auto-resize columns to fit content
        self.tableView.resizeColumnsToContents()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
