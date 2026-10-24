"""Model/view column picker with search, selected chips and single-select mode."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from qtpy.QtCore import (
    QAbstractListModel,
    QEvent,
    QModelIndex,
    QPoint,
    QPointF,
    QRect,
    QSize,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from qtpy.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
)
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.qt.theme_manager import get_theme_manager
from trigger_designer.qt.widgets.common.config_widgets import CONTROL_H, TextButton

NAME_ROLE = int(Qt.ItemDataRole.UserRole) + 1
DTYPE_ROLE = NAME_ROLE + 1
SELECTED_ROLE = NAME_ROLE + 2
BLANK_ROLE = NAME_ROLE + 3


def dtype_label(dtype: Any) -> str:
    """Short readable dtype for the row badge."""
    text = str(dtype)
    text = text.removeprefix("pl.")
    if "(" in text:
        text = text.split("(", 1)[0]
    return {"Boolean": "Bool", "Datetime": "DateTime"}.get(text, text)


@dataclass(frozen=True)
class ColumnItem:
    name: str
    dtype: str = ""
    label: str = ""
    blank: bool = False

    def display(self) -> str:
        return self.label or self.name


def _normalise_items(items: Iterable[Any]) -> list[ColumnItem]:
    result: list[ColumnItem] = []
    seen: set[str] = set()
    for raw in items:
        if isinstance(raw, ColumnItem):
            item = raw
        elif isinstance(raw, (tuple, list)) and len(raw) >= 2:
            item = ColumnItem(str(raw[0]), str(raw[1] or ""))
        else:
            item = ColumnItem(str(raw), "")
        if item.name in seen:
            continue
        seen.add(item.name)
        result.append(item)
    return result


class ColumnPickerModel(QAbstractListModel):
    """Rows, selected state and an optional ``(none)`` row."""

    def __init__(
        self,
        columns: Iterable[Any] = (),
        checked: Iterable[str] = (),
        *,
        single: bool = False,
        allow_blank: bool = False,
        blank_label: str = "(none)",
    ) -> None:
        super().__init__()
        self._items: list[ColumnItem] = []
        self._selected: set[str] = set()
        self._single = single
        self._allow_blank = allow_blank
        self._blank_label = blank_label
        self.set_columns(columns, checked)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._items)

    def data(self, index: QModelIndex, role: int = 0):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role == int(Qt.ItemDataRole.DisplayRole):
            return item.display()
        if role == NAME_ROLE:
            return item.name
        if role == DTYPE_ROLE:
            return item.dtype
        if role == SELECTED_ROLE:
            return item.name in self._selected
        if role == BLANK_ROLE:
            return item.blank
        if role == int(Qt.ItemDataRole.ToolTipRole):
            if item.blank:
                return "Clear selection"
            return f"{item.name} ({item.dtype})" if item.dtype else item.name
        if role == int(Qt.ItemDataRole.SizeHintRole):
            return QSize(0, 28)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    @property
    def single(self) -> bool:
        return self._single

    @property
    def total_count(self) -> int:
        return sum(1 for item in self._items if not item.blank)

    def set_columns(
        self,
        columns: Iterable[Any],
        checked: Iterable[str] = (),
        *,
        preserve_selection: bool = False,
    ) -> None:
        old = set(self._selected) if preserve_selection else set(checked)
        items = _normalise_items(columns)
        if self._allow_blank:
            items = [ColumnItem("", "", self._blank_label, True), *items]
        valid = {item.name for item in items if not item.blank}
        self.beginResetModel()
        self._items = items
        self._selected = {name for name in old if name in valid}
        if self._single and len(self._selected) > 1:
            first = next(item.name for item in items if item.name in self._selected)
            self._selected = {first}
        self.endResetModel()

    def selected_names(self) -> list[str]:
        return [
            item.name
            for item in self._items
            if not item.blank and item.name in self._selected
        ]

    def set_selected(self, names: Iterable[str]) -> bool:
        valid = {item.name for item in self._items if not item.blank}
        selected = {name for name in names if name in valid}
        if self._single and len(selected) > 1:
            first = next(item.name for item in self._items if item.name in selected)
            selected = {first}
        if selected == self._selected:
            return False
        self._selected = selected
        self._emit_all()
        return True

    def clear(self) -> bool:
        return self.set_selected(())

    def set_many(self, names: Iterable[str], checked: bool) -> bool:
        target = set(names)
        new = set(self._selected) | target if checked else set(self._selected) - target
        if self._single and len(new) > 1:
            first = next(item.name for item in self._items if item.name in new)
            new = {first}
        if new == self._selected:
            return False
        self._selected = new
        self._emit_all()
        return True

    def toggle_name(self, name: str) -> bool:
        if name == "" and self._allow_blank:
            return self.clear()
        row = next(
            (
                i
                for i, item in enumerate(self._items)
                if item.name == name and not item.blank
            ),
            None,
        )
        if row is None:
            return False
        if self._single:
            if name in self._selected:
                return False
            self._selected = {name}
            self._emit_row(row)
            return True
        if name in self._selected:
            self._selected.remove(name)
        else:
            self._selected.add(name)
        self._emit_row(row)
        return True

    def _emit_all(self) -> None:
        if self._items:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._items) - 1, 0),
                [SELECTED_ROLE],
            )

    def _emit_row(self, row: int) -> None:
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0), [SELECTED_ROLE])


class ColumnPickerFilterProxy(QSortFilterProxyModel):
    """Case-insensitive name search. The blank row only appears unfiltered."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._query = ""

    def set_query(self, text: str) -> None:
        query = text.strip().casefold()
        if query == self._query:
            return
        self._query = query
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return False
        index = model.index(source_row, 0, source_parent)
        if index.data(BLANK_ROLE):
            return not self._query
        name = str(index.data(NAME_ROLE) or "").casefold()
        return self._query in name


class ColumnPickerDelegate(QStyledItemDelegate):
    """Paint a 28px checkbox row with an elided name and dtype badge."""

    def __init__(self, view: QListView) -> None:
        super().__init__(view)
        self._view = view

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(0, 28)

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        theme = get_theme_manager()
        accent = QColor(theme.color("accent_primary", "#5680C2"))
        text = QColor(theme.color("text_primary", "#F5F7F9"))
        secondary = QColor(theme.color("text_secondary", "#C6CDD5"))
        muted = QColor(theme.color("text_inactive", "#919BA6"))
        border = QColor(theme.color("border_primary", "#242A30"))
        strong = QColor(theme.color("border_light", "#3E4750"))
        hover = QColor(theme.color("background_hover", "#22282E"))
        raised = QColor(theme.color("background_secondary", "#191E22"))
        inset = QColor(theme.color("editor_background", "#101418"))

        selected = bool(index.data(SELECTED_ROLE))
        blank = bool(index.data(BLANK_ROLE))
        rect = option.rect
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if selected:
            fill = QColor(accent)
            fill.setAlpha(28)
            painter.fillRect(rect, fill)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, hover)

        current = self._view.currentIndex() == index and self._view.hasFocus()
        if current:
            painter.setPen(QPen(accent, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 3, 3)

        box = QRect(rect.left() + 6, rect.center().y() - 6, 13, 13)
        painter.setPen(QPen(strong, 1))
        painter.setBrush(inset)
        painter.drawRoundedRect(box, 2, 2)
        if selected and not blank:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent)
            painter.drawRoundedRect(box, 2, 2)
            painter.setPen(QPen(QColor("#FFFFFF"), 1.6))
            painter.drawLine(
                QPointF(box.left() + 3.0, box.center().y()),
                QPointF(box.left() + 5.5, box.center().y() + 2.5),
            )
            painter.drawLine(
                QPointF(box.left() + 5.5, box.center().y() + 2.5),
                QPointF(box.left() + 10.0, box.center().y() - 2.5),
            )
        elif blank:
            painter.setPen(QPen(muted, 1))
            painter.drawLine(
                box.left() + 3,
                box.center().y(),
                box.right() - 3,
                box.center().y(),
            )

        name_x = box.right() + 7
        dtype = str(index.data(DTYPE_ROLE) or "")
        dtype_rect = QRect()
        if dtype:
            dtype_font = QFont("Cascadia Mono")
            dtype_font.setPixelSize(9)
            metrics = QFontMetrics(dtype_font)
            width = metrics.horizontalAdvance(dtype) + 10
            dtype_rect = QRect(
                rect.right() - 7 - width,
                rect.center().y() - 8,
                width,
                16,
            )
            painter.setPen(QPen(border, 1))
            painter.setBrush(raised)
            painter.drawRoundedRect(dtype_rect, 3, 3)
            painter.setFont(dtype_font)
            painter.setPen(muted)
            painter.drawText(dtype_rect, Qt.AlignmentFlag.AlignCenter, dtype)

        name_right = dtype_rect.left() - 5 if dtype else rect.right() - 7
        name_font = QFont(option.font)
        name_font.setPixelSize(12)
        name_font.setWeight(QFont.Weight.Normal)
        painter.setFont(name_font)
        painter.setPen(text if (selected or current) else secondary)
        label = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        elided = QFontMetrics(name_font).elidedText(
            label, Qt.TextElideMode.ElideRight, max(name_right - name_x, 10)
        )
        painter.drawText(
            QRect(name_x, rect.top(), max(name_right - name_x, 10), rect.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            elided,
        )
        painter.restore()


class ColumnPickerList(QListView):
    """List view that toggles a row on click instead of selecting it."""

    toggled = Signal(str)
    escapePressed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ColumnPickerList")
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setUniformItemSizes(True)
        self.setSpacing(0)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setToolTipDuration(3000)

    def mousePressEvent(self, event) -> None:
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        index = self.indexAt(pos)
        if index.isValid():
            self.setCurrentIndex(index)
            self.toggled.emit(str(index.data(NAME_ROLE) or ""))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        if self.indexAt(pos).isValid():
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.escapePressed.emit()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            index = self.currentIndex()
            if index.isValid():
                self.toggled.emit(str(index.data(NAME_ROLE) or ""))
                event.accept()
                return
        super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:
        if (
            not self.currentIndex().isValid()
            and self.model() is not None
            and self.model().rowCount()
        ):
            self.setCurrentIndex(self.model().index(0, 0))
        super().focusInEvent(event)


class ColumnPickerPopup(QFrame):
    """Floating popup used by :class:`ColumnPicker`."""

    closed = Signal()

    def __init__(self, picker: ColumnPicker) -> None:
        super().__init__(
            picker,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self._picker = picker
        self._anchor: QWidget | None = None
        self._search = QLineEdit(self)
        self._search.setObjectName("ColumnPickerSearch")
        self._search.setPlaceholderText("Search columns...")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedHeight(CONTROL_H)
        self._search.textChanged.connect(self._on_search)
        self._search.installEventFilter(self)
        if picker._rsm is not None:
            pixmap = picker._rsm.get("icon_search")
            if isinstance(pixmap, QPixmap) and not pixmap.isNull():
                self._search.addAction(
                    QIcon(pixmap), QLineEdit.ActionPosition.LeadingPosition
                )

        self._tray = QFrame(self)
        self._tray.setObjectName("ColumnPickerTray")
        tray_layout = QVBoxLayout(self._tray)
        tray_layout.setContentsMargins(6, 5, 6, 6)
        tray_layout.setSpacing(4)
        tray_head = QHBoxLayout()
        tray_head.setContentsMargins(0, 0, 0, 0)
        tray_head.setSpacing(4)
        tray_label = QLabel("SELECTED", self._tray)
        tray_label.setObjectName("ColumnPickerTrayLabel")
        self._tray_count = QLabel("0", self._tray)
        self._tray_count.setObjectName("ColumnPickerTrayCount")
        tray_head.addWidget(tray_label)
        tray_head.addStretch(1)
        tray_head.addWidget(self._tray_count)
        tray_layout.addLayout(tray_head)
        self._chips = QWidget(self._tray)
        self._chips_grid = QGridLayout(self._chips)
        self._chips_grid.setContentsMargins(0, 0, 0, 0)
        self._chips_grid.setHorizontalSpacing(3)
        self._chips_grid.setVerticalSpacing(3)
        self._chips_grid.setColumnStretch(4, 1)
        tray_layout.addWidget(self._chips)

        self.list = ColumnPickerList(self)
        self.list.setModel(picker._proxy)
        self.list.setItemDelegate(ColumnPickerDelegate(self.list))
        self.list.toggled.connect(picker._toggle_name)
        self.list.escapePressed.connect(picker._escape)

        self.empty = QLabel("No columns available.", self)
        self.empty.setObjectName("ColumnPickerEmpty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setMinimumHeight(150)
        self.empty.hide()

        self.footer = QFrame(self)
        self.footer.setObjectName("ColumnPickerFooter")
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(6, 0, 6, 0)
        footer_layout.setSpacing(4)
        self.count_label = QLabel("", self.footer)
        self.count_label.setObjectName("ColumnPickerFooterCount")
        footer_layout.addWidget(self.count_label, 1)
        self.all_button = TextButton("All", "Select every visible column", self.footer)
        self.none_button = TextButton(
            "None", "Deselect every visible column", self.footer
        )
        for button in (self.all_button, self.none_button):
            button.setFixedSize(56, CONTROL_H)
        self.all_button.clicked.connect(lambda: picker.select_all_visible())
        self.none_button.clicked.connect(lambda: picker.clear_visible())
        footer_layout.addWidget(self.all_button)
        footer_layout.addWidget(self.none_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        search_row = QFrame(self)
        search_row_layout = QHBoxLayout(search_row)
        search_row_layout.setContentsMargins(6, 6, 6, 6)
        search_row_layout.setSpacing(0)
        search_row_layout.addWidget(self._search)
        layout.addWidget(search_row)
        layout.addWidget(self._tray)
        layout.addWidget(self.list)
        layout.addWidget(self.empty)
        layout.addWidget(self.footer)

        self.setObjectName("ColumnPickerPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedWidth(318)
        self.setFocusProxy(self._search)

    @property
    def search(self) -> QLineEdit:
        return self._search

    def open_near(self, anchor: QWidget) -> None:
        self._anchor = anchor
        self._search.blockSignals(True)
        self._search.clear()
        self._search.blockSignals(False)
        self._picker._proxy.set_query("")
        self.refresh()
        self.adjustSize()
        self._place()
        self.show()
        self._search.setFocus()

    def refresh(self) -> None:
        picker = self._picker
        rows = picker._proxy.rowCount()
        names = picker.checked()
        if rows:
            self.list.show()
            self.list.setFixedHeight(min(198, rows * 28 + 6))
            self.empty.hide()
        else:
            self.list.hide()
            self.list.setFixedHeight(0)
            self.empty.show()
            query = self._search.text().strip()
            if picker._model.total_count == 0:
                self.empty.setText("No columns available.")
            elif query:
                self.empty.setText(f'No columns match "{query}".')
            else:
                self.empty.setText("No columns available.")
        self._rebuild_tray(names)
        self._tray.setVisible(bool(names) and not picker._single)
        self.footer.setVisible(not picker._single)
        total = picker._model.total_count
        shown = picker._proxy.rowCount()
        suffix = (
            f"{shown} of {total} shown"
            if self._search.text().strip()
            else f"{total} columns"
        )
        self.count_label.setText(f"{len(names)} selected \u00b7 {suffix}")
        visible = picker.visible_names()
        visible_selected = [name for name in visible if name in names]
        self.all_button.setEnabled(
            bool(visible) and len(visible_selected) < len(visible)
        )
        self.none_button.setEnabled(bool(visible_selected))
        self.adjustSize()
        if self.isVisible():
            self._place()

    def _rebuild_tray(self, names: list[str]) -> None:
        while self._chips_grid.count():
            item = self._chips_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._tray_count.setText(str(len(names)))
        if not names:
            return
        shown = names[:7] if len(names) > 8 else names[:8]
        for index, name in enumerate(shown):
            label = QLabel(self._chips)
            label.setObjectName("ColumnToken")
            label.setFixedHeight(21)
            label.setMaximumWidth(70)
            label.setText(
                QFontMetrics(label.font()).elidedText(
                    name, Qt.TextElideMode.ElideRight, 60
                )
            )
            label.setToolTip(name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._chips_grid.addWidget(label, index // 4, index % 4)
        if len(names) > len(shown):
            more = QLabel(f"+{len(names) - len(shown)}", self._chips)
            more.setObjectName("ColumnPickerMore")
            more.setFixedHeight(21)
            self._chips_grid.addWidget(more, len(shown) // 4, len(shown) % 4)

    def _on_search(self, text: str) -> None:
        self._picker._proxy.set_query(text)
        self.refresh()

    def _place(self) -> None:
        if self._anchor is None:
            return
        width = self.width()
        height = self.height()
        screen = self._anchor.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        point = self._anchor.mapToGlobal(QPoint(0, self._anchor.height() + 2))
        x = max(available.left(), min(point.x(), available.right() - width + 1))
        y = point.y()
        if y + height > available.bottom():
            y = self._anchor.mapToGlobal(QPoint(0, 0)).y() - height - 2
            y = max(available.top(), y)
        self.move(x, y)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.closed.emit()

    def eventFilter(self, watched, event) -> bool:
        if watched is self._search and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self._picker._escape()
                return True
            if event.key() == Qt.Key.Key_Down:
                self._picker.focus_first()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._picker._escape()
            event.accept()
            return
        super().keyPressEvent(event)


class ColumnPicker(QPushButton):
    """Compact column trigger with a searchable popup.

    The popup keeps its own model, search proxy and delegate, so it stays
    responsive with large schemas. Selection is live and emitted once per
    action; the node owns the undo step.
    """

    _undo_composite = True

    changed = Signal(list)

    def __init__(
        self,
        columns: Iterable[Any] = (),
        checked: Iterable[str] = (),
        placeholder: str = "Choose columns...",
        parent: QWidget | None = None,
        *,
        single: bool = False,
        allow_blank: bool = False,
        blank_label: str = "(none)",
        rsm: Any = None,
        label: str = "Columns",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ColumnPicker")
        self.setFixedHeight(CONTROL_H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._placeholder = placeholder
        self._label = label
        self._single = single
        self._rsm = rsm
        self._popup: ColumnPickerPopup | None = None
        self._is_open = False
        self._model = ColumnPickerModel(
            columns,
            checked,
            single=single,
            allow_blank=allow_blank,
            blank_label=blank_label,
        )
        self._proxy = ColumnPickerFilterProxy(self)
        self._proxy.setSourceModel(self._model)
        self.clicked.connect(self.toggle_popup)
        self.setProperty("open", "false")
        self._render()

    def setColumns(self, columns: Iterable[Any], checked: Iterable[str] = ()) -> None:
        self._model.set_columns(columns, checked)
        self._render()
        if self._popup is not None:
            self._popup.refresh()

    def setChecked(self, checked: Iterable[str]) -> None:
        self._model.set_selected(checked)
        self._render()
        if self._popup is not None:
            self._popup.refresh()

    def set_selected(self, names: Iterable[str], *, emit: bool = False) -> None:
        before = self.checked()
        if not self._model.set_selected(names):
            return
        self._render()
        if self._popup is not None:
            self._popup.refresh()
        if emit and before != self.checked():
            self.changed.emit(self.checked())

    def set_selected_quiet(self, names: Iterable[str]) -> None:
        self._model.set_selected(names)
        self._render()
        if self._popup is not None:
            self._popup.refresh()

    def checked(self) -> list[str]:
        return self._model.selected_names()

    def selected(self) -> list[str]:
        return self.checked()

    def column_names(self) -> list[str]:
        return [item.name for item in self._model._items if not item.blank]

    def visible_names(self) -> list[str]:
        names: list[str] = []
        for row in range(self._proxy.rowCount()):
            source = self._proxy.mapToSource(self._proxy.index(row, 0))
            name = str(source.data(NAME_ROLE) or "")
            if name:
                names.append(name)
        return names

    def select_all_visible(self) -> None:
        before = self.checked()
        if self._model.set_many(self.visible_names(), True):
            self._render()
            if self._popup is not None:
                self._popup.refresh()
            if before != self.checked():
                self.changed.emit(self.checked())

    def clear_visible(self) -> None:
        before = self.checked()
        if self._model.set_many(self.visible_names(), False):
            self._render()
            if self._popup is not None:
                self._popup.refresh()
            if before != self.checked():
                self.changed.emit(self.checked())

    def is_open(self) -> bool:
        return self._is_open

    def open_popup(self) -> None:
        if not self.isEnabled():
            return
        self._ensure_popup()
        if self._popup is None:
            return
        self._set_open(True)
        self._popup.open_near(self)

    def close_popup(self) -> None:
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide()
        self._set_open(False)

    def toggle_popup(self) -> None:
        if self._is_open:
            self.close_popup()
        else:
            self.open_popup()

    def focus_first(self) -> None:
        if self._popup is None or self._proxy.rowCount() == 0:
            return
        self._popup.list.setCurrentIndex(self._proxy.index(0, 0))
        self._popup.list.setFocus()

    def _ensure_popup(self) -> None:
        if self._popup is not None:
            return
        self._popup = ColumnPickerPopup(self)
        self._popup.closed.connect(self._on_popup_closed)

    def _on_popup_closed(self) -> None:
        self._set_open(False)

    def _escape(self) -> None:
        self.close_popup()
        self.setFocus()

    def _set_open(self, opened: bool) -> None:
        if self._is_open == opened:
            return
        self._is_open = opened
        self.setProperty("open", "true" if opened else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self._render()

    def _toggle_name(self, name: str) -> None:
        before = self.checked()
        changed = self._model.toggle_name(name)
        if changed:
            self._render()
            if self._popup is not None:
                self._popup.refresh()
            if before != self.checked():
                self.changed.emit(self.checked())
        if self._single:
            self.close_popup()

    def _set_all(self, checked: bool) -> None:
        """Compatibility helper used by older tests and callers."""
        if checked:
            self.select_all_visible()
        else:
            self.clear_visible()

    def display_tokens(self) -> tuple[list[str], int]:
        """Names shown in the trigger and how many are collapsed."""
        names = self.checked()
        if self._single:
            return names[:1], 0
        if len(names) <= 2:
            return names, 0
        return names[:2], len(names) - 2

    def _render(self) -> None:
        names = self.checked()
        self.setToolTip(", ".join(names) or self._placeholder)
        self.setAccessibleName(
            f"{self._label}: {len(names)} selected" if names else self._label
        )
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        content = QRect(6, 0, max(self.width() - 12, 0), self.height())
        painter.setClipRect(content)

        theme = get_theme_manager()
        text = QColor(theme.color("text_secondary", "#C6CDD5"))
        muted = QColor(theme.color("text_inactive", "#919BA6"))
        border = QColor(theme.color("border_primary", "#242A30"))
        fill = QColor(theme.color("background_secondary", "#191E22"))
        if not self.isEnabled():
            text = QColor(theme.color("text_disabled", "#5C6672"))
            muted = text

        token_font = QFont(self.font())
        token_font.setPixelSize(10)
        count_font = QFont(self.font())
        count_font.setPixelSize(9)
        chevron_font = QFont(self.font())
        chevron_font.setPixelSize(10)
        metrics = QFontMetrics(token_font)

        names = self.checked()
        chevron_w = 9
        chevron_x = content.right() - chevron_w + 1
        count_rect: QRect | None = None
        if names and not self._single:
            count_w = max(
                18, QFontMetrics(count_font).horizontalAdvance(str(len(names))) + 10
            )
            count_rect = QRect(
                chevron_x - 3 - count_w,
                (self.height() - 16) // 2,
                count_w,
                16,
            )
        right_x = count_rect.left() if count_rect is not None else chevron_x
        token_right = right_x - 3

        if not names:
            placeholder_font = QFont(self.font())
            placeholder_font.setPixelSize(11)
            painter.setFont(placeholder_font)
            painter.setPen(muted)
            label = QFontMetrics(placeholder_font).elidedText(
                self._placeholder,
                Qt.TextElideMode.ElideRight,
                max(token_right - content.left(), 10),
            )
            painter.drawText(
                QRect(
                    content.left(),
                    0,
                    max(token_right - content.left(), 10),
                    self.height(),
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
        else:
            visible = names[:1] if self._single else names[:2]
            overflow = len(names) - len(visible)
            available = max(token_right - content.left(), 10)
            more_text = f"+{overflow}" if overflow else ""
            more_w = (
                QFontMetrics(token_font).horizontalAdvance(more_text) + 3
                if overflow
                else 0
            )
            gaps = max(len(visible) - 1, 0) * 3 + (3 if overflow else 0)
            slots = max(len(visible), 1)
            slot = max((available - more_w - gaps) // slots, 0)
            if len(visible) > 1 and slot < 30:
                visible = visible[:1]
                overflow = len(names) - 1
                more_text = f"+{overflow}" if overflow else ""
                more_w = (
                    QFontMetrics(token_font).horizontalAdvance(more_text) + 3
                    if overflow
                    else 0
                )
                gaps = 3 if overflow else 0
                slot = max(available - more_w - gaps, 0)
            if slot < 8:
                visible = []
                overflow = len(names)
                more_text = f"+{overflow}" if overflow else ""
                more_w = (
                    QFontMetrics(token_font).horizontalAdvance(more_text) + 3
                    if overflow
                    else 0
                )

            x = content.left()
            for name in visible:
                natural = min(96, metrics.horizontalAdvance(name) + 10)
                width = min(natural, max(slot, 8))
                if x + width > token_right:
                    width = max(token_right - x, 0)
                if width < 8:
                    break
                rect = QRect(x, (self.height() - 20) // 2, width, 20)
                painter.setPen(QPen(border, 1))
                painter.setBrush(fill)
                painter.drawRoundedRect(rect, 3, 3)
                painter.setFont(token_font)
                painter.setPen(text)
                label = metrics.elidedText(
                    name, Qt.TextElideMode.ElideRight, max(width - 8, 2)
                )
                painter.drawText(
                    rect.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignCenter, label
                )
                x += width + 3
            if more_text and x + more_w <= token_right + 1:
                painter.setFont(token_font)
                painter.setPen(muted)
                painter.drawText(
                    QRect(x, 0, max(more_w, 1), self.height()),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    more_text,
                )

        if count_rect is not None:
            painter.setPen(QPen(border, 1))
            painter.setBrush(fill)
            painter.drawRoundedRect(count_rect, 3, 3)
            painter.setFont(count_font)
            painter.setPen(muted)
            painter.drawText(
                count_rect,
                Qt.AlignmentFlag.AlignCenter,
                str(len(names)),
            )

        painter.setFont(chevron_font)
        painter.setPen(muted)
        painter.drawText(
            QRect(chevron_x, 0, chevron_w, self.height()),
            Qt.AlignmentFlag.AlignCenter,
            "\u25b4" if self._is_open else "\u25be",
        )
        painter.end()

    def keyPressEvent(self, event) -> None:
        if (
            event.key()
            in (
                Qt.Key.Key_Down,
                Qt.Key.Key_Up,
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
                Qt.Key.Key_Space,
            )
            and not self._is_open
        ):
            self.open_popup()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape and self._is_open:
            self._escape()
            event.accept()
            return
        super().keyPressEvent(event)

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        if not enabled:
            self.close_popup()
