"""Table models of the Run History dock (plan 02 3.15).

Thin ``QAbstractTableModel`` wrappers over the Qt-free rows of
``core/audit/view.py``; colours come from theme tokens, never from hex values.
"""

from __future__ import annotations

from typing import Any

from qtpy.QtCore import QAbstractTableModel, QModelIndex, Qt
from qtpy.QtGui import QColor

from trigger_designer.core.audit.compare import DiffItem
from trigger_designer.core.audit.view import (
    format_duration,
    format_local_time,
    node_table_rows,
    run_rows_out,
)
from trigger_designer.qt.theme_manager import get_theme_manager

#: status text -> (theme token, fallback)
_STATUS_COLORS = {
    "ok": ("success", "#5cb85c"),
    "failed": ("danger", "#e0686c"),
    "cancelled": ("warning", "#d9a441"),
    "skipped": ("warning", "#d9a441"),
}


def token_color(token: str, fallback: str) -> QColor:
    return QColor(get_theme_manager().color(token, fallback))


def status_color(status: str) -> QColor | None:
    pair = _STATUS_COLORS.get(status)
    return token_color(*pair) if pair else None


class RunListModel(QAbstractTableModel):
    """One row per sealed run, newest first."""

    HEADERS = ("#", "Started", "Status", "Duration", "Nodes", "Rows out", "Chain")
    COL_SEQ, COL_STARTED, COL_STATUS, COL_DURATION, COL_NODES, COL_ROWS, COL_CHAIN = (
        range(7)
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []
        self._chain_checked = False

    # -- data ------------------------------------------------------------
    def set_runs(self, headers: list) -> None:
        """Replace the rows from ``RunHeader`` objects (any order)."""
        old = {row["run_id"]: row for row in self._rows}
        rows = []
        # Newest first. The primary and the fallback store keep separate seq
        # counters, so time orders them; seq breaks a tie inside one chain.
        for header in sorted(
            headers, key=lambda h: (h.started_at, h.seq), reverse=True
        ):
            row = {
                "seq": header.seq,
                "run_id": header.run_id,
                "started_at": header.started_at,
                "status": header.status,
                "file": header.file,
                "record_hash": header.record_hash,
                "duration": None,
                "nodes": None,
                "rows_out": None,
                "chain": None,
            }
            kept = old.get(header.run_id)
            if kept:
                for key in ("duration", "nodes", "rows_out", "chain"):
                    row[key] = kept[key]
            rows.append(row)
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def set_details(self, details: dict[str, dict]) -> None:
        for row in self._rows:
            found = details.get(row["run_id"])
            if found:
                row.update(found)
        self._emit_all()

    def set_chain(self, problems_by_run: dict[str, str] | None) -> None:
        """After Verify: ``run_id -> first problem kind``; ``None`` clears it."""
        self._chain_checked = problems_by_run is not None
        for row in self._rows:
            if problems_by_run is None:
                row["chain"] = None
            else:
                row["chain"] = problems_by_run.get(row["run_id"], "ok")
        self._emit_all()

    def _emit_all(self) -> None:
        if self._rows:
            self.dataChanged.emit(
                self.index(0, 0), self.index(len(self._rows) - 1, len(self.HEADERS) - 1)
            )

    def refresh_colors(self) -> None:
        self._emit_all()

    def run_at(self, row: int) -> dict[str, Any] | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def row_of(self, run_id: str) -> int:
        for index, row in enumerate(self._rows):
            if row["run_id"] == run_id:
                return index
        return -1

    # -- Qt model API --------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self.HEADERS[section]
        return None

    def _text(self, row: dict, column: int) -> str:
        if column == self.COL_SEQ:
            return str(row["seq"])
        if column == self.COL_STARTED:
            return format_local_time(row["started_at"])
        if column == self.COL_STATUS:
            return str(row["status"])
        if column == self.COL_DURATION:
            return "" if row["duration"] is None else format_duration(row["duration"])
        if column == self.COL_NODES:
            return "" if row["nodes"] is None else str(row["nodes"])
        if column == self.COL_ROWS:
            return "" if row["rows_out"] is None else f"{row['rows_out']:,}"
        return "-" if row["chain"] is None else str(row["chain"])

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return self._text(row, column)
        if role == Qt.ItemDataRole.ForegroundRole:
            if column == self.COL_STATUS:
                return status_color(row["status"])
            if column == self.COL_CHAIN and row["chain"] is not None:
                return token_color(
                    "success" if row["chain"] == "ok" else "danger",
                    "#5cb85c" if row["chain"] == "ok" else "#e0686c",
                )
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole and column in (
            self.COL_SEQ,
            self.COL_DURATION,
            self.COL_NODES,
            self.COL_ROWS,
        ):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ToolTipRole and column == self.COL_CHAIN:
            return row["chain"] or "Not verified yet: use Verify run log"
        if role == Qt.ItemDataRole.UserRole:
            return row["run_id"]
        return None


def summarise_record(record: dict) -> dict[str, Any]:
    """The cheap per-run numbers the list shows, from one raw record."""
    return {
        "duration": record.get("duration_s"),
        "nodes": len(record.get("nodes") or []),
        "rows_out": run_rows_out(record),
    }


class SummaryModel(QAbstractTableModel):
    """The read-only label/value pairs of the Summary pane."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, str]] = []

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rows(self) -> list[tuple[str, str]]:
        return list(self._rows)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else 2

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        label, value = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return label if index.column() == 0 else value
        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 1:
            return value
        if role == Qt.ItemDataRole.ForegroundRole and index.column() == 1:
            if label == "Note":
                return token_color("warning", "#d9a441")
            if label == "Status":
                return status_color(value)
        return None


class NodeTableModel(QAbstractTableModel):
    """One row per node of the selected run."""

    HEADERS = (
        "Node",
        "Operation",
        "Status",
        "In",
        "Out",
        "Cols",
        "Time",
        "Test",
        "Problem",
    )
    KEYS = (
        "node",
        "op",
        "status",
        "rows_in",
        "rows_out",
        "columns",
        "duration",
        "test",
        "error",
    )
    NUMERIC = frozenset({3, 4, 5, 6})

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []

    def set_record(self, record: dict | None) -> None:
        self.beginResetModel()
        self._rows = node_table_rows(record) if record else []
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = self.KEYS[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return row[key]
        if role == Qt.ItemDataRole.ForegroundRole and key == "status":
            return status_color(row["status"])
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in self.NUMERIC:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ToolTipRole and row[key]:
            return str(row[key])
        return None


def _shown(value: object) -> str:
    if value is None:
        return "-"
    text = str(value)
    return text if len(text) <= 60 else text[:57] + "..."


class DiffTableModel(QAbstractTableModel):
    """The differences between two runs (``compare_runs`` items)."""

    HEADERS = ("Kind", "Node", "Field", "Old", "New")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: list[DiffItem] = []

    def set_items(self, items: list[DiffItem]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return (
                item.kind,
                item.node_title or ("" if item.node_id is None else str(item.node_id)),
                item.field,
                _shown(item.old),
                _shown(item.new),
            )[column]
        if role == Qt.ItemDataRole.ToolTipRole and column in (3, 4):
            return str(item.old if column == 3 else item.new)
        return None
