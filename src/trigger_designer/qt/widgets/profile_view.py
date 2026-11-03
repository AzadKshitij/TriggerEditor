"""Data Profile dock view (plan 05): column table, detail pane, export buttons.

The text helpers (``detail_rows``, ``status_text``, ``chart_for`` ...) are plain
functions over ``ColumnProfile``/``DataProfile`` so they can be tested without a
widget. The view never mutates the node; it only shows a finished profile.
"""

from __future__ import annotations

import atexit
import os
import tempfile
from html import escape
from typing import Any

from qtpy.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QRectF,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from qtpy.QtGui import QDesktopServices, QPainter
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.profile import (
    ColumnProfile,
    DataProfile,
    profile_to_tsv,
    write_profile_xlsx,
)
from trigger_designer.core.profile_report import (
    FLAG_LABELS,  # noqa: F401 - re-exported for callers and tests
    chart_for,
    detail_rows,
    distinct_text,
    flag_labels,
    flags_text,
    has_warning,
    profile_to_html,
    status_text,
    suggested_text,
)
from trigger_designer.qt.theme_manager import get_theme_manager
from trigger_designer.qt.widgets.common import EmptyStateLabel
from trigger_designer.qt.widgets.common.config_widgets import Chip, IconButton

HEADERS = ("Column", "Type", "Null %", "Distinct", "Suggested", "Flags")
#: Starting widths in pixels; the user can drag any divider.
COLUMN_WIDTHS = (112, 58, 92, 64, 76, 150)
NULL_COLUMN = 2
SORT_ROLE = Qt.ItemDataRole.UserRole
SEARCH_DEBOUNCE_MS = 300


def sort_value(cp: ColumnProfile, column: int) -> Any:
    """What a header click orders by, per visible column."""
    if column == 0:
        return cp.name.casefold()
    if column == 1:
        return cp.dtype
    if column == NULL_COLUMN:
        return cp.null_pct
    if column == 3:
        return -1 if cp.distinct_count is None else cp.distinct_count
    if column == 4:
        return suggested_text(cp)
    return len(cp.flags)


#: Reports written for "Full report"; removed when the application exits.
_TEMP_REPORTS: list[str] = []


def _remove_temp_reports() -> None:
    for path in _TEMP_REPORTS:
        try:
            os.remove(path)
        except OSError:
            continue


atexit.register(_remove_temp_reports)


# ---- table ----------------------------------------------------------------
class ProfileTableModel(QAbstractTableModel):
    """Six visible columns over a list of ``ColumnProfile``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._columns: list[ColumnProfile] = []

    def set_columns(self, columns: list[ColumnProfile]) -> None:
        self.beginResetModel()
        self._columns = list(columns)
        self.endResetModel()

    def column_at(self, row: int) -> ColumnProfile | None:
        return self._columns[row] if 0 <= row < len(self._columns) else None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._columns)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        cp = self.column_at(index.row())
        if cp is None:
            return None
        column = index.column()
        if role == SORT_ROLE:
            return sort_value(cp, column)
        if role == Qt.ItemDataRole.DisplayRole:
            return (
                cp.name,
                cp.dtype,
                f"{cp.null_pct:.1f}%",
                distinct_text(cp),
                suggested_text(cp),
                flags_text(cp),
            )[column]
        if role == Qt.ItemDataRole.TextAlignmentRole and column == 3:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole and column == 5:
            token = "warning" if has_warning(cp) else "text_secondary"
            return get_theme_manager().color(token)
        if role == Qt.ItemDataRole.ToolTipRole and column == 5 and cp.flags:
            return "\n".join(flag_labels(cp))
        return None


class NullBarDelegate(QStyledItemDelegate):
    """Paints the null share as a small bar followed by its percentage."""

    BAR_W = 36
    BAR_H = 6

    def sizeHint(self, option, index) -> QSize:
        return QSize(92, 22)

    def paint(self, painter: QPainter, option, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget
        )
        pct = float(index.data(SORT_ROLE) or 0.0)
        theme = get_theme_manager()
        track = QRectF(
            opt.rect.left() + 6,
            opt.rect.center().y() - self.BAR_H / 2,
            self.BAR_W,
            self.BAR_H,
        )
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.color("border_subtle"))
        painter.drawRoundedRect(track, 2, 2)
        if pct > 0:
            fill = QRectF(track)
            fill.setWidth(max(2.0, track.width() * min(pct, 100.0) / 100.0))
            painter.setBrush(theme.color("danger" if pct >= 100.0 else "warning"))
            painter.drawRoundedRect(fill, 2, 2)
        painter.setPen(theme.color("text_primary"))
        text_rect = QRectF(
            track.right() + 6,
            opt.rect.top(),
            opt.rect.right() - track.right() - 8,
            opt.rect.height(),
        )
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            f"{pct:.1f}%",
        )
        painter.restore()


class MiniBarChart(QWidget):
    """A painted histogram (``hist``) or frequency list (``freq``); no plotting library."""

    ROW_H = 18

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MiniBarChart")
        self.kind = ""
        self._labels: list[str] = []
        self._values: list[int] = []
        self._captions: tuple[str, str] = ("", "")
        self.setMinimumHeight(24)

    def set_bars(
        self,
        labels: list[str],
        values: list[int],
        kind: str,
        captions: tuple[str, str] = ("", ""),
    ) -> None:
        self._labels, self._values = list(labels), list(values)
        self.kind = kind if values else ""
        self._captions = captions
        if self.kind == "freq":
            self.setMinimumHeight(self.ROW_H * len(values) + 4)
        elif self.kind == "hist":
            self.setMinimumHeight(96)
        else:
            self.setMinimumHeight(24)
        self.update()

    def clear(self) -> None:
        self.set_bars([], [], "")

    def paintEvent(self, _event) -> None:
        if not self._values:
            return
        theme = get_theme_manager()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        biggest = max(self._values) or 1
        if self.kind == "hist":
            self._paint_hist(painter, theme, biggest)
        else:
            self._paint_freq(painter, theme, biggest)
        painter.end()

    def _paint_hist(self, painter: QPainter, theme, biggest: int) -> None:
        caption_h = 16
        area_h = max(1, self.height() - caption_h - 2)
        count = len(self._values)
        gap = 2.0
        bar_w = max(1.0, (self.width() - gap * (count - 1)) / count)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.color("accent_primary"))
        for i, value in enumerate(self._values):
            height = max(2.0, area_h * value / biggest) if value else 0.0
            painter.drawRect(QRectF(i * (bar_w + gap), area_h - height, bar_w, height))
        painter.setPen(theme.color("text_secondary"))
        low, high = self._captions
        painter.drawText(
            QRectF(0, area_h + 2, self.width() / 2, caption_h),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            low,
        )
        painter.drawText(
            QRectF(self.width() / 2, area_h + 2, self.width() / 2, caption_h),
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            high,
        )

    def _paint_freq(self, painter: QPainter, theme, biggest: int) -> None:
        label_w = max(60, int(self.width() * 0.34))
        count_w = 56
        track_x = label_w + 6
        track_w = max(10, self.width() - track_x - count_w - 6)
        for i, (label, value) in enumerate(zip(self._labels, self._values)):
            top = i * self.ROW_H
            painter.setPen(theme.color("text_primary"))
            metrics = painter.fontMetrics()
            painter.drawText(
                QRectF(0, top, label_w, self.ROW_H),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                metrics.elidedText(
                    label or "(empty)", Qt.TextElideMode.ElideRight, label_w
                ),
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.color("border_subtle"))
            painter.drawRoundedRect(QRectF(track_x, top + 6, track_w, 6), 2, 2)
            painter.setBrush(theme.color("accent_primary"))
            painter.drawRoundedRect(
                QRectF(track_x, top + 6, max(2.0, track_w * value / biggest), 6), 2, 2
            )
            painter.setPen(theme.color("text_secondary"))
            painter.drawText(
                QRectF(self.width() - count_w, top, count_w, self.ROW_H),
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                f"{value:,}",
            )


# ---- the view -------------------------------------------------------------
class ProfileDockView(QWidget):
    """Toolbar, state chip, sortable column table and a detail pane."""

    #: The Config Dock sweep binds every control it finds to the undo stack;
    #: nothing in here (search text, sort, selection) is document state.
    _undo_composite = True

    recomputeRequested = Signal()

    def __init__(self, rsm: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProfileDockView")
        self.state = "loading"
        self.source = "live"
        #: Heading of the HTML report; the node sets it to its own title.
        self.report_title = "Data profile"
        self._profile: DataProfile | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(2)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter columns")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(30)
        self.search.setAccessibleName("Filter columns")
        toolbar.addWidget(self.search, 1)
        self.report_button = IconButton.themed(
            "Open the full report (every column) in your browser",
            rsm.get("icon_report"),
        )
        self.export_button = IconButton.themed("Export profile", rsm.get("icon_save"))
        self.export_menu = QMenu(self.export_button)
        self.copy_action = self.export_menu.addAction("Copy to clipboard")
        self.csv_action = self.export_menu.addAction("CSV file...")
        self.html_action = self.export_menu.addAction("HTML report...")
        self.excel_action = self.export_menu.addAction("Excel workbook...")
        self.export_button.setMenu(self.export_menu)
        self.refresh_button = IconButton.themed(
            "Recompute profile", rsm.get("icon_refresh")
        )
        for button in (self.report_button, self.export_button, self.refresh_button):
            toolbar.addWidget(button)
        root.addLayout(toolbar)

        self.notice = Chip("Profiling...", "accent")
        root.addWidget(self.notice, 0, Qt.AlignmentFlag.AlignLeft)

        self.model = ProfileTableModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.proxy.setFilterKeyColumn(0)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.table = QTableView()
        self.table.setObjectName("ColumnTable")
        self.table.setModel(self.proxy)
        self.table.setItemDelegateForColumn(NULL_COLUMN, NullBarDelegate(self.table))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        # Start in the input's column order; a header click sorts from there.
        self.table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        # Fixed starting widths, not size-to-contents: on a CSV every Type cell
        # reads "String", and contents-sizing would starve Flags, the column an
        # auditor reads first. The last column takes whatever width is left.
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(48)
        for column, width in enumerate(COLUMN_WIDTHS):
            self.table.setColumnWidth(column, width)
        self.table.setMinimumHeight(160)
        self.table.setAccessibleName("Column profile")
        root.addWidget(self.table, 3)

        self.detail_title = QLabel("")
        self.detail_title.setObjectName("FieldHint")
        self.chart = MiniBarChart()
        self.detail_stats = QLabel("")
        self.detail_stats.setTextFormat(Qt.TextFormat.RichText)
        self.detail_stats.setWordWrap(True)
        self.detail_stats.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.empty_note = EmptyStateLabel("No columns")
        self.empty_note.hide()
        root.addWidget(self.detail_title)
        root.addWidget(self.chart)
        root.addWidget(self.detail_stats)
        root.addWidget(self.empty_note)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._apply_filter)
        self.search.textChanged.connect(lambda _text: self._search_timer.start())
        self.table.selectionModel().currentRowChanged.connect(self._on_row_changed)
        self.report_button.clicked.connect(self.open_full_report)
        self.copy_action.triggered.connect(self.copy_profile)
        self.csv_action.triggered.connect(self.export_csv)
        self.html_action.triggered.connect(self.export_html)
        self.excel_action.triggered.connect(self.export_excel)
        self.refresh_button.clicked.connect(self.recomputeRequested.emit)

    # ---- states ----------------------------------------------------------
    def set_profile(
        self, profile: DataProfile, source: str = "live", run_time: str = ""
    ) -> None:
        """Show ``profile``; ``source`` is ``"live"`` (canvas preview) or ``"run"``."""
        self._profile = profile
        self.source = source
        self.state = "ready"
        self.model.set_columns(profile.columns)
        empty = not profile.columns
        self.table.setVisible(not empty)
        self.empty_note.setText("No columns")
        self.empty_note.setVisible(empty)
        self._set_notice(status_text(profile), "accent" if profile.sampled else "muted")
        self.notice.setToolTip(
            f"Result of the workflow run{f' at {run_time}' if run_time else ''}"
            if source == "run"
            else "Live preview of the rows the canvas holds (the first 100). "
            "Run the workflow to profile all rows."
        )
        if profile.columns:
            self.table.selectRow(0)
            self._show_detail(profile.columns[0])
        else:
            self._clear_detail()

    def set_skipped(self, message: str) -> None:
        """Show no table, only ``message`` (the live preview was not computed)."""
        self._profile = None
        self.state = "skipped"
        self.source = "live"
        self.model.set_columns([])
        self.table.setVisible(False)
        self.empty_note.setText(message)
        self.empty_note.setVisible(True)
        self._set_notice("Live preview skipped", "muted")
        self.notice.setToolTip(message)
        self._clear_detail()

    def set_failed(self, message: str) -> None:
        self.state = "failed"
        self._set_notice(f"Profile failed: {message}", "warning")

    def set_message(self, message: str) -> None:
        """A one-off status (export result) in the chip; the table is unchanged."""
        tone = "warning" if message.startswith("Export failed") else "accent"
        self._set_notice(message, tone)

    def _set_notice(self, text: str, tone: str) -> None:
        self.notice.setText(text)
        self.notice.setProperty("tone", tone)
        self.notice.setToolTip(text)
        style = self.notice.style()
        style.unpolish(self.notice)
        style.polish(self.notice)

    # ---- filter and selection ------------------------------------------------
    def _apply_filter(self) -> None:
        self.proxy.setFilterFixedString(self.search.text())

    def _on_row_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        source = self.proxy.mapToSource(current)
        cp = self.model.column_at(source.row())
        if cp is not None:
            self._show_detail(cp)

    def _show_detail(self, cp: ColumnProfile) -> None:
        suggested = suggested_text(cp)
        title = f"{cp.name}  -  {cp.dtype}"
        if suggested:
            title += f"  (looks like {suggested})"
        self.detail_title.setText(title)
        labels, values, kind, captions = chart_for(cp)
        self.chart.set_bars(labels, values, kind, captions)
        rows = "".join(
            f"<tr><td style='padding-right:12px'>{escape(label)}</td>"
            f"<td>{escape(text)}</td></tr>"
            for label, text in detail_rows(cp)
        )
        self.detail_stats.setText(f"<table>{rows}</table>")

    def _clear_detail(self) -> None:
        self.detail_title.setText("")
        self.chart.clear()
        self.detail_stats.setText("")

    # ---- copy and export ---------------------------------------------------------
    def _frame(self):
        return None if self._profile is None else self._profile.to_frame()

    def copy_profile(self) -> None:
        frame = self._frame()
        if frame is None:
            self.set_message("Nothing to copy yet")
            return
        QApplication.clipboard().setText(profile_to_tsv(frame))
        self.set_message(f"Copied {frame.height:,} rows")

    def export_csv(self) -> None:
        frame = self._frame()
        if frame is None:
            self.set_message("Nothing to export yet")
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, "Export profile as CSV", "profile.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            frame.write_csv(path)
        except Exception as exc:  # noqa: BLE001 - shown in the chip, never raised
            self.set_message(f"Export failed: {exc}")
            return
        self.set_message(f"Exported {frame.height:,} rows to CSV")

    def export_excel(self) -> None:
        frame = self._frame()
        if frame is None:
            self.set_message("Nothing to export yet")
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, "Export profile as Excel", "profile.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            write_profile_xlsx(frame, path)
        except Exception as exc:  # noqa: BLE001 - shown in the chip, never raised
            self.set_message(f"Export failed: {exc}")
            return
        self.set_message(f"Exported {frame.height:,} rows to Excel")

    def _report_html(self) -> str | None:
        if self._profile is None:
            return None
        return profile_to_html(self._profile, self.report_title)

    def export_html(self) -> None:
        html = self._report_html()
        if html is None:
            self.set_message("Nothing to export yet")
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, "Export profile as HTML report", "profile.html", "HTML (*.html)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(html)
        except OSError as exc:
            self.set_message(f"Export failed: {exc}")
            return
        self.set_message("Exported HTML report")

    def open_full_report(self) -> None:
        """Write the report to a temporary file and open it in the browser."""
        html = self._report_html()
        if html is None:
            self.set_message("Nothing to show yet")
            return
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="",
                prefix="data_profile_",
                suffix=".html",
                delete=False,
            ) as handle:
                handle.write(html)
        except OSError as exc:
            self.set_message(f"Could not write the report: {exc}")
            return
        _TEMP_REPORTS.append(handle.name)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(handle.name)):
            self.set_message(f"Could not open the report: {handle.name}")
