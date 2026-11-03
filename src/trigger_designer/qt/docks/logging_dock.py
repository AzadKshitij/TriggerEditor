"""Logs dock: one list of log lines and node problems.

The dock is a pure projection of the active document's
:class:`~trigger_designer.qt.helpers.diagnostic_feed.DiagnosticFeed`. It keeps
no records of its own, so a failure path can never write to the widget and miss
the feed, or the other way round.

The filter strip is Alteryx's Results strip: counted categories are the filter
*and* the count, the node name on a row is the link that centres that node, and
a segmented control at the right splits what the last run reported from what the
current configuration says.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from qtpy.QtCore import (
    QAbstractItemModel,
    QItemSelectionModel,
    QModelIndex,
    QPointF,
    QRect,
    QSize,
    Qt,
    QTimer,
)
from qtpy.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QShortcut,
)
from qtpy.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDockWidget,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.qt.helpers.diagnostic_feed import (
    CATEGORY_ALL,
    CATEGORY_CONV,
    CATEGORY_ERRORS,
    CATEGORY_MESSAGES,
    CATEGORY_WARNINGS,
    KIND_PROBLEM,
    ORIGIN_RUN,
    DiagnosticFeed,
    DiagnosticRecord,
)
from trigger_designer.qt.preferences import get_preferences
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.theme_manager import get_theme_manager
from trigger_designer.qt.widgets.common import (
    EmptyStateLabel,
    IconButton,
    SegmentedControl,
)

if TYPE_CHECKING:
    from trigger_designer.qt.design_window import TriggerSubWindow

#: The dock follows whichever document is active, so its title stays generic:
#: the file name belongs to the MDI window and the chrome row, not here.
_TITLE = "Logs"

_ROW_HEIGHT = 22
_DETAIL_LINE = 16
_TIME_WIDTH = 62
_NODE_MAX = 170
_PAD = 6
_GLYPH = 12

_MODE_LAST_RUN = "Last Run"
_MODE_CONFIGURATION = "Configuration"

_CATEGORY_LABELS = {
    CATEGORY_ALL: "All",
    CATEGORY_ERRORS: "Errors",
    CATEGORY_CONV: "Conv",
    CATEGORY_WARNINGS: "Warnings",
    CATEGORY_MESSAGES: "Messages",
}

_CATEGORY_TOOLTIPS = {
    CATEGORY_ALL: "Every log line and problem",
    CATEGORY_ERRORS: "Errors, excluding type-conversion failures",
    CATEGORY_CONV: "Type-conversion failures (TD-TYP)",
    CATEGORY_WARNINGS: "Warnings",
    CATEGORY_MESSAGES: "Log messages",
}


class DiagnosticModel(QAbstractItemModel):
    """Flat model over the feed's records, one row per record."""

    RecordRole = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._records: list[DiagnosticRecord] = []
        self._expanded: set[int] = set()

    # -- QAbstractItemModel ----------------------------------------------
    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._records)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return 1

    def index(
        self, row: int, column: int = 0, parent: QModelIndex | None = None
    ) -> QModelIndex:
        if (parent is not None and parent.isValid()) or column != 0:
            return QModelIndex()
        if not 0 <= row < len(self._records):
            return QModelIndex()
        return self.createIndex(row, column, None)

    def parent(self, index: QModelIndex) -> QModelIndex:
        return QModelIndex()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._records):
            return None
        record = self._records[index.row()]
        if role == self.RecordRole:
            return record
        if role == Qt.ItemDataRole.DisplayRole:
            return record.message
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(record)
        return None

    @staticmethod
    def _tooltip(record: DiagnosticRecord) -> str:
        if record.error is not None:
            return record.error.render_tooltip()
        return f"{record.level}: {record.message}"

    # -- projection -------------------------------------------------------
    def set_records(self, records: Iterable[DiagnosticRecord]) -> None:
        """Replace the projection, keeping the view when only payloads changed."""
        records = list(records)
        old = [record.seq for record in self._records]
        new = [record.seq for record in records]
        if old == new:
            self._records = records
            if records:
                self.dataChanged.emit(self.index(0, 0), self.index(len(records) - 1, 0))
            return
        self.beginResetModel()
        self._records = records
        live = {record.seq for record in records}
        self._expanded &= live
        self.endResetModel()

    def record_at(self, row: int) -> DiagnosticRecord | None:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    def row_for_seq(self, seq: int) -> int:
        for row, record in enumerate(self._records):
            if record.seq == seq:
                return row
        return -1

    def records(self) -> list[DiagnosticRecord]:
        return list(self._records)

    # -- expansion --------------------------------------------------------
    def is_expanded(self, seq: int) -> bool:
        return seq in self._expanded

    def clear_expanded(self) -> None:
        """Drop expansion state; called when the dock follows another document."""
        if not self._expanded:
            return
        self.layoutAboutToBeChanged.emit()
        self._expanded.clear()
        self.layoutChanged.emit()

    def set_expanded(self, seq: int, expanded: bool) -> None:
        if expanded:
            self._expanded.add(seq)
        else:
            self._expanded.discard(seq)
        row = self.row_for_seq(seq)
        if row >= 0:
            # A height change is a layout change, not just a repaint.
            self.layoutAboutToBeChanged.emit()
            self.layoutChanged.emit()


class DiagnosticDelegate(QStyledItemDelegate):
    """Paints one record per row: glyph, time, node link, message."""

    def __init__(self, view: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent or view)
        self._view = view
        self._technical = False
        self._colors: dict[str, QColor] = {}
        self.refresh_colors()

    def refresh_colors(self) -> None:
        manager = get_theme_manager()
        self._colors = {
            "time": QColor(manager.color("text_tertiary", "#919ba6")),
            "message": QColor(manager.color("text_secondary", "#c6cdd5")),
            "link": QColor(manager.color("accent_secondary", "#6a96d7")),
            "muted": QColor(manager.color("text_inactive", "#919ba6")),
            "error": QColor(manager.color("danger", "#e0686c")),
            "warning": QColor(manager.color("warning", "#d9a441")),
            "info": QColor(manager.color("info", "#5ba8d6")),
            "selected": QColor(manager.color("accent_primary", "#5680c2")),
            "selected_text": QColor(manager.color("selection_color", "#ffffff")),
            "editor": QColor(manager.color("editor_background", "#101418")),
        }

    def set_technical(self, enabled: bool) -> None:
        self._technical = enabled

    # -- metrics ----------------------------------------------------------
    @staticmethod
    def _detail_lines(record: DiagnosticRecord, technical: bool) -> list[str]:
        error = record.error
        if error is None:
            return []
        lines: list[str] = []
        if error.hint:
            lines.append(f"{error.code}  Fix: {error.hint}")
        else:
            lines.append(error.code)
        if error.culprit_node_id is not None:
            culprit = error.culprit_node_title or f"node {error.culprit_node_id}"
            lines.append(f"Caused by: {culprit} (node {error.culprit_node_id})")
        if technical and (error.technical or error.traceback):
            raw = (error.technical or error.traceback).strip().splitlines()
            if raw:
                lines.append(raw[0])
        return lines

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        record: DiagnosticRecord | None = index.data(DiagnosticModel.RecordRole)
        if record is None:
            return QSize(0, _ROW_HEIGHT)
        model = index.model()
        expanded = isinstance(model, DiagnosticModel) and model.is_expanded(record.seq)
        if record.kind == KIND_PROBLEM and expanded:
            extra = len(self._detail_lines(record, self._technical))
            return QSize(0, _ROW_HEIGHT + extra * _DETAIL_LINE + 2)
        return QSize(0, _ROW_HEIGHT)

    # -- painting ---------------------------------------------------------
    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        record: DiagnosticRecord | None = index.data(DiagnosticModel.RecordRole)
        if record is None:
            return
        painter.save()
        painter.setClipRect(option.rect)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            painter.fillRect(option.rect, self._colors["selected"])

        row = QRect(option.rect)
        row.setHeight(_ROW_HEIGHT)
        text_color = (
            self._colors["selected_text"] if selected else self._colors["message"]
        )

        x = row.left() + _PAD
        self._paint_glyph(
            painter,
            QRect(x, row.top() + (_ROW_HEIGHT - _GLYPH) // 2, _GLYPH, _GLYPH),
            record,
        )
        x += _GLYPH + 6

        painter.setPen(
            self._colors["selected_text"] if selected else self._colors["time"]
        )
        painter.drawText(
            QRect(x, row.top(), _TIME_WIDTH, _ROW_HEIGHT),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            record.first_seen.astimezone().strftime("%H:%M:%S"),
        )
        x += _TIME_WIDTH + 4

        if record.kind == KIND_PROBLEM and record.node_label:
            label = record.node_label
            metrics = painter.fontMetrics()
            advance = metrics.horizontalAdvance(label)
            width = min(advance, _NODE_MAX)
            drawn = (
                label
                if advance <= _NODE_MAX
                else metrics.elidedText(label, Qt.TextElideMode.ElideRight, _NODE_MAX)
            )
            painter.setPen(
                self._colors["selected_text"] if selected else self._colors["link"]
            )
            painter.drawText(
                QRect(x, row.top(), width, _ROW_HEIGHT),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                drawn,
            )
            x += width + 4
            if record.error is not None and record.error.node_id is not None:
                suffix = f"({record.error.node_id})"
                painter.setPen(
                    self._colors["selected_text"] if selected else self._colors["muted"]
                )
                painter.drawText(
                    QRect(x, row.top(), 70, _ROW_HEIGHT),
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                    suffix,
                )
                x += painter.fontMetrics().horizontalAdvance(suffix) + 6
            else:
                x += 6

        message = record.message or (record.error.title if record.error else "")
        painter.setPen(text_color)
        chevron = record.kind == KIND_PROBLEM
        right = row.right() - (_PAD + 14 if chevron else _PAD)
        painter.drawText(
            QRect(x + 6, row.top(), max(0, right - x - 6), _ROW_HEIGHT),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            painter.fontMetrics().elidedText(
                message, Qt.TextElideMode.ElideRight, max(0, right - x - 6)
            ),
        )

        if chevron:
            self._paint_chevron(painter, row, record, selected)

        model = index.model()
        if (
            record.kind == KIND_PROBLEM
            and isinstance(model, DiagnosticModel)
            and model.is_expanded(record.seq)
        ):
            self._paint_details(painter, row, record, selected)
        painter.restore()

    def _paint_details(
        self,
        painter: QPainter,
        row: QRect,
        record: DiagnosticRecord,
        selected: bool,
    ) -> None:
        lines = self._detail_lines(record, self._technical)
        top = row.bottom() + 2
        painter.setPen(
            self._colors["selected_text"] if selected else self._colors["muted"]
        )
        for offset, line in enumerate(lines):
            rect = QRect(
                row.left() + _PAD + _GLYPH + 6,
                top + offset * _DETAIL_LINE,
                row.width() - _PAD * 2 - _GLYPH - 6,
                _DETAIL_LINE,
            )
            painter.drawText(
                rect,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                painter.fontMetrics().elidedText(
                    line, Qt.TextElideMode.ElideRight, rect.width()
                ),
            )

    def _paint_chevron(
        self,
        painter: QPainter,
        row: QRect,
        record: DiagnosticRecord,
        selected: bool,
    ) -> None:
        model = self._view.model()
        expanded = isinstance(model, DiagnosticModel) and model.is_expanded(record.seq)
        painter.setPen(
            QPen(
                self._colors["selected_text"] if selected else self._colors["muted"],
                1.2,
            )
        )
        cx = row.right() - _PAD - 4
        cy = row.top() + _ROW_HEIGHT // 2
        path = QPainterPath()
        if expanded:
            path.moveTo(cx - 4, cy - 2)
            path.lineTo(cx, cy + 3)
            path.lineTo(cx + 4, cy - 2)
        else:
            path.moveTo(cx - 2, cy - 4)
            path.lineTo(cx + 3, cy)
            path.lineTo(cx - 2, cy + 4)
        painter.drawPath(path)

    def _paint_glyph(
        self, painter: QPainter, rect: QRect, record: DiagnosticRecord
    ) -> None:
        severity = record.severity
        if severity in ("error", "critical"):
            color = self._colors["error"]
        elif severity == "warning":
            color = self._colors["warning"]
        elif severity == "info":
            color = self._colors["info"]
        else:
            color = self._colors["muted"]

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        cx = rect.center().x()
        cy = rect.center().y()

        if severity in ("error", "critical"):
            painter.drawEllipse(QPointF(cx, cy), 6, 6)
            painter.setBrush(self._colors["editor"])
            painter.drawRect(cx - 1, cy - 4, 2, 5)
            painter.drawEllipse(QPointF(cx, cy + 3), 1, 1)
        elif severity == "warning":
            path = QPainterPath()
            path.moveTo(cx, cy - 6)
            path.lineTo(cx + 6, cy + 5)
            path.lineTo(cx - 6, cy + 5)
            path.closeSubpath()
            painter.drawPath(path)
            painter.setBrush(self._colors["editor"])
            painter.drawRect(cx - 1, cy - 3, 2, 4)
            painter.drawEllipse(QPointF(cx, cy + 3), 1, 1)
        elif severity == "info":
            painter.drawEllipse(QPointF(cx, cy), 5, 5)
            painter.setBrush(self._colors["editor"])
            painter.drawEllipse(QPointF(cx, cy), 2, 2)
        elif severity in ("debug",):
            painter.drawRect(cx - 4, cy - 4, 8, 8)
        else:
            painter.drawEllipse(QPointF(cx, cy), 2, 2)
        painter.restore()


class _DiagnosticTree(QTreeView):
    """Tree view that turns Return into the jump and Space into expansion."""

    def __init__(self, dock: LoggingDock, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dock = dock

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._dock.jump_to_current()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Space:
            self._dock.toggle_current()
            event.accept()
            return
        super().keyPressEvent(event)


class LoggingDock(QDockWidget):
    """One list for log lines and node problems, following the active document."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_TITLE, parent)
        self.setObjectName("LoggingDock")

        self._window: TriggerSubWindow | None = None
        self._feed: DiagnosticFeed | None = None
        self._category = CATEGORY_ALL
        self._mode = _MODE_CONFIGURATION
        self._needle = ""
        self._records: list[DiagnosticRecord] = []

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(0)
        self._refresh_timer.timeout.connect(self.refresh)

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(300)
        self._filter_timer.timeout.connect(self._on_filter_settled)

        self._build()
        self._apply_log_font()
        self.refresh()

    # -- construction -----------------------------------------------------
    def _build(self) -> None:
        panel = QWidget(self)
        panel.setObjectName("LoggingDockWidget")
        panel.setMinimumWidth(400)
        panel.setMinimumHeight(200)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        toolbar = QWidget(panel)
        toolbar.setObjectName("LoggingToolbar")
        toolbar.setFixedHeight(40)
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(2)

        self._chips: dict[str, QPushButton] = {}
        self._chip_group = QButtonGroup(self)
        self._chip_group.setExclusive(True)
        for category in (
            CATEGORY_ALL,
            CATEGORY_ERRORS,
            CATEGORY_CONV,
            CATEGORY_WARNINGS,
            CATEGORY_MESSAGES,
        ):
            button = QPushButton(_CATEGORY_LABELS[category], toolbar)
            button.setObjectName("DiagnosticCount")
            button.setCheckable(True)
            button.setFixedHeight(30)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(_CATEGORY_TOOLTIPS[category])
            button.setAccessibleName(_CATEGORY_TOOLTIPS[category])
            button.clicked.connect(
                lambda _checked=False, value=category: self.set_category(value)
            )
            self._chip_group.addButton(button)
            self._chips[category] = button
            bar.addWidget(button)
        self._chips[CATEGORY_ALL].setChecked(True)
        bar.addStretch(1)

        self.search = QLineEdit(toolbar)
        self.search.setObjectName("DiagnosticSearch")
        self.search.setPlaceholderText("Filter messages and problems")
        self.search.setMinimumHeight(30)
        self.search.setMinimumWidth(140)
        self.search.setMaximumWidth(220)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_timer.start)
        self.search.hide()
        bar.addWidget(self.search)

        resources = ResourceManager()
        self.copy_button = IconButton.themed(
            "Copy details",
            rsm_icon=resources.get("icon_copy"),
            parent=toolbar,
        )
        self.copy_button.clicked.connect(self._copy_details)
        bar.addWidget(self.copy_button)

        self.technical_button = IconButton.themed(
            "Show technical details",
            rsm_icon=resources.get("icon_technical"),
            parent=toolbar,
        )
        self.technical_button.setCheckable(True)
        self.technical_button.setChecked(
            bool(get_preferences().get("errors/show_technical", False))
        )
        self.technical_button.setAccessibleName("Technical details")
        self.technical_button.toggled.connect(self._on_technical_toggled)
        bar.addWidget(self.technical_button)

        self.clear_button = IconButton.themed(
            "Clear log messages",
            rsm_icon=resources.get("icon_clear"),
            parent=toolbar,
        )
        self.clear_button.clicked.connect(self.clear_logs)
        bar.addWidget(self.clear_button)

        self.follow_button = IconButton.themed(
            "Follow new entries",
            rsm_icon=resources.get("icon_follow"),
            parent=toolbar,
        )
        self.follow_button.setCheckable(True)
        self.follow_button.setChecked(True)
        self.follow_button.setAccessibleName("Follow new entries")
        bar.addWidget(self.follow_button)

        self.mode = SegmentedControl(
            [_MODE_LAST_RUN, _MODE_CONFIGURATION],
            current=_MODE_CONFIGURATION,
            parent=toolbar,
        )
        self.mode.changed.connect(self._on_mode_changed)
        bar.addWidget(self.mode)

        layout.addWidget(toolbar)

        self.model = DiagnosticModel(self)
        self.tree = _DiagnosticTree(self, panel)
        self.tree.setObjectName("DiagnosticTree")
        self.tree.setModel(self.model)
        self.tree.setRootIsDecorated(False)
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(False)
        self.tree.setAllColumnsShowFocus(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setWordWrap(False)
        self.tree.setMouseTracking(True)
        self.delegate = DiagnosticDelegate(self.tree)
        self.delegate.set_technical(self.technical_button.isChecked())
        self.tree.setItemDelegate(self.delegate)
        self.tree.clicked.connect(self._on_clicked)
        self.tree.doubleClicked.connect(self._on_double_clicked)
        layout.addWidget(self.tree, 1)

        self.empty = EmptyStateLabel("No messages yet", panel)
        layout.addWidget(self.empty)

        self.setWidget(panel)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

        find_shortcut = QShortcut(
            QKeySequence.StandardKey.Find, self, self._focus_search
        )
        find_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        copy_shortcut = QShortcut(
            QKeySequence.StandardKey.Copy, self.tree, self._copy_details
        )
        copy_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        escape_shortcut = QShortcut(
            QKeySequence(Qt.Key.Key_Escape), self.search, self._close_search
        )
        escape_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)

    def _apply_log_font(self) -> None:
        scale = get_theme_manager().font_scale()
        font = QFont("Consolas", round(9 * scale))
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.tree.setFont(font)

    # -- follow the active document ---------------------------------------
    def switch_to_design_window(self, design_window: TriggerSubWindow | None) -> None:
        old = self._feed
        if old is not None:
            try:
                old.changed.disconnect(self._schedule_refresh)
            except TypeError, RuntimeError:
                pass
        self._window = design_window
        self._feed = getattr(design_window, "diagnostics", None)
        if self._feed is not None:
            self._feed.changed.connect(self._schedule_refresh)
        self.model.clear_expanded()
        self.setWindowTitle(_TITLE)
        self.refresh()

    def remove_design_window(self, design_window_id: str) -> None:
        if self._window is not None and str(id(self._window)) == design_window_id:
            self.switch_to_design_window(None)

    def _schedule_refresh(self) -> None:
        self._refresh_timer.start()

    # -- filtering --------------------------------------------------------
    def set_category(self, category: str) -> None:
        if category not in self._chips:
            category = CATEGORY_ALL
        self._category = category
        button = self._chips[category]
        if not button.isChecked():
            button.setChecked(True)
        self.refresh()

    def set_mode(self, mode: str) -> None:
        if mode not in (_MODE_LAST_RUN, _MODE_CONFIGURATION):
            mode = _MODE_CONFIGURATION
        self._mode = mode
        self.mode.set_value(mode)
        self.refresh()

    def _on_mode_changed(self, value: str) -> None:
        self._mode = value
        self.refresh()

    def _focus_search(self) -> None:
        self.search.show()
        self.search.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search.selectAll()

    def _close_search(self) -> None:
        self.search.clear()
        self.search.hide()
        self.tree.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_filter_settled(self) -> None:
        self._needle = self.search.text().strip().casefold()
        self.refresh()

    def _on_technical_toggled(self, checked: bool) -> None:
        get_preferences().set("errors/show_technical", bool(checked))
        self.delegate.set_technical(bool(checked))
        self.tree.viewport().update()

    def _mode_matches(self, record: DiagnosticRecord) -> bool:
        if record.kind != KIND_PROBLEM:
            # A log line has no phase: it is the stream, and it stays visible in
            # both modes so the toggle never hides what the document said.
            return True
        if self._mode == _MODE_LAST_RUN:
            return record.source == ORIGIN_RUN
        return record.source != ORIGIN_RUN

    def _category_matches(self, record: DiagnosticRecord) -> bool:
        return self._category == CATEGORY_ALL or record.category == self._category

    def _needle_matches(self, record: DiagnosticRecord) -> bool:
        return not self._needle or self._needle in record.searchable.casefold()

    # -- refresh ----------------------------------------------------------
    def refresh(self) -> None:
        feed = self._feed
        records = feed.records() if feed is not None else []
        records = [record for record in records if self._mode_matches(record)]
        self._update_counts(records)
        visible = [
            record
            for record in records
            if self._category_matches(record) and self._needle_matches(record)
        ]
        self._records = visible

        scrollbar = self.tree.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 2
        selected = {
            record.seq
            for index in self.tree.selectionModel().selectedRows()
            if (record := self.model.record_at(index.row())) is not None
        }

        self.model.set_records(visible)

        if selected:
            selection = self.tree.selectionModel()
            flags = (
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows
            )
            first = (
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows
            )
            rows = [self.model.row_for_seq(seq) for seq in selected]
            for position, row in enumerate(row for row in rows if row >= 0):
                selection.select(
                    self.model.index(row, 0), first if position == 0 else flags
                )

        if self.follow_button.isChecked() and at_bottom:
            self.tree.scrollToBottom()

        has_rows = bool(visible)
        self.tree.setVisible(has_rows)
        self.empty.setVisible(not has_rows)
        self.empty.setText(self._empty_text())

    def _empty_text(self) -> str:
        if self._needle:
            return "Nothing matches this filter"
        if self._category == CATEGORY_MESSAGES:
            return "No messages yet"
        if self._mode == _MODE_LAST_RUN:
            return "The last run reported nothing"
        return "No problems"

    def _update_counts(self, records: list[DiagnosticRecord]) -> None:
        counts = {
            CATEGORY_ALL: len(records),
            CATEGORY_ERRORS: 0,
            CATEGORY_CONV: 0,
            CATEGORY_WARNINGS: 0,
            CATEGORY_MESSAGES: 0,
        }
        for record in records:
            counts[record.category] += 1
        for category, button in self._chips.items():
            count = counts[category]
            if category == CATEGORY_ALL:
                button.setText(_CATEGORY_LABELS[category])
            else:
                button.setText(f"{count} {_CATEGORY_LABELS[category]}")
            if button.property("zero") != (count == 0):
                button.setProperty("zero", count == 0)
                button.style().unpolish(button)
                button.style().polish(button)

    # -- row actions ------------------------------------------------------
    def _record_for_index(self, index: QModelIndex) -> DiagnosticRecord | None:
        if not index.isValid():
            return None
        return self.model.record_at(index.row())

    def _on_clicked(self, index: QModelIndex) -> None:
        record = self._record_for_index(index)
        if record is None or record.kind != KIND_PROBLEM:
            return
        self.jump_to_node(record)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        record = self._record_for_index(index)
        if record is None or record.kind != KIND_PROBLEM:
            return
        self.model.set_expanded(record.seq, not self.model.is_expanded(record.seq))

    def jump_to_current(self) -> None:
        record = self._record_for_index(self.tree.currentIndex())
        if record is not None:
            self.jump_to_node(record)

    def toggle_current(self) -> None:
        record = self._record_for_index(self.tree.currentIndex())
        if record is not None and record.kind == KIND_PROBLEM:
            self.model.set_expanded(record.seq, not self.model.is_expanded(record.seq))

    def jump_to_node(self, record: DiagnosticRecord) -> None:
        """Select the record's node and centre the canvas on it."""
        error = record.error
        window = self._window
        if error is None or error.node_id is None or window is None:
            return
        node = next(
            (item for item in window.getAllNodes() if item.id == error.node_id),
            None,
        )
        if node is None:
            return
        window.scene.doDeselectItems()
        node.grNode.setSelected(True)
        view = window.scene.getView()
        if view is not None:
            view.centerOn(node.grNode)

    def _copy_details(self) -> None:
        selected: list[DiagnosticRecord] = []
        seen: set[int] = set()
        for index in self.tree.selectionModel().selectedRows():
            record = self.model.record_at(index.row())
            if record is not None and record.seq not in seen:
                seen.add(record.seq)
                selected.append(record)

        problems = [record for record in selected if record.kind == KIND_PROBLEM]
        log_lines = [record for record in selected if record.kind != KIND_PROBLEM]

        if problems or log_lines:
            rows = problems or log_lines
        else:
            rows = [record for record in self._records if record.kind == KIND_PROBLEM]
            if not rows:
                rows = self._records

        if rows and rows[0].kind == KIND_PROBLEM:
            technical = self.technical_button.isChecked()
            text = "\n\n".join(
                record.error.render_text(include_technical=technical)
                for record in rows
                if record.error is not None
            )
        else:
            text = "\n".join(
                f"{record.first_seen.astimezone():%H:%M:%S} {record.level} {record.message}"
                for record in rows
            )
        if text:
            QGuiApplication.clipboard().setText(text)

    def clear_logs(self) -> None:
        """Clear log lines only; live problems are not the user's to delete."""
        if self._feed is not None:
            self._feed.clear_logs()
            return
        self.refresh()

    # -- run integration --------------------------------------------------
    def show_last_run(self, *, only_errors: bool = False) -> None:
        """Show what the last run reported, optionally narrowed to errors."""
        self.set_mode(_MODE_LAST_RUN)
        if only_errors:
            self.set_category(CATEGORY_ERRORS)

    def apply_theme(self) -> None:
        self._apply_log_font()
        self.delegate.refresh_colors()
        self.tree.viewport().update()
        self.tree.update()
