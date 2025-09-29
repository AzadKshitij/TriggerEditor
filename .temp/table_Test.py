import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTableView,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QCheckBox,
    QComboBox,
    QStyledItemDelegate,
    QStyleOptionComboBox,
    QStyle,
    QAbstractItemView,
    QAbstractItemDelegate,
    QStyleOptionViewItem,
)
from PyQt6.QtCore import Qt, QVariant, QModelIndex, QEvent
from PyQt6.QtGui import QPainter

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
        # Available options for the dropdown
        self._options = ["Option A", "Option B", "Option C"]

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
                return self._options

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
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
                return True
            elif col == 2:
                # Handle combobox selection change
                if isinstance(value, str):
                    row_data.option = value
                    self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
                    return True
            return False
        elif role == Qt.CheckStateRole:
            # Handle checkbox state change (column 1)
            if col == 1:
                row_data.checked = value == Qt.Checked
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
            return (
                default_flags
                | Qt.ItemIsEditable
                | Qt.ItemIsSelectable
                | Qt.ItemIsEnabled
            )
        elif index.column() == 1:
            # Checkbox column is checkable, selectable, and enabled
            return (
                default_flags
                | Qt.ItemIsUserCheckable
                | Qt.ItemIsSelectable
                | Qt.ItemIsEnabled
            )
        elif index.column() == 2:
            # Combobox column is editable, selectable, and enabled
            # | Qt.ItemIsSelectable
            return (
                default_flags
                | Qt.ItemIsUserCheckable
                | Qt.ItemIsEditable
                | Qt.ItemIsEnabled
                | Qt.ItemIsSelectable
            )

        return default_flags

    def swapRows(self, row1, row2):
        # Method to swap rows in the model
        if 0 <= row1 < len(self._data) and 0 <= row2 < len(self._data):
            # Determine source and destination rows for the signal
            source_row = row1
            destination_row = row2

            # If moving a row to an earlier position, the destination index needs adjustment
            if row1 < row2:
                destination_row = (
                    row2 + 1
                )  # Signal moving row1 to the position *after* row2

            # Notify the view that rows are about to move
            if self.beginMoveRows(
                QModelIndex(), source_row, source_row, QModelIndex(), destination_row
            ):
                # Perform the data swap in the model's internal list
                self._data[row1], self._data[row2] = self._data[row2], self._data[row1]
                # End the move operation
                self.endMoveRows()

                # Although begin/endMoveRows should handle the visual update,
                # sometimes explicitly signaling data changed for the affected rows
                # can help ensure all delegates refresh correctly.
                top_left = self.index(min(row1, row2), 0)
                bottom_right = self.index(max(row1, row2), self.columnCount() - 1)
                self.dataChanged.emit(
                    top_left,
                    bottom_right,
                    [Qt.DisplayRole, Qt.EditRole, Qt.CheckStateRole, Qt.UserRole],
                )

                print(f"Swapped Row {row1 + 1} and Row {row2 + 1}")
                return True
            else:
                print("Failed to begin row move operation.")
                return False
        print("Invalid row indices for swapping.")
        return False


# Custom delegate for the ComboBox column


# Custom delegate for the ComboBox column
class ComboBoxDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        # Create the editor widget (a QComboBox)
        if index.column() == 2:  # Apply only to the 'Option' column
            editor = QComboBox(parent)
            # Get the list of options from the model using Qt.UserRole
            options = index.model().data(index, Qt.UserRole)
            if options:
                editor.addItems(options)
            editor.setAutoFillBackground(True)  # Helps with painting
            return editor
        # Use default editor for other columns
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor, index):
        # Set the editor's data from the model
        if index.column() == 2:
            current_value = index.model().data(index, Qt.EditRole)
            editor.setCurrentText(current_value)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        # Get data from the editor and set it in the model
        if index.column() == 2:
            model.setData(index, editor.currentText(), Qt.EditRole)
        else:
            super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index):
        # Set the geometry of the editor
        if index.column() == 2:
            editor.setGeometry(option.rect)
        else:
            super().updateEditorGeometry(editor, option, index)

    def paint(self, painter, option, index):
        # Paint the item (including the combobox appearance)
        # Use the QStyleOptionViewItem to handle the painting
        # This is important for proper rendering of the item
        if index.column() == 2:
            # super().paint(painter, option, index)
            # Get the current value from the model
            value = index.model().data(index, Qt.DisplayRole)
            options = index.model().data(index, Qt.UserRole)  # Get options list

            # --- IMPROVED PAINTING ---``
            # Draw the item's background and state (e.g., selection highlight)
            # option.initFrom(option.widget)
            if option.state & QStyle.StateFlag.State_Selected:
                painter.fillRect(option.rect, option.palette.highlight())
                painter.setPen(option.palette.highlightedText().color())
            else:
                painter.fillRect(option.rect, option.palette.base())
                painter.setPen(option.palette.text().color())

            # Create a style option for a combobox
            opt = QStyleOptionComboBox()
            opt.rect = option.rect  # Set the rectangle for painting
            opt.state = option.state  # Inherit state (selected, enabled, etc.)
            opt.currentText = value  # Set the current text to display

            # Set the list of items in the style option (needed for size hints/painting)
            if options:
                opt.currentValue = value
                try:
                    opt.currentIndex = options.index(value)
                except ValueError:
                    opt.currentIndex = -1  # Value not found in options

            # Draw the combobox using the style
            QApplication.style().drawComplexControl(
                QStyle.ComplexControl.CC_ComboBox, opt, painter
            )
            # QApplication.style().drawControl(
            #     QStyle.ControlElement.CE_ComboBoxLabel, opt, painter)
            super().paint(painter, option, index)

        else:
            # For other columns, use the default painting
            super().paint(painter, option, index)

    # def paint(self, painter, option, index):
    #     # Paint the item (including the combobox appearance)
    #     if index.column() == 2:
    #         # Get the current value from the model
    #         value = index.model().data(index, Qt.DisplayRole)
    #         options = index.model().data(index, Qt.UserRole)  # Get options list

    #         # Create a style option for a combobox
    #         opt = QStyleOptionComboBox()
    #         opt.rect = option.rect  # Set the rectangle for painting
    #         opt.state = option.state  # Inherit state (selected, enabled, etc.)
    #         opt.currentText = value  # Set the current text to display

    #         # Set the list of items in the style option (needed for size hints/painting)
    #         if options:
    #             # Although QStyleOptionComboBox doesn't have addItems,
    #             # setting the current value and index helps the style draw correctly.
    #             opt.currentValue = value
    #             try:
    #                 opt.currentIndex = options.index(value)
    #             except ValueError:
    #                 opt.currentIndex = -1  # Value not found in options

    #         # Draw the combobox using the style
    #         QApplication.style().drawComplexControl(
    #             QStyle.ComplexControl.CC_ComboBox, opt, painter)
    #         QApplication.style().drawControl(
    #             QStyle.ControlElement.CE_ComboBoxLabel, opt, painter)

    #     else:
    #         # For other columns, use the default painting
    #         super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        # Handle events within the cell, even when not in edit mode
        if index.column() == 2:  # Only for the 'Option' column
            if event.type() == QEvent.MouseButtonPress:
                # If it's a left mouse button press
                if event.button() == Qt.LeftButton:
                    # Tell the view to start editing this index
                    view = option.widget  # The view is available as the option's widget
                    if isinstance(view, QAbstractItemView):
                        view.edit(index)
                        return True  # Event handled

        # For other events or columns, let the base class handle it
        return super().editorEvent(event, model, option, index)


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

        # Set the custom delegate for the 'Option' column (index 2)
        self.tableView.setItemDelegateForColumn(2, ComboBoxDelegate(self.tableView))

        # Auto-resize columns to fit content
        self.tableView.resizeColumnsToContents()
        self.tableView.setEditTriggers(
            QTableView.EditTrigger.DoubleClicked | QTableView.EditTrigger.EditKeyPressed
        )

        # Set delegates for specific columns if needed (e.g., for combobox editor)
        # The default delegate handles checkboxes and text editing.
        # For a combobox editor, you might need a custom delegate if the default isn't sufficient
        # based on the data role (Qt.EditRole and Qt.UserRole are used here to help a delegate).
        # However, for basic display and interaction, the default delegate often works
        # with the correct data roles implemented in the model.

        # Auto-resize columns to fit content
        self.tableView.resizeColumnsToContents()

        self.swap_button = QPushButton("Swap Row 3 and Row 7 (Model Indices 2 and 6)")
        # Connect the button to the model's swap method
        self.swap_button.clicked.connect(
            lambda: self.model.swapRows(2, 6)
        )  # Swap row indices 2 and 6

        layout = QVBoxLayout()
        layout.addWidget(self.tableView)
        layout.addWidget(self.swap_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # You can then call this method, for example, from a button click or another action
        # For instance, add another button to print the data
        # In __init__ after creating swap_button:
        self.get_data_button = QPushButton("Get Table Data")
        self.get_data_button.clicked.connect(self.print_table_data)
        layout.addWidget(self.get_data_button)  # Add to layout

        # Auto-resize columns to fit content
        self.tableView.resizeColumnsToContents()

    # Add a new slot to print the data
    def print_table_data(self):
        data = self.get_table_data()
        if data:
            print("Table Data:")
            for row in data:
                print(row)
        else:
            print("Could not retrieve table data.")

    # Add this method to your MainWindow class

    def get_table_data(self):
        """Retrieves all data from the table model."""
        all_data = []
        # Access the model instance
        model = self.tableView.model()
        if isinstance(model, CustomTableModel):
            # Iterate through the internal data list of the model
            for row_data in model._data:
                # Append the data for each row to the list
                all_data.append(
                    {
                        "text": row_data.text,
                        "checked": row_data.checked,
                        "option": row_data.option,
                    }
                )
            return all_data
        return None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
