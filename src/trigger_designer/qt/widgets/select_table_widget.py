from typing import Optional
from qtpy.QtWidgets import QTableWidget, QTableWidgetItem, QCheckBox, QComboBox, QLineEdit, QVBoxLayout, QWidget, QHeaderView, QHBoxLayout, QToolButton, QMenu, QLabel
from qtpy.QtCore import Qt, Signal
import pandas as pd


class SelectTableWidget(QWidget):
    dataChanged = Signal(list)

    def __init__(self, parent: QWidget, data: list, changes: dict) -> None:
        super().__init__(parent)
        self.data = data
        self.filtered_rows = []  # For search functionality
        self.changes = changes or {
            'selected_columns': [],
            'rename_mapping': {},
            'dtype_mapping': {}
        }
        self.initUI()
        self.populateTable()
        self.setupConnections()

    def initUI(self) -> None:

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)

        # Create toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(5, 0, 5, 0)
        toolbar.setSpacing(5)

        # Options dropdown
        self.options_btn = QToolButton()
        self.options_btn.setText("Options")
        self.options_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.options_btn.setToolTip("Options")
        toolbar.addWidget(self.options_btn)
        self.setupOptionsMenu()

        # Up/Down buttons
        self.up_btn = QToolButton()
        self.up_btn.setText("↑")
        self.up_btn.setToolTip("Move selected row up")
        self.down_btn = QToolButton()
        self.down_btn.setText("↓")
        self.down_btn.setToolTip("Move selected row down")

        toolbar.addWidget(self.up_btn)
        toolbar.addWidget(self.down_btn)

        # Search field (right-aligned)
        toolbar.addStretch()
        search_layout = QHBoxLayout()
        # search_icon = QLabel("🔍")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search columns...")
        # self.search_input.setMaximumWidth(200)
        # search_layout.addWidget(search_icon)
        search_layout.addWidget(self.search_input)
        toolbar.addLayout(search_layout)

        main_layout.addLayout(toolbar)

        # self.v_layout = QVBoxLayout(self)
        # self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.table: QTableWidget = QTableWidget(self)

        # Enable drag-drop reordering
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDragDropMode(QTableWidget.DragDrop)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        # Enable column reordering
        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)
        header.sectionMoved.connect(self.onColumnMoved)

        # Add select all checkbox in header
        self.select_all = QCheckBox()
        self.select_all.stateChanged.connect(self.onSelectAllChanged)
        header.setCornerWidget(self.select_all)

        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Status", "Column Name", "Data Type", "Rename"])
        main_layout.addWidget(self.table)
        self.setLayout(main_layout)

    def setupOptionsMenu(self) -> None:
        """Setup the options dropdown menu"""
        menu = QMenu(self)

        # Column operations with connected actions
        select_all_action = menu.addAction("Select All")
        select_all_action.triggered.connect(self.selectAll)

        deselect_all_action = menu.addAction("Deselect All")
        deselect_all_action.triggered.connect(self.deselectAll)

        menu.addSeparator()

        # Sort options submenu
        sort_menu = menu.addMenu("Sort Columns")

        original_action = sort_menu.addAction("Original Order")
        original_action.triggered.connect(lambda: self.sortColumns("original"))

        name_asc_action = sort_menu.addAction("Name (A-Z)")
        name_asc_action.triggered.connect(lambda: self.sortColumns("name_asc"))

        name_desc_action = sort_menu.addAction("Name (Z-A)")
        name_desc_action.triggered.connect(
            lambda: self.sortColumns("name_desc"))

        type_action = sort_menu.addAction("Type")
        type_action.triggered.connect(lambda: self.sortColumns("type"))

        self.options_btn.setMenu(menu)

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
        row_count = len(self.data)
        # self.table.setRowCount(row_count)

        for i in range(row_count):
            self.table.insertRow(i)
            column_name = self.data[i]['column_name']

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
                self.data[i]['dtype'])
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
        self.dataChanged.emit(data)

    def update_from_changes(self, changes: dict) -> None:
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

    # Add these methods after the existing ones
    def selectAll(self) -> None:
        """Select all columns"""
        self.select_all.setChecked(True)
        for row in range(self.table.rowCount()):
            checkbox_container = self.table.cellWidget(row, 0)
            checkbox = checkbox_container.layout().itemAt(0).widget()
            checkbox.setChecked(True)
        self.onDataChanged()

    def deselectAll(self) -> None:
        """Deselect all columns"""
        self.select_all.setChecked(False)
        for row in range(self.table.rowCount()):
            checkbox_container = self.table.cellWidget(row, 0)
            checkbox = checkbox_container.layout().itemAt(0).widget()
            checkbox.setChecked(False)
        self.onDataChanged()

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

    def filterTable(self, text: str) -> None:
        """Filter table rows based on search text"""
        search_text = text.lower()
        for row in range(self.table.rowCount()):
            matches = False
            # Search in column name, rename, and description
            # Column name, rename, description columns
            for col in range(self.table.columnCount()):
                print(f"Row: {row}, Column: {col}")
                widget = self.table.cellWidget(row, col)
                print(f"Widget type: {type(widget)}")
                cell_text = ""
                if widget:
                    # Print widget type(widget)
                    if isinstance(widget, QCheckBox):
                        print("Checkbox found")
                        cell_text = widget.text()
                    elif isinstance(widget, QLineEdit):
                        print("LineEdit found")
                        cell_text = widget.text()
                    # else:
                    #     cell_text = widget.text()
                    print(f"Searching in {cell_text}")
                    # Check if search text is in cell text
                    if search_text in cell_text.lower():
                        matches = True
                        break
            self.table.setRowHidden(row, not matches)

    def moveSelectedRow(self, direction: str) -> None:
        """Move selected row up or down"""
        current_row = self.table.currentRow()
        if current_row < 0:
            return

        target_row = current_row - 1 if direction == "up" else current_row + 1
        if 0 <= target_row < self.table.rowCount():
            # Save widgets from both rows
            self.swapRows(current_row, target_row)
            self.table.setCurrentCell(target_row, 0)
            # self.onDataChanged()

    # def swapRows(self, row1: int, row2: int) -> None:
    #     """Swap all widgets and items between two rows"""

    #     if not (0 <= row1 < self.table.rowCount() and 0 <= row2 < self.table.rowCount()):
    #         return  # Invalid row indices

    #     # Create a temporary list to store items of row1
    #     row1_items = []
    #     for col in range(self.table.columnCount()):
    #         item = self.table.item(row1, col)
    #         if item:
    #             row1_items.append(item)
    #         else:
    #             row1_items.append(None)

    #     # Clear row1
    #     for col in range(self.table.columnCount()):
    #         self.table.setItem(row1, col, None)

    #     # Move row2 to row1
    #     for col in range(self.table.columnCount()):
    #         item = self.table.item(row2, col)
    #         self.table.setItem(row1, col, item)

    #     # Clear row2
    #     for col in range(self.table.columnCount()):
    #         self.table.setItem(row2, col, None)

    #     # Move stored row1 items to row2
    #     for col in range(self.table.columnCount()):
    #         self.table.setItem(row2, col, row1_items[col])

    #     # for col in range(self.table.columnCount()):
    #     #     # Swap widgets if they exist
    #     #     widget1 = self.table.cellWidget(row1, col)
    #     #     widget2 = self.table.cellWidget(row2, col)
    #     #     if widget1 and widget2:
    #     #         self.table.setCellWidget(row1, col, widget2)
    #     #         self.table.setCellWidget(row2, col, widget1)
    #     #     # Swap items if they exist
    #     #     item1 = self.table.item(row1, col)
    #     #     item2 = self.table.item(row2, col)
    #     #     if item1 and item2:
    #     #         temp = self.table.takeItem(row1, col)
    #     #         self.table.setItem(row1, col, self.table.takeItem(row2, col))
    #     #         self.table.setItem(row2, col, temp)

    def swapRows(self, row1, row2):
        """Swaps the content and widgets of two specified rows."""
        if 0 <= row1 < self.table.rowCount() and 0 <= row2 < self.table.rowCount():
            for col in range(self.table.columnCount()):
                # --- Handle QTableWidgetItem ---
                item1 = self.table.takeItem(
                    row1, col)  # Takes the QTableWidgetItem
                item2 = self.table.takeItem(
                    row2, col)  # Takes the QTableWidgetItem

                # Sets the QTableWidgetItem
                self.table.setItem(row1, col, item2)
                # Sets the QTableWidgetItem
                self.table.setItem(row2, col, item1)

                # --- Handle Cell Widget ---
                # Get the widgets before removing them
                widget1 = self.table.cellWidget(
                    row1, col)  # Gets the cell widget
                widget2 = self.table.cellWidget(
                    row2, col)  # Gets the cell widget

                # Remove widgets from their original positions
                self.table.removeCellWidget(
                    row1, col)  # Removes the cell widget
                self.table.removeCellWidget(
                    row2, col)  # Removes the cell widget

                # Set widgets in the swapped positions
                if widget1:
                    self.table.setCellWidget(
                        row2, col, widget1)  # Sets the cell widget
                if widget2:
                    self.table.setCellWidget(
                        row1, col, widget2)  # Sets the cell widget

    def onColumnMoved(self, logicalIndex: int, oldVisualIndex: int, newVisualIndex: int) -> None:
        """Handle column reordering"""
        self.onDataChanged()

    def getData(self) -> list:
        data = []
        for row in range(self.table.rowCount()):
            # Get checkbox from container
            checkbox_container = self.table.cellWidget(row, 0)
            checkbox = checkbox_container.layout().itemAt(0).widget()
            is_selected = checkbox.isChecked()
            # is_selected = self.table.cellWidget(row, 0).isChecked()
            if is_selected:
                column_name = self.table.item(row, 1).text()
                data_type = self.table.cellWidget(row, 2).currentText()
                rename = self.table.cellWidget(row, 3).text()
                data.append((column_name, data_type, rename))
        return data
