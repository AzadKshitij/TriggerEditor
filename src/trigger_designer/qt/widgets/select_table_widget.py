"""Table editor for the Select node.

The table is a projection of ``settings['columns']``.  A model owns the rows,
a proxy filters them, and two delegates edit the dtype and rename columns.
Every user action emits one :class:`TableEdit`, so the content can record one
labelled undo step without the model knowing about history.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from loguru import logger
from qtpy.QtCore import (
    QAbstractTableModel,
    QEvent,
    QItemSelectionModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    Signal,
)
from qtpy.QtGui import QPainter, QPalette, QPen
from qtpy.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QLineEdit,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)

from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.widgets.common.config_widgets import ROW_H, NoWheelComboBox


@dataclasses.dataclass
class RowData:
    checked: bool = dataclasses.field(default=False)
    text: str = ""
    dtype: str = "object"
    rename: str = ""
    is_missing: bool = False
    date_format: str = ""


@dataclass
class TableEdit:
    """One completed table action, ready to become one undo step."""

    rows: list[RowData]
    label: str = "Select Columns Changed"


class SelectTableModel(QAbstractTableModel):
    """The Select table's rows and the only source of table mutations."""

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

    HEADERS = ("", "Column", "Data Type", "Rename")
    COL_CHECK = 0
    COL_NAME = 1
    COL_DTYPE = 2
    COL_RENAME = 3

    data_processed = Signal(object)

    def __init__(self, data: list[RowData], changes: dict, parent=None) -> None:
        super().__init__(parent)
        self._data = data
        self.changes = changes or {
            "selected_columns": [],
            "rename_mapping": {},
            "dtype_mapping": {},
        }

    # ---- Qt model ------------------------------------------------------
    def rowCount(self, parent=None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._data)

    def columnCount(self, parent=None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self.HEADERS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        column = index.column()
        if not 0 <= row < len(self._data):
            return None
        row_data = self._data[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if column == self.COL_NAME:
                return row_data.text
            if column == self.COL_DTYPE:
                return row_data.dtype
            if column == self.COL_RENAME:
                return row_data.rename
        elif role == Qt.ItemDataRole.CheckStateRole and column == self.COL_CHECK:
            return (
                Qt.CheckState.Checked if row_data.checked else Qt.CheckState.Unchecked
            )
        elif role == Qt.ItemDataRole.EditRole:
            if column == self.COL_NAME:
                return row_data.text
            if column == self.COL_DTYPE:
                return row_data.dtype
            if column == self.COL_RENAME:
                return row_data.rename
        elif role == Qt.ItemDataRole.UserRole and column == self.COL_DTYPE:
            return list(self.DATA_TYPES)
        elif role == Qt.ItemDataRole.BackgroundRole and row_data.is_missing:
            color = ResourceManager().get_theme_color("background_warning")
            color.setAlpha(140)  # let a selection highlight still show through
            return color
        elif role == Qt.ItemDataRole.ToolTipRole and row_data.is_missing:
            return "Column not found in the current input"
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if column == self.COL_CHECK:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False
        row = index.row()
        column = index.column()
        if not 0 <= row < len(self._data):
            return False
        row_data = self._data[row]

        if column == self.COL_CHECK and role == Qt.ItemDataRole.CheckStateRole:
            checked = _as_checked(value)
            if row_data.checked == checked:
                return True
            row_data.checked = checked
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            self._emit("Column Selected" if checked else "Column Deselected")
            return True

        if role != Qt.ItemDataRole.EditRole:
            return False

        if column == self.COL_DTYPE:
            dtype = str(value).strip()
            if not dtype:
                return False
            if row_data.dtype == dtype:
                return True
            row_data.dtype = dtype
            # A manual pick has no known parse format -- clear any stale one
            # from a previous auto-detect.
            row_data.date_format = ""
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.EditRole])
            self._emit("Column Type Changed")
            return True

        if column == self.COL_RENAME:
            rename = str(value).strip()
            if row_data.rename == rename:
                return True
            row_data.rename = rename
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.EditRole])
            self._emit("Column Renamed")
            return True

        return False

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        elif orientation == Qt.Orientation.Vertical:
            return str(section + 1)
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = (
            super().flags(index)
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )
        if index.column() == self.COL_CHECK:
            return flags | Qt.ItemFlag.ItemIsUserCheckable
        if index.column() in (self.COL_DTYPE, self.COL_RENAME):
            return flags | Qt.ItemFlag.ItemIsEditable
        return flags

    # ---- projection ----------------------------------------------------
    def rows(self) -> list[RowData]:
        """Every row, including unchecked and missing columns."""
        return self._data

    def set_rows(self, rows: list[RowData]) -> None:
        """Replace the row list without emitting ``data_processed``."""
        self.beginResetModel()
        self._data = rows
        self.endResetModel()

    def notify_rows_changed(self) -> None:
        """Repaint every row after a caller mutated ``RowData`` in place."""
        if not self._data:
            return
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(len(self._data) - 1, self.columnCount() - 1),
            [],
        )

    def getData(self) -> list:
        """Checked rows as ``(name, dtype, rename)`` tuples.

        Kept for callers written against the old table; new code should use
        :meth:`rows`.
        """
        return [(row.text, row.dtype, row.rename) for row in self._data if row.checked]

    def update_from_changes(self, changes: dict) -> None:
        """Project a restored ``changes`` dict onto the model without recording.

        Undo restores the settings first and then asks the editor to show them.
        This method must stay silent: emitting ``data_processed`` here would
        record the change it is restoring.
        """
        order = list(changes.get("column_order") or [])
        if not order:
            selected = list(changes.get("selected_columns") or [])
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
                    return

        selected = set(changes.get("selected_columns") or [])
        dtype_mapping = changes.get("dtype_mapping") or {}
        rename_mapping = changes.get("rename_mapping") or {}
        for row_data in self._data:
            if row_data.is_missing:
                # Retained row: selected_columns/rename_mapping are pruned of
                # missing columns by design, so they must not overwrite what
                # table_data already holds for it.
                continue
            row_data.checked = row_data.text in selected
            if row_data.text in dtype_mapping:
                row_data.dtype = dtype_mapping[row_data.text]
            row_data.rename = rename_mapping.get(row_data.text, "")

        self.changes = changes
        self.notify_rows_changed()

    # ---- user actions --------------------------------------------------
    def toggle_row(self, row: int) -> None:
        if not 0 <= row < len(self._data):
            return
        self.setData(
            self.index(row, self.COL_CHECK),
            not self._data[row].checked,
            Qt.ItemDataRole.CheckStateRole,
        )

    def set_all_checked(self, checked: bool) -> None:
        """Check or uncheck every row, emitting once.

        One emission keeps undo to a single step and avoids a full downstream
        recompute per row.
        """
        changed = False
        for row_data in self._data:
            if row_data.checked != checked:
                row_data.checked = checked
                changed = True
        if not changed or not self._data:
            return
        self.dataChanged.emit(
            self.index(0, self.COL_CHECK),
            self.index(len(self._data) - 1, self.COL_CHECK),
            [Qt.ItemDataRole.CheckStateRole],
        )
        self._emit("Columns Selected" if checked else "Columns Deselected")

    def checkSelected(self, view: QTableView) -> None:
        """Check the highlighted rows, in one history step."""
        rows = self._source_rows_from_view(view)
        if not rows:
            return
        changed = False
        for row in rows:
            if not self._data[row].checked:
                self._data[row].checked = True
                changed = True
        if not changed:
            return
        self.dataChanged.emit(
            self.index(rows[0], self.COL_CHECK),
            self.index(rows[-1], self.COL_CHECK),
            [Qt.ItemDataRole.CheckStateRole],
        )
        self._emit("Columns Selected" if len(rows) > 1 else "Column Selected")

    def uncheckSelected(self, view: QTableView) -> None:
        """Uncheck the highlighted rows, in one history step."""
        rows = self._source_rows_from_view(view)
        if not rows:
            return
        changed = False
        for row in rows:
            if self._data[row].checked:
                self._data[row].checked = False
                changed = True
        if not changed:
            return
        self.dataChanged.emit(
            self.index(rows[0], self.COL_CHECK),
            self.index(rows[-1], self.COL_CHECK),
            [Qt.ItemDataRole.CheckStateRole],
        )
        self._emit("Columns Deselected" if len(rows) > 1 else "Column Deselected")

    def _source_rows_from_view(self, view: QTableView | None) -> list[int]:
        if view is None:
            return []
        try:
            selection = view.selectionModel()
            model = view.model()
        except RuntimeError:
            return []
        if selection is None or model is None:
            return []
        rows: list[int] = []
        try:
            for index in selection.selectedRows():
                if isinstance(model, QSortFilterProxyModel):
                    index = model.mapToSource(index)
                row = index.row()
                if 0 <= row < len(self._data) and row not in rows:
                    rows.append(row)
        except RuntimeError:
            return []
        return sorted(rows)

    # ---- reordering ----------------------------------------------------
    def _move_data(self, source_row: int, target_row: int) -> bool:
        """Reorder ``_data`` with model notifications, without emitting."""
        if not (
            0 <= source_row < len(self._data) and 0 <= target_row < len(self._data)
        ):
            return False
        if source_row == target_row:
            return True

        destination_row = target_row + 1 if source_row < target_row else target_row
        if self.beginMoveRows(
            QModelIndex(), source_row, source_row, QModelIndex(), destination_row
        ):
            item = self._data.pop(source_row)
            self._data.insert(target_row, item)
            self.endMoveRows()
            return True
        return False

    def moveRow(self, source_row: int, target_row: int) -> bool:
        if self._move_data(source_row, target_row):
            if source_row != target_row:
                self._emit("Columns Reordered")
            return True
        if 0 <= source_row < len(self._data) and 0 <= target_row < len(self._data):
            return source_row == target_row
        return False

    def moveSelectedRow(self, direction: str, view: QTableView | None = None) -> None:
        """Move selected row(s) up or down, preserving the display order.

        Operates on highlighted rows (``selectedRows``) with a fallback to
        the current index, mapped through the search proxy to source rows.
        A contiguous block moves together; a single row swaps with its
        neighbour. Emits one ``data_processed`` so the Select node records
        a single history step.
        """
        logger.debug(f"Moving row {direction}")
        if direction not in ("up", "down") or view is None:
            return
        rows = self._selected_source_rows(view)
        if not rows:
            return
        if direction == "up" and rows[0] == 0:
            return
        if direction == "down" and rows[-1] == len(self._data) - 1:
            return

        if len(rows) == 1:
            current_row = rows[0]
            target_row = current_row - 1 if direction == "up" else current_row + 1
            if self._move_data(current_row, target_row):
                self._emit("Columns Reordered")
                self._restore_move_selection(view, [target_row])
            return

        # Block move: step rows in an order that keeps the block intact.
        ordered = list(rows) if direction == "up" else list(reversed(rows))
        moved = True
        for row in ordered:
            target = row - 1 if direction == "up" else row + 1
            moved = self._move_data(row, target) and moved
        if moved:
            step = -1 if direction == "up" else 1
            self._emit("Columns Reordered")
            self._restore_move_selection(view, [row + step for row in rows])

    def moveSelectedToTop(self, view: QTableView | None = None) -> None:
        self._move_selected_to_edge(view, "top")

    def moveSelectedToBottom(self, view: QTableView | None = None) -> None:
        self._move_selected_to_edge(view, "bottom")

    def _move_selected_to_edge(self, view: QTableView | None, edge: str) -> None:
        rows = self._selected_source_rows(view)
        if not rows or view is None:
            return
        selected = set(rows)
        block = [self._data[row] for row in rows]
        rest = [row for index, row in enumerate(self._data) if index not in selected]
        ordered = block + rest if edge == "top" else rest + block
        if [row.text for row in ordered] == [row.text for row in self._data]:
            return
        self.beginResetModel()
        self._data[:] = ordered
        self.endResetModel()
        target_rows = (
            list(range(len(block)))
            if edge == "top"
            else list(range(len(rest), len(rest) + len(block)))
        )
        self._emit(
            "Columns Moved to Top" if edge == "top" else "Columns Moved to Bottom"
        )
        self._restore_move_selection(view, target_rows)

    def _selected_source_rows(self, view: QTableView | None) -> list[int]:
        rows = self._source_rows_from_view(view)
        if rows:
            return rows
        if view is None:
            return []
        try:
            current = view.selectionModel().currentIndex()
        except AttributeError, RuntimeError:
            return []
        if not current.isValid():
            return []
        model = view.model()
        if isinstance(model, QSortFilterProxyModel):
            current = model.mapToSource(current)
        row = current.row()
        return [row] if 0 <= row < len(self._data) else []

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
                source_index = self.index(row, self.COL_CHECK)
                proxy_index = (
                    model.mapFromSource(source_index) if is_proxy else source_index
                )
                if proxy_index.isValid():
                    view.setCurrentIndex(proxy_index)
                    selection_model.select(
                        proxy_index,
                        QItemSelectionModel.SelectionFlag.Select
                        | QItemSelectionModel.SelectionFlag.Rows,
                    )
        except RuntimeError:
            pass

    # ---- signal --------------------------------------------------------
    def _emit(self, label: str) -> None:
        self.data_processed.emit(TableEdit(rows=self._data, label=label))


class SelectFilterProxy(QSortFilterProxyModel):
    """Case-insensitive search over column name, rename and dtype."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(-1)
        self._needle = ""

    def setFilterText(self, text: str) -> None:
        needle = str(text).strip().casefold()
        # Qt 6.12 deprecates invalidateFilter()/invalidateRowsFilter() in
        # favour of an explicit filter-change scope. Keep the old calls for
        # older Qt builds.
        begin = getattr(self, "beginFilterChange", None)
        end = getattr(self, "endFilterChange", None)
        if begin is not None and end is not None:
            begin()
            self._needle = needle
            end(QSortFilterProxyModel.Direction.Rows)
            return
        self._needle = needle
        invalidate = getattr(self, "invalidateRowsFilter", None)
        if invalidate is not None:
            invalidate()
        else:
            self.invalidateFilter()

    # Keep the old call site working; it is also the QSortFilterProxyModel API.
    def setFilterFixedString(self, pattern: str) -> None:
        self.setFilterText(pattern)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._needle:
            return True
        model = self.sourceModel()
        if model is None:
            return True
        for column in (
            SelectTableModel.COL_NAME,
            SelectTableModel.COL_DTYPE,
            SelectTableModel.COL_RENAME,
        ):
            index = model.index(source_row, column, source_parent)
            text = str(model.data(index, Qt.ItemDataRole.DisplayRole) or "")
            if self._needle in text.casefold():
                return True
        return False


class DtypeDelegate(QStyledItemDelegate):
    """Inline dtype dropdown; one click opens it, one pick commits."""

    def createEditor(self, parent, option, index):
        if index.column() != SelectTableModel.COL_DTYPE:
            return super().createEditor(parent, option, index)
        editor = NoWheelComboBox(parent)
        editor.setObjectName("DataTypeCombo")
        options = index.data(Qt.ItemDataRole.UserRole) or SelectTableModel.DATA_TYPES
        editor.addItems(list(options))
        return editor

    def setEditorData(self, editor, index):
        if not isinstance(editor, QComboBox):
            return super().setEditorData(editor, index)
        value = str(index.data(Qt.ItemDataRole.EditRole) or "")
        position = editor.findText(value)
        if position < 0 and value:
            editor.addItem(value)
            position = editor.findText(value)
        editor.setCurrentIndex(max(position, 0))
        _open_combo_popup(editor)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)
        editor.setFixedHeight(max(20, option.rect.height()))

    def paint(self, painter, option, index):
        if not index.isValid():
            return super().paint(painter, option, index)

        value = index.data(Qt.ItemDataRole.DisplayRole)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        # Let the view's stylesheet paint the row background, hover tint,
        # selection and missing-column warning. Only the cell text is ours, so
        # clear it for this pass and draw it below with room for the chevron.
        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        style_option.text = ""
        style = (
            style_option.widget.style()
            if style_option.widget is not None
            else QApplication.style()
        )
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            style_option,
            painter,
            style_option.widget,
        )

        text_color = option.palette.color(
            QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        )
        text_rect = option.rect.adjusted(6, 0, -20, 0)

        # Subtle field frame so the cell still reads as a dropdown.
        painter.save()
        painter.setPen(QPen(option.palette.color(QPalette.ColorRole.Mid), 1))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawRoundedRect(option.rect.adjusted(3, 3, -3, -3), 3, 3)
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

        # Chevron in the same colour as the text.
        painter.setPen(QPen(text_color, 1))
        cx = option.rect.right() - 12
        cy = option.rect.center().y() + 1
        painter.drawLine(cx - 3, cy - 1, cx, cy + 2)
        painter.drawLine(cx, cy + 2, cx + 3, cy - 1)
        painter.restore()


class RenameDelegate(QStyledItemDelegate):
    """Rename editor: Enter/focus-out commits, Escape reverts."""

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setObjectName("RenameEditor")
        editor.setFrame(False)
        return editor

    def setEditorData(self, editor, index):
        if isinstance(editor, QLineEdit):
            editor.setText(str(index.data(Qt.ItemDataRole.EditRole) or ""))
            editor.selectAll()
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QLineEdit):
            model.setData(index, editor.text().strip(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect.adjusted(1, 1, -1, -1))

    def eventFilter(self, editor, event):
        if (
            isinstance(editor, QLineEdit)
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
        ):
            self.closeEditor.emit(
                editor, QAbstractItemDelegate.EndEditHint.RevertModelCache
            )
            return True
        return super().eventFilter(editor, event)


class SelectTableView(QTableView):
    """Editable column table with keyboard and context-menu affordances."""

    contextMenuRequested = Signal(object)

    #: Floor for the auto-fitted name column; below this the table scrolls
    #: instead of squeezing the only column that shows real content.
    MIN_NAME_WIDTH = 110

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ColumnTable")
        self._undo_composite = True
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.setSortingEnabled(False)
        self.setCornerButtonEnabled(False)
        self.clicked.connect(self._open_dtype_editor)
        #: True while the view itself grows a column to fill spare width; the
        #: content must not treat that as a user-chosen width.
        self._auto_fitting = False
        #: True until the user drags a column: the name column then absorbs
        #: both spare width and overflow so the table stays flush.
        self._auto_width = True
        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionsClickable(False)
        header.setFixedHeight(24)
        vertical = self.verticalHeader()
        vertical.setVisible(False)
        vertical.setDefaultSectionSize(ROW_H)

    def _source_index(self, index):
        model = self.model()
        if model is None or not index.isValid():
            return QModelIndex()
        if isinstance(model, QSortFilterProxyModel):
            return model.mapToSource(index)
        return index

    def _open_dtype_editor(self, index) -> None:
        """Open the dtype dropdown on a single click, after the click lands."""
        if index.column() == SelectTableModel.COL_DTYPE:
            self.edit(index)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fill_name_column()

    def _fill_name_column(self) -> None:
        """Keep the table flush with the viewport.

        Before the user drags a column, the name column absorbs spare width
        and overflow, so the table always fits. Afterwards their widths are
        respected: spare width still goes to the name column, but a narrow
        dock scrolls instead of silently shrinking a chosen width.
        """
        header = self.horizontalHeader()
        count = header.count()
        if count == 0:
            return
        total = sum(header.sectionSize(column) for column in range(count))
        extra = self.viewport().width() - total
        if extra == 0:
            return
        name = SelectTableModel.COL_NAME
        current = header.sectionSize(name)
        target = current + extra
        if self._auto_width:
            target = max(target, self.MIN_NAME_WIDTH)
        elif target <= current:
            return
        if target == current:
            return
        self._auto_fitting = True
        try:
            header.resizeSection(name, target)
        finally:
            self._auto_fitting = False

    def keyPressEvent(self, event) -> None:
        index = self.currentIndex()
        model = self.model()
        if index.isValid() and model is not None:
            source = self._source_index(index)
            source_model = source.model() if source.isValid() else None
            if event.key() == Qt.Key.Key_Space and source_model is not None:
                source_model.toggle_row(source.row())
                event.accept()
                return
            if event.modifiers() & Qt.KeyboardModifier.AltModifier and event.key() in (
                Qt.Key.Key_Up,
                Qt.Key.Key_Down,
            ):
                if source_model is not None:
                    source_model.moveSelectedRow(
                        "up" if event.key() == Qt.Key.Key_Up else "down", self
                    )
                event.accept()
                return
            if event.key() == Qt.Key.Key_F2:
                target = index
                if index.column() not in (
                    SelectTableModel.COL_DTYPE,
                    SelectTableModel.COL_RENAME,
                ):
                    target = model.index(index.row(), SelectTableModel.COL_RENAME)
                self.setCurrentIndex(target)
                self.edit(target)
                event.accept()
                return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:
        index = self.indexAt(event.pos())
        if index.isValid():
            selection = self.selectionModel()
            if selection is not None and not selection.isSelected(index):
                selection.select(
                    index,
                    QItemSelectionModel.SelectionFlag.ClearAndSelect
                    | QItemSelectionModel.SelectionFlag.Rows,
                )
            self.setCurrentIndex(index)
        self.contextMenuRequested.emit(event.globalPos())
        event.accept()


def _as_checked(value) -> bool:
    if isinstance(value, Qt.CheckState):
        return value == Qt.CheckState.Checked
    if isinstance(value, bool):
        return value
    return int(value) == int(Qt.CheckState.Checked.value)


def _open_combo_popup(editor: QComboBox) -> None:
    def _show() -> None:
        try:
            editor.showPopup()
        except RuntimeError:
            pass

    QTimer.singleShot(0, _show)


# Compatibility aliases for imports written against the old table module.
SelectTableWidget = SelectTableModel
ComboBoxDelegate = DtypeDelegate
