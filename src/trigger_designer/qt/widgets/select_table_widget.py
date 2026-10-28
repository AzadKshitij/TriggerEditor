import dataclasses
from loguru import logger
from qtpy.QtGui import QColor, QPalette, QPainter, QPen
from qtpy.QtWidgets import (
    QTableView,
    QComboBox,
    QStyledItemDelegate,
    QStyleOptionComboBox,
    QStyle,
    QAbstractItemView,
)
from qtpy.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QEvent,
    QSortFilterProxyModel,
    QItemSelectionModel,
)
from qtpy.QtCore import Qt, Signal

from trigger_designer.qt.resource_manager import ResourceManager


@dataclasses.dataclass
class RowData:
    checked: bool = dataclasses.field(default=False)
    text: str = ""
    dtype: str = "object"
    rename: str = ""
    is_missing: bool = False
    date_format: str = ""


class SelectTableWidget(QAbstractTableModel):
    #: Dtype options offered by the Data Type column. Public so the dock can
    #: size that column to its longest label instead of shipping a guessed
    #: width that clips "Categorical" or wastes air on "List".
    DATA_TYPES = (
        "String",
        "Int64",
        "Float64",
        "Boolean",
        "Date",
        "Datetime",
        "List",
        "Struct",
        "Categorical",
        "Binary",
        "Decimal",
        "Duration",
    )

    # Keep the default Qt signal
    dataChanged = Signal(QModelIndex, QModelIndex, list)
    data_processed = Signal(list)  # Add new signal for processed data

    def __init__(self, data: list, changes: dict, parent=None) -> None:
        super().__init__(parent)
        self._data = data
        self.changes = changes or {
            "selected_columns": [],
            "rename_mapping": {},
            "dtype_mapping": {},
        }
        self._header_labels = ["", "Column", "Data Type", "Rename"]
        self._data_types = list(self.DATA_TYPES)

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
            return None

        row = index.row()
        col = index.column()

        row_data: RowData = self._data[row]

        if role == Qt.ItemDataRole.DisplayRole:
            # Display role for showing text
            if col == 1:
                return row_data.text
            elif col == 2:
                # For the combobox column, display the selected option
                return row_data.dtype
            elif col == 3:
                return row_data.rename
        elif role == Qt.ItemDataRole.CheckStateRole and col == 0:
            # Check state role for checkboxes (column 1)
            return (
                Qt.CheckState.Checked if row_data.checked else Qt.CheckState.Unchecked
            )
        elif role == Qt.ItemDataRole.EditRole:
            # Edit role for editing data (e.g., combobox selection)
            if col == 1:
                return row_data.text
            elif col == 2:
                # For the combobox column, return the currently selected option
                return row_data.dtype
            elif col == 3:
                return row_data.rename
        elif role == Qt.ItemDataRole.UserRole:
            # User role to potentially return the raw data object or specific values
            if col == 2:
                # Return the list of options for the combobox delegate
                return self._data_types
        elif role == Qt.ItemDataRole.BackgroundRole and getattr(
            row_data, "is_missing", False
        ):
            color = ResourceManager().get_theme_color("background_warning")
            color.setAlpha(140)  # let a selection highlight still show through
            return color
        elif role == Qt.ItemDataRole.ToolTipRole and getattr(
            row_data, "is_missing", False
        ):
            return "Column not found in the current input"

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False

        row = index.row()
        col = index.column()
        row_data: RowData = self._data[row]
        success = False

        if col == 0 and role == Qt.ItemDataRole.CheckStateRole:
            # Handle checkbox state change
            check_state = int(value)
            row_data.checked = check_state == Qt.CheckState.Checked.value
            logger.debug(
                f"Checkbox at row {row} set to {row_data.checked}, value: {check_state}"
            )
            success = True
        elif role == Qt.ItemDataRole.EditRole:
            if col == 3:  # Rename column
                row_data.rename = str(value)
                success = True
            elif col == 2:  # Combobox column
                row_data.dtype = str(value)
                # A manual pick has no known parse format -- clear any
                # stale one from a previous auto-detect (see
                # SelectContent.bulk_auto_detect / _date_format_by_column).
                row_data.date_format = ""
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
        return None

    def flags(self, index):
        # Define item flags (e.g., IsEditable, IsSelectable, IsUserCheckable)
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        default_flags = (
            super().flags(index)
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )

        if index.column() == 0:
            # Checkbox column is checkable
            return default_flags | Qt.ItemFlag.ItemIsUserCheckable
        elif index.column() == 2:
            # Combobox column is editable (to allow delegate to work)
            return default_flags | Qt.ItemFlag.ItemIsEditable
        elif index.column() == 3:  # Rename column
            return default_flags | Qt.ItemFlag.ItemIsEditable

        return default_flags

    def update_from_changes(self, changes: dict) -> None:
        """Update model state from changes dictionary"""
        # Restore display order first so undo/redo of a move repaints.
        # ``column_order`` holds the full order (checked + unchecked);
        # legacy stamps only have ``selected_columns`` (checked).
        order = list(changes.get("column_order") or [])
        if not order:
            selected = list(changes.get("selected_columns", []))
            order = selected + [
                row.text for row in self._data if row.text not in selected
            ]
        if order and [row.text for row in self._data] != order:
            by_name = {row.text: row for row in self._data}
            if set(by_name) == set(order):
                try:
                    self.beginResetModel()
                    self._data[:] = [by_name[name] for name in order]
                    self.endResetModel()
                except RuntimeError:
                    pass
        for row in range(len(self._data)):
            row_data: RowData = self._data[row]
            if getattr(row_data, "is_missing", False):
                # Retained row: selected_columns/rename_mapping are pruned
                # of missing columns by design, so they must not be used to
                # overwrite what table_data already holds for it.
                continue
            # Update checked state
            row_data.checked = row_data.text in changes["selected_columns"]

            # Update data type
            if row_data.text in changes["dtype_mapping"]:
                row_data.dtype = changes["dtype_mapping"][row_data.text]
            # Update rename
            row_data.rename = changes["rename_mapping"].get(row_data.text, "")

        # Notify the view that values changed. This must be a bounded
        # dataChanged, not layoutChanged: nothing structural changed, and a
        # bare layoutChanged with an active selection segfaults (the proxy
        # rebuilds selection state around a layout change that never
        # happened).
        if self._data:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._data) - 1, 3)
            self.dataChanged.emit(top_left, bottom_right, [])
        self.data_processed.emit(self.getData())

    def set_all_checked(self, checked: bool) -> None:
        """Check or uncheck every row, emitting once.

        One emission keeps undo to a single step and avoids a full
        downstream recompute per row.
        """
        changed = False
        for row_data in self._data:
            if row_data.checked != checked:
                row_data.checked = checked
                changed = True
        if not changed or not self._data:
            return
        top_left = self.index(0, 0)
        bottom_right = self.index(len(self._data) - 1, 0)
        self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole])
        self.data_processed.emit(self.getData())

    def checkSelected(self, view: QTableView) -> None:
        """Check only the selected rows in the view

        Args:
            view (QTableView): The table view instance
        """
        if not view:
            logger.debug("No table view provided")
            return

        # Get selected indexes from the view
        selected_indexes = view.selectionModel().selectedRows()
        if not selected_indexes:
            logger.debug("No rows selected")
            return

        # Check each selected row
        for index in selected_indexes:
            # Map to source model if using proxy
            if isinstance(view.model(), QSortFilterProxyModel):
                index = view.model().mapToSource(index)

            row = index.row()
            if 0 <= row < len(self._data):
                self._data[row].checked = True
                checkbox_index = self.index(row, 0)
                self.dataChanged.emit(
                    checkbox_index, checkbox_index, [Qt.ItemDataRole.CheckStateRole]
                )

        self.data_processed.emit(self.getData())
        logger.debug(f"Checked {len(selected_indexes)} selected rows")

    def uncheckSelected(self, view: QTableView) -> None:
        """Uncheck only the selected rows in the view

        Args:
            view (QTableView): The table view instance
        """

        if not view:
            logger.debug("No table view provided")
            return

        # Get selected indexes from the view
        selected_indexes = view.selectionModel().selectedRows()
        if not selected_indexes:
            logger.debug("No rows selected")
            return

        # Check each selected row
        for index in selected_indexes:
            # Map to source model if using proxy
            if isinstance(view.model(), QSortFilterProxyModel):
                index = view.model().mapToSource(index)

            row = index.row()
            if 0 <= row < len(self._data):
                self._data[row].checked = False
                checkbox_index = self.index(row, 0)
                self.dataChanged.emit(
                    checkbox_index, checkbox_index, [Qt.ItemDataRole.CheckStateRole]
                )

        self.data_processed.emit(self.getData())
        logger.debug(f"Checked {len(selected_indexes)} selected rows")

    def _move_data(self, source_row: int, target_row: int) -> bool:
        """Reorder ``_data`` with proper model notifications, without emitting."""
        if not (
            0 <= source_row < len(self._data) and 0 <= target_row < len(self._data)
        ):
            return False
        if source_row == target_row:
            return True

        # Adjust target position for moving down
        destination_row = target_row + 1 if source_row < target_row else target_row

        # Use beginMoveRows to handle the move
        if self.beginMoveRows(
            QModelIndex(), source_row, source_row, QModelIndex(), destination_row
        ):
            # Actually move the data
            item = self._data.pop(source_row)
            self._data.insert(target_row, item)
            self.endMoveRows()
            return True
        return False

    def moveSelectedRow(self, direction: str, view: QTableView = None) -> None:
        """Move selected row(s) up or down, preserving the display order.

        Operates on highlighted rows (``selectedRows``) with a fallback to
        the current index, mapped through the search proxy to source rows.
        A contiguous block moves together; a single row swaps with its
        neighbour. Emits one ``data_processed`` so the Select node records
        a single history step.

        Args:
            direction (str): "up" or "down"
            view (QTableView, optional): The table view. Defaults to None.
        """
        logger.debug(f"Moving row {direction}")

        if direction not in ("up", "down"):
            logger.debug(f"Unknown move direction: {direction}")
            return

        if not view:
            logger.debug("No table view provided")
            return

        try:
            selection_model = view.selectionModel()
            model = view.model()
        except RuntimeError:
            return
        if selection_model is None:
            logger.debug("No selection model")
            return

        is_proxy = isinstance(model, QSortFilterProxyModel)

        def _to_source(row_index) -> int | None:
            try:
                if is_proxy:
                    row_index = model.mapToSource(row_index)
                if row_index.isValid() and 0 <= row_index.row() < len(self._data):
                    return row_index.row()
            except RuntimeError:
                return None
            return None

        source_rows: list[int] = []
        try:
            for proxy_index in selection_model.selectedRows():
                row = _to_source(proxy_index)
                if row is not None and row not in source_rows:
                    source_rows.append(row)
        except RuntimeError:
            return
        if not source_rows:
            try:
                current_index = selection_model.currentIndex()
            except RuntimeError:
                return
            if current_index.isValid():
                row = _to_source(current_index)
                if row is not None:
                    source_rows.append(row)
        if not source_rows:
            logger.debug("No row selected")
            return

        source_rows.sort()
        if direction == "up" and source_rows[0] == 0:
            return
        if direction == "down" and source_rows[-1] == len(self._data) - 1:
            return

        if len(source_rows) == 1:
            current_row = source_rows[0]
            target_row = current_row - 1 if direction == "up" else current_row + 1
            if self._move_data(current_row, target_row):
                self.data_processed.emit(self.getData())
                self._restore_move_selection(view, [target_row])
            return

        # Block move: step rows in an order that keeps the block intact.
        ordered = (
            list(source_rows) if direction == "up" else list(reversed(source_rows))
        )
        moved = True
        for row in ordered:
            target = row - 1 if direction == "up" else row + 1
            moved = self._move_data(row, target) and moved
        if moved:
            step = -1 if direction == "up" else 1
            self.data_processed.emit(self.getData())
            self._restore_move_selection(view, [row + step for row in source_rows])

    def _restore_move_selection(self, view: QTableView, source_rows: list[int]) -> None:
        """Highlight ``source_rows`` after a move so the selection follows."""
        try:
            selection_model = view.selectionModel()
            model = view.model()
            is_proxy = isinstance(model, QSortFilterProxyModel)
            selection_model.clearSelection()
            for row in source_rows:
                if not 0 <= row < len(self._data):
                    continue
                source_index = self.index(row, 0)
                proxy_index = (
                    model.mapFromSource(source_index) if is_proxy else source_index
                )
                if proxy_index.isValid():
                    view.setCurrentIndex(proxy_index)
                    selection_model.select(
                        proxy_index,
                        QItemSelectionModel.Select | QItemSelectionModel.Rows,
                    )
        except RuntimeError:
            pass

    def getData(self) -> list:
        data = []
        for row in range(self.rowCount()):
            row_data: RowData = self._data[row]
            if row_data.checked:
                data.append((row_data.text, row_data.dtype, row_data.rename))
        return data

    def rows(self) -> list:
        """Every row, including unchecked and missing columns."""
        return self._data

    def set_rows(self, rows: list) -> None:
        """Replace the row list without emitting ``data_processed``."""
        self.beginResetModel()
        self._data = rows
        self.endResetModel()


# Custom delegate for the ComboBox column
class ComboBoxDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        # Create the editor widget (a QComboBox)
        if index.column() == 2:  # Apply only to the 'Option' column
            editor = QComboBox(parent)
            # Themed via QSS; setAutoFillBackground(True) would repaint it
            # with the default palette and undo the dock colours.
            editor.setObjectName("DataTypeCombo")
            # Get the list of options from the model using Qt.UserRole
            options = index.model().data(index, Qt.UserRole)
            if options:
                editor.addItems(options)
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
            # Pin the height to the cell: the dock's 30px control height would
            # otherwise make the open editor hang over the row below.
            editor.setGeometry(option.rect)
            editor.setFixedHeight(max(18, option.rect.height()))
        else:
            super().updateEditorGeometry(editor, option, index)

    def paint(self, painter, option, index):
        if not index.isValid():
            return super().paint(painter, option, index)

        # Get the value from the model
        value = index.data(Qt.ItemDataRole.DisplayRole)

        # Create style option for combo box. The palette/font MUST be copied
        # from the view option: a bare QStyleOptionComboBox falls back to the
        # application default palette, which renders a light grey box that
        # clashes with the themed table.
        opt = QStyleOptionComboBox()
        opt.rect = option.rect
        opt.state = option.state
        opt.palette = option.palette
        opt.font = option.font
        opt.fontMetrics = option.fontMetrics
        opt.subControls = (
            QStyle.SubControl.SC_ComboBoxFrame | QStyle.SubControl.SC_ComboBoxArrow
        )
        opt.activeSubControls = QStyle.SubControl.SC_ComboBoxArrow
        opt.currentText = ""

        # Cell background first: keeps alternating rows and selection intact.
        # This delegate builds its own QStyleOptionComboBox rather than
        # calling initStyleOption(), so option.backgroundBrush is never
        # populated from the model's BackgroundRole the way it is for the
        # plain-QStyledItemDelegate columns -- read it explicitly instead.
        painter.save()
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        role_bg = index.data(Qt.ItemDataRole.BackgroundRole)
        if selected:
            # The text below is HighlightedText, so the cell must be Highlight
            # or it is light text on a light cell.
            painter.fillRect(
                option.rect, option.palette.color(QPalette.ColorRole.Highlight)
            )
        elif role_bg is not None:
            painter.fillRect(option.rect, QColor(role_bg))
        elif option.backgroundBrush.style() != Qt.BrushStyle.NoBrush:
            option.backgroundBrush.draw(painter, option.rect)
        else:
            painter.fillRect(option.rect, option.palette.color(QPalette.ColorRole.Base))

        text_rect = option.rect.adjusted(6, 0, -20, 0)

        # Text colour follows selection state, like every other cell.
        text_color = option.palette.color(
            QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        )

        # Subtle field frame so the cell still reads as a dropdown.
        frame_color = option.palette.color(QPalette.ColorRole.Mid)
        painter.setPen(QPen(frame_color, 1))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        field_rect = option.rect.adjusted(3, 3, -3, -3)
        painter.drawRoundedRect(field_rect, 3, 3)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        painter.setPen(QPen(text_color))
        elided = option.fontMetrics.elidedText(
            str(value), Qt.TextElideMode.ElideRight, text_rect.width()
        )
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elided,
        )

        # Chevron, drawn in the same colour as the text.
        painter.setPen(QPen(text_color, 1))
        cx = option.rect.right() - 12
        cy = option.rect.center().y() + 1
        painter.drawLine(cx - 3, cy - 1, cx, cy + 2)
        painter.drawLine(cx, cy + 2, cx + 3, cy - 1)

        painter.restore()

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
