from typing import Optional
from loguru import logger
from qtpy.QtWidgets import (QApplication, QMainWindow, QTableView,
                            QVBoxLayout, QWidget, QPushButton, QCheckBox, QComboBox,
                            QStyledItemDelegate, QStyleOptionComboBox, QStyle, QAbstractItemView, QAbstractItemDelegate, QStyleOptionViewItem, QMenu)
from qtpy.QtCore import QAbstractTableModel, QVariant, QModelIndex, QEvent, QSortFilterProxyModel, QItemSelectionModel
from qtpy.QtCore import Qt, Signal, QVariant, QModelIndex
import pandas as pd


class RowData:
    def __init__(self, checked: bool, text: str, option: str, rename: str = ""):
        self.checked = checked
        self.text = text
        self.option = option  # Store the selected option string
        self.rename = rename


class SelectTableWidget(QAbstractTableModel):
    # Keep the default Qt signal
    dataChanged = Signal(QModelIndex, QModelIndex, list)
    data_processed = Signal(list)  # Add new signal for processed data

    # Add new signals for selection changes
    selectionChanged = Signal()
    moveRowRequested = Signal(int, int)

    def __init__(self, data: list, changes: dict, parent=None) -> None:
        super().__init__(parent)
        self._data = data
        self.filtered_rows = []  # For search functionality
        self.changes = changes or {
            'selected_columns': [],
            'rename_mapping': {},
            'dtype_mapping': {}
        }
        self._header_labels = ["", "Text Data", "Data Type", "Rename"]
        self._data_types = ['object', 'int64', 'float64', 'bool', 'datetime64']

        # self.initUI()
        # self.populateTable()
        # self.setupConnections()

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

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Return data for the given index and role."""
        # Return data based on role
        if not index.isValid():
            return QVariant()

        row = index.row()
        col = index.column()

        # Handle filtered rows
        if self.filtered_rows and row not in self.filtered_rows:
            return QVariant()

        row_data = self._data[row]

        if role == Qt.ItemDataRole.DisplayRole:
            # Display role for showing text
            if col == 1:
                return row_data.text
            elif col == 2:
                # For the combobox column, display the selected option
                return row_data.option
            elif col == 3:
                return row_data.rename
        elif role == Qt.ItemDataRole.CheckStateRole and col == 0:
            # Check state role for checkboxes (column 1)
            return Qt.CheckState.Checked if row_data.checked else Qt.CheckState.Unchecked
        elif role == Qt.ItemDataRole.EditRole:
            # Edit role for editing data (e.g., combobox selection)
            if col == 1:
                return row_data.text
            elif col == 2:
                # For the combobox column, return the currently selected option
                return row_data.option
            elif col == 3:
                return row_data.rename
        elif role == Qt.ItemDataRole.UserRole:
            # User role to potentially return the raw data object or specific values
            if col == 2:
                # Return the list of options for the combobox delegate
                return self._data_types

        return QVariant()

    # def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
    #     # Set data based on role (for editing)
    #     if not index.isValid():
    #         return False

    #     success = False
    #     row = index.row()
    #     col = index.column()
    #     row_data = self._data[row]

    #     if role == Qt.ItemDataRole.EditRole:
    #         # Handle editing for text and combobox
    #         if col == 1:
    #             row_data.text = str(value)
    #             success = True
    #         elif col == 2:
    #             # Handle combobox selection change
    #             if isinstance(value, str):
    #                 row_data.option = value
    #                 success = True

    #     elif role == Qt.ItemDataRole.CheckStateRole:
    #         # Handle checkbox state change (column 1)
    #         if col == 0:
    #             row_data.checked = (value == Qt.CheckState.Checked)
    #             success = True

    #     if success:
    #         self.dataChanged.emit(index, index, [role])
    #         # Emit processed data whenever data changes
    #         processed_data = self.getData()
    #         self.data_processed.emit(processed_data)
    #         return True

    #     return False

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False

        row = index.row()
        col = index.column()
        row_data = self._data[row]
        success = False

        if col == 0 and role == Qt.ItemDataRole.CheckStateRole:
            # Handle checkbox state change
            check_state = int(value)
            row_data.checked = (check_state == Qt.CheckState.Checked.value)
            print(
                f"Checkbox at row {row} set to {row_data.checked}, value: {check_state}")
            success = True
        elif role == Qt.ItemDataRole.EditRole:
            if col == 3:  # Rename column
                row_data.rename = str(value)
                success = True
            elif col == 2:  # Combobox column
                row_data.option = str(value)
                success = True

        if success:
            self.dataChanged.emit(index, index, [role])
            self.data_processed.emit(self.getData())
            return True

        return False

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        # Return header data
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self._header_labels[section]
            elif orientation == Qt.Orientation.Vertical:
                return str(section + 1)  # Row numbers
        return QVariant()

    def flags(self, index):
        # Define item flags (e.g., IsEditable, IsSelectable, IsUserCheckable)
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        default_flags = super().flags(
            index) | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        if index.column() == 0:
            # Checkbox column is checkable
            return default_flags | Qt.ItemFlag.ItemIsUserCheckable
        elif index.column() == 2:
            # Combobox column is editable (to allow delegate to work)
            return default_flags | Qt.ItemFlag.ItemIsEditable
        elif index.column() == 3:  # Rename column
            return default_flags | Qt.ItemFlag.ItemIsEditable

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
                    Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, Qt.ItemDataRole.CheckStateRole, Qt.ItemDataRole.UserRole])

                print(f"Swapped Row {row1 + 1} and Row {row2 + 1}")
                return True
            else:
                print("Failed to begin row move operation.")
                return False
        print("Invalid row indices for swapping.")
        return False

    def setupOptionsMenu(self, button: QPushButton) -> None:
        """Setup the options dropdown menu.

        Args:
            button (QPushButton): Button that will show the menu
        """
        menu = QMenu(button)

        # Selection actions
        select_all = menu.addAction("Select All")
        select_all.triggered.connect(self.selectAll)

        deselect_all = menu.addAction("Deselect All")
        deselect_all.triggered.connect(self.deselectAll)

        menu.addSeparator()

        # Sorting submenu
        sort_menu = menu.addMenu("Sort")

        sort_original = sort_menu.addAction("Original Order")
        sort_original.triggered.connect(lambda: self.sortColumns("original"))

        sort_name_asc = sort_menu.addAction("Name (A-Z)")
        sort_name_asc.triggered.connect(lambda: self.sortColumns("name_asc"))

        sort_name_desc = sort_menu.addAction("Name (Z-A)")
        sort_name_desc.triggered.connect(lambda: self.sortColumns("name_desc"))

        sort_type = sort_menu.addAction("By Type")
        sort_type.triggered.connect(lambda: self.sortColumns("type"))

        button.setMenu(menu)

    def setupConnections(self) -> None:
        """Setup all signal connections"""
        self.search_input.textChanged.connect(self.filterTable)
        self.up_btn.clicked.connect(lambda: self.moveSelectedRow("up"))
        self.down_btn.clicked.connect(lambda: self.moveSelectedRow("down"))

        # Connect to checkbox state changes
        for row in range(self.table.rowCount()):
            checkbox_container = self.table.cellWidget(row, 0)
            checkbox: QCheckBox = checkbox_container.layout().itemAt(0).widget()
            checkbox.stateChanged.connect(self.onDataChanged)

            # Connect to combobox changes
            combo_box: QComboBox = self.table.cellWidget(row, 2)
            combo_box.currentTextChanged.connect(self.onDataChanged)

            # Connect to rename field changes
            rename_item: QLineEdit = self.table.cellWidget(row, 3)
            rename_item.textChanged.connect(self.onDataChanged)

    def populateTable(self) -> None:
        data_types = ['object', 'int64', 'float64', 'bool', 'datetime64']
        row_count = len(self._data)
        # self.table.setRowCount(row_count)

        for i in range(row_count):
            self.table.insertRow(i)
            column_name = self._data[i]['column_name']

            # Create container widget for checkbox
            checkbox_container = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_container)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Checkbox for isSelected
            checkbox = QCheckBox()
            checkbox.setChecked(
                column_name in self.changes['selected_columns'])
            checkbox_layout.addWidget(checkbox)

            self.table.setCellWidget(i, 0, checkbox_container)

            # Column name (non-editable)
            column_name_item = QTableWidgetItem(column_name)
            column_name_item.setFlags(
                column_name_item.flags() ^ ~Qt.ItemIsEditable)
            print(f"Column name: {column_name} -----")
            print(column_name_item.text())
            self.table.setItem(i, 1, column_name_item)

            # Dropdown for data_type
            combo_box = QComboBox()
            combo_box.addItems(data_types)
            # Set saved dtype if exists, otherwise use original
            saved_dtype = self.changes['dtype_mapping'].get(column_name)
            current_dtype = saved_dtype if saved_dtype else str(
                self._data[i]['dtype'])
            combo_box.setCurrentText(current_dtype)
            self.table.setCellWidget(i, 2, combo_box)

            # Line edit for rename
            rename_item = QLineEdit()
            # Set saved rename if exists
            saved_rename = self.changes['rename_mapping'].get(column_name, "")
            rename_item.setText(saved_rename)
            self.table.setCellWidget(i, 3, rename_item)

    def onDataChanged(self) -> None:
        # Emit the updated data whenever changes occur
        data = self.getData()
        self._dataChanged.emit(data)

    def update_from_changes(self, changes: dict) -> None:
        """Update model state from changes dictionary"""
        for row in range(len(self._data)):
            row_data = self._data[row]
            # Update checked state
            row_data.checked = row_data.text in changes['selected_columns']
            # Update data type
            if row_data.text in changes['dtype_mapping']:
                row_data.option = changes['dtype_mapping'][row_data.text]
            # Update rename
            row_data.rename = changes['rename_mapping'].get(row_data.text, '')

        # Notify view that data has changed
        self.layoutChanged.emit()
        self.data_processed.emit(self.getData())

    def get_renamed_columns(self) -> dict:
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

    def selectAll(self) -> None:
        """Select all rows"""
        for row in range(len(self._data)):
            self._data[row].checked = True
            index = self.index(row, 0)
            self.dataChanged.emit(
                index, index, [Qt.ItemDataRole.CheckStateRole])
        self.data_processed.emit(self.getData())

    def deselectAll(self) -> None:
        """Deselect all rows"""
        for row in range(len(self._data)):
            self._data[row].checked = False
            index = self.index(row, 0)
            self.dataChanged.emit(
                index, index, [Qt.ItemDataRole.CheckStateRole])
        self.data_processed.emit(self.getData())

    def sortColumns(self, sort_type: str) -> None:
        """Sort columns based on specified criteria"""
        rows_data = []
        for row in range(self.table.rowCount()):
            column_name = self.table.item(row, 1).text()
            dtype = self.table.cellWidget(row, 2).currentText()
            rows_data.append((row, column_name, dtype))

        # Sort based on criteria
        if sort_type == "original":
            rows_data.sort(key=lambda x: x[0])
        elif sort_type == "name_asc":
            rows_data.sort(key=lambda x: x[1].lower())
        elif sort_type == "name_desc":
            rows_data.sort(key=lambda x: x[1].lower(), reverse=True)
        elif sort_type == "type":
            rows_data.sort(key=lambda x: x[2])

        # Reorder rows
        for new_idx, (old_idx, _, _) in enumerate(rows_data):
            if new_idx != old_idx:
                self.swapRows(new_idx, old_idx)

        self.onDataChanged()

    def onSelectAllChanged(self, state: int) -> None:
        """Handle select all checkbox changes"""
        for row in range(self.table.rowCount()):
            checkbox_container: Optional[QWidget] = self.table.cellWidget(
                row, 0)
            checkbox: Optional[QCheckBox] = checkbox_container.layout().itemAt(
                0).widget()
            checkbox.setChecked(bool(state))

        self.onDataChanged()

    def filterRows(self, text: str) -> None:
        """Filter rows based on search text"""
        search_text = text.lower()
        self.filtered_rows = []

        for row in range(len(self._data)):
            row_data = self._data[row]
            if (search_text in row_data.text.lower() or
                search_text in row_data.option.lower() or
                    (row_data.rename and search_text in row_data.rename.lower())):
                self.filtered_rows.append(row)

        # Notify view that data has changed
        self.layoutChanged.emit()

    # def filterTable(self, text: str) -> None:
    #     """Filter table rows based on search text"""
    #     search_text = text.lower()
    #     for row in range(self.table.rowCount()):
    #         matches = False
    #         # Search in column name, rename, and description
    #         # Column name, rename, description columns
    #         for col in range(self.table.columnCount()):
    #             print(f"Row: {row}, Column: {col}")
    #             widget = self.table.cellWidget(row, col)
    #             print(f"Widget type: {type(widget)}")
    #             cell_text = ""
    #             if widget:
    #                 # Print widget type(widget)
    #                 if isinstance(widget, QCheckBox):
    #                     print("Checkbox found")
    #                     cell_text = widget.text()
    #                 elif isinstance(widget, QLineEdit):
    #                     print("LineEdit found")
    #                     cell_text = widget.text()
    #                 # else:
    #                 #     cell_text = widget.text()
    #                 print(f"Searching in {cell_text}")
    #                 # Check if search text is in cell text
    #                 if search_text in cell_text.lower():
    #                     matches = True
    #                     break
    #         self.table.setRowHidden(row, not matches)

    def moveRow(self, source_row: int, target_row: int) -> bool:
        """Move a row from source to target position

        Args:
            source_row (int): Current row index
            target_row (int): Target row index
        """
        if not (0 <= source_row < len(self._data) and 0 <= target_row < len(self._data)):
            return False

        # Adjust target position for moving down
        destination_row = target_row + 1 if source_row < target_row else target_row

        # Use beginMoveRows to handle the move
        if self.beginMoveRows(QModelIndex(), source_row, source_row,
                              QModelIndex(), destination_row):
            # Actually move the data
            item = self._data.pop(source_row)
            self._data.insert(target_row, item)
            self.endMoveRows()
            self.data_processed.emit(self.getData())
            return True
        return False

    def moveSelectedRow(self, direction: str, view: QTableView = None) -> None:
        """Move selected row up or down

        Args:
            direction (str): "up" or "down"
            view (QTableView, optional): The table view. Defaults to None.
        """
        logger.debug(f"Moving row {direction}")

        if not view:
            logger.debug("No table view provided")
            return

        # Get current row from the view
        current_index = view.selectionModel().currentIndex()
        if not current_index.isValid():
            logger.debug("No row selected")
            return

        # Get the source model index if using proxy model
        source_index = current_index
        if isinstance(view.model(), QSortFilterProxyModel):
            source_index = view.model().mapToSource(current_index)

        current_row = source_index.row()
        target_row = current_row - 1 if direction == "up" else current_row + 1

        if 0 <= target_row < len(self._data):
            # Move the row
            if self.moveRow(current_row, target_row):
                # Update selection to follow the moved row
                new_index = self.index(target_row, current_index.column())
                if isinstance(view.model(), QSortFilterProxyModel):
                    new_index = view.model().mapFromSource(new_index)
                view.setCurrentIndex(new_index)
                view.selectionModel().select(
                    new_index, QItemSelectionModel.Select | QItemSelectionModel.Rows)

    def onColumnMoved(self, logicalIndex: int, oldVisualIndex: int, newVisualIndex: int) -> None:
        """Handle column reordering"""
        self.onDataChanged()

    def getData(self) -> list:
        data = []
        for row in range(self.rowCount()):
            row_data = self._data[row]
            if row_data.checked:
                data.append((row_data.text, row_data.option, row_data.rename))
        return data
    # for row in range(self.table.rowCount()):
    #     # Get checkbox from container
    #     checkbox_container = self.table.cellWidget(row, 0)
    #     checkbox = checkbox_container.layout().itemAt(0).widget()
    #     is_selected = checkbox.isChecked()
    #     # is_selected = self.table.cellWidget(row, 0).isChecked()
    #     if is_selected:
    #         column_name = self.table.item(row, 1).text()
    #         data_type = self.table.cellWidget(row, 2).currentText()
    #         rename = self.table.cellWidget(row, 3).text()
    #         data.append((column_name, data_type, rename))
    # return data


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
        if not index.isValid():
            return super().paint(painter, option, index)

        # Get the value from the model
        value = index.data(Qt.ItemDataRole.DisplayRole)

        # Create style option for combo box
        opt = QStyleOptionComboBox()
        opt.rect = option.rect
        opt.state = option.state

        # Convert QVariant to string if needed
        if isinstance(value, QVariant):
            value = value.toString() if value.isValid() else ""
        else:
            value = str(value)

        opt.currentText = value

        # Draw the combo box
        if option.widget:
            style = option.widget.style()
        else:
            style = QApplication.style()

        style.drawComplexControl(
            QStyle.ComplexControl.CC_ComboBox, opt, painter)
        style.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opt, painter)

    # def paint(self, painter, option, index):
    #     # Paint the item (including the combobox appearance)

    #     if not index.isValid():
    #         return super().paint(painter, option, index)

    #     # Use the QStyleOptionViewItem to handle the painting
    #     # This is important for proper rendering of the item
    #     if index.column() == 2:
    #         # super().paint(painter, option, index)
    #         # Get the current value from the model
    #         value = index.model().data(index, Qt.DisplayRole)
    #         options = index.model().data(index, Qt.UserRole)  # Get options list

    #         # --- IMPROVED PAINTING ---``
    #         # Draw the item's background and state (e.g., selection highlight)
    #         # option.initFrom(option.widget)
    #         if option.state & QStyle.StateFlag.State_Selected:
    #             painter.fillRect(option.rect, option.palette.highlight())
    #             painter.setPen(option.palette.highlightedText().color())
    #         else:
    #             painter.fillRect(option.rect, option.palette.base())
    #             painter.setPen(option.palette.text().color())

    #         # Create a style option for a combobox
    #         opt = QStyleOptionComboBox()
    #         opt.rect = option.rect  # Set the rectangle for painting
    #         opt.state = option.state  # Inherit state (selected, enabled, etc.)
    #         opt.currentText = value  # Set the current text to display

    #         # Set the list of items in the style option (needed for size hints/painting)
    #         if options:
    #             opt.currentValue = value
    #             try:
    #                 opt.currentIndex = options.index(value)
    #             except ValueError:
    #                 opt.currentIndex = -1  # Value not found in options

    #         # Draw the combobox using the style
    #         QApplication.style().drawComplexControl(
    #             QStyle.ComplexControl.CC_ComboBox, opt, painter)
    #         # QApplication.style().drawControl(
    #         #     QStyle.ControlElement.CE_ComboBoxLabel, opt, painter)
    #         super().paint(painter, option, index)

    #     else:
    #         # For other columns, use the default painting
    #         super().paint(painter, option, index)

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItems(['object', 'int64', 'float64', 'bool', 'datetime64'])
        return editor

    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.DisplayRole)
        if isinstance(value, QVariant):
            value = value.toString() if value.isValid() else ""
        else:
            value = str(value)
        editor.setCurrentText(value)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

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
