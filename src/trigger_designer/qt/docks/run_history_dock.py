"""Run History dock: the sealed run records of the active workflow (plan 02 3.15).

Follows the active design window like the Logging dock. Everything that reads
files in bulk (verify, check inputs, export, the per-run numbers of the list)
runs in an :class:`AuditTask`; the dock only shows results. UI rules:
icon-only toolbar buttons with tooltip and accessible name, theme tokens for
colour, no inline stylesheets.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import orjson
from loguru import logger
from qtpy.QtCore import QItemSelectionModel, Qt, QUrl, Signal
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.audit.compare import InputCheck, check_inputs, compare_runs
from trigger_designer.core.audit.export import export_json, render_html
from trigger_designer.core.audit.store import VerifyReport, verify_store
from trigger_designer.core.audit.view import run_summary_rows
from trigger_designer.qt.helpers.audit_bridge import store_from_preferences
from trigger_designer.qt.helpers.audit_tasks import AuditTask
from trigger_designer.qt.models.run_history_models import (
    DiffTableModel,
    NodeTableModel,
    RunListModel,
    SummaryModel,
    summarise_record,
    token_color,
)
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.widgets.common import (
    ConfigSection,
    EmptyStateLabel,
    IconButton,
)

if TYPE_CHECKING:
    from trigger_designer.qt.design_window import TriggerSubWindow

_TITLE = "Run History"

#: Glyphs this dock needs beyond resources.json; an entry there always wins.
_EXTRA_ICONS = {
    "icon_compare": "compare",
    "icon_verify": "verified_user",
    "icon_check_inputs": "fact_check",
}

#: Most runs whose numbers (duration, rows) the list loads in the background.
DETAIL_LIMIT = 500

_STATE_TEXT = {
    "unchanged": "unchanged",
    "modified": "MODIFIED",
    "missing": "MISSING",
    "skipped": "not checked",
    "error": "unreadable",
}


def _icon(resource_id: str):
    name = _EXTRA_ICONS.get(resource_id)
    if name:
        ResourceManager.register_material(resource_id, name)
    return ResourceManager().get(resource_id)


class InputCheckDialog(QDialog):
    """Result of "Check inputs": one row per recorded input file."""

    def __init__(self, checks: list[InputCheck], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Check inputs")
        self.setObjectName("InputCheckDialog")
        self.setMinimumSize(560, 260)
        layout = QVBoxLayout(self)
        modified = sum(1 for c in checks if c.state in ("modified", "missing", "error"))
        summary = (
            "Every recorded input matches the file on disk."
            if checks and not modified and all(c.state == "unchanged" for c in checks)
            else f"{modified} of {len(checks)} input file(s) differ from the record."
        )
        self.summary_label = QLabel(summary)
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.table = QTableView(self)
        self.table.setObjectName("ColumnTable")
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        from qtpy.QtGui import QStandardItem, QStandardItemModel

        model = QStandardItemModel(len(checks), 3, self.table)
        model.setHorizontalHeaderLabels(["State", "File", "Sheet"])
        warning = token_color("warning", "#d9a441")
        danger = token_color("danger", "#e0686c")
        for row, check in enumerate(checks):
            cells = [
                QStandardItem(_STATE_TEXT.get(check.state, check.state)),
                QStandardItem(check.path),
                QStandardItem(check.sheet or ""),
            ]
            for cell in cells:
                cell.setEditable(False)
                cell.setToolTip(
                    f"recorded {check.recorded_sha256 or '-'}\n"
                    f"now      {check.current_sha256 or '-'}"
                )
            if check.state == "modified":
                cells[0].setForeground(warning)
            elif check.state in ("missing", "error"):
                cells[0].setForeground(danger)
            for column, cell in enumerate(cells):
                model.setItem(row, column, cell)
        self.table.setModel(model)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(1, 330)
        layout.addWidget(self.table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(
            self.accept
        )
        layout.addWidget(buttons)
        self.checks = list(checks)


def show_input_check(parent: QWidget, checks: list[InputCheck]) -> None:
    """Module-level so tests can replace the modal dialog."""
    InputCheckDialog(checks, parent).exec()


def _record_path(directory: Path, header_file: str) -> Path:
    return directory / header_file


class RunHistoryDock(QDockWidget):
    """Lists, verifies, compares and exports the runs of the active workflow."""

    #: Emits the ``VerifyReport`` of a finished verification (tests wait on it).
    verify_finished = Signal(object)
    #: Emits the output path after an export finished.
    export_finished = Signal(str)
    #: Emits the list of ``InputCheck`` after "Check inputs".
    check_finished = Signal(object)
    #: Emits after the run list was (re)loaded.
    reloaded = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_TITLE, parent)
        self.setObjectName("RunHistoryDock")
        self._window: TriggerSubWindow | None = None
        self._directory: Path | None = None
        self._records: dict[str, dict] = {}
        self._tasks: set[AuditTask] = set()
        self._last_report: VerifyReport | None = None
        self._verified_at: str | None = None
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self._build()
        self.apply_theme()

    # ------------------------------------------------------------- layout
    def _table(self, name: str, model) -> QTableView:
        view = QTableView(self)
        view.setObjectName("ColumnTable")
        view.setAccessibleName(name)
        view.setModel(model)
        view.verticalHeader().setVisible(False)
        view.verticalHeader().setDefaultSectionSize(22)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        view.setAlternatingRowColors(False)
        view.setWordWrap(False)
        view.horizontalHeader().setStretchLastSection(True)
        view.horizontalHeader().setHighlightSections(False)
        return view

    def _build(self) -> None:
        panel = QWidget(self)
        panel.setObjectName("RunHistoryPanel")
        root = QVBoxLayout(panel)
        root.setContentsMargins(5, 5, 5, 5)
        root.setSpacing(2)

        toolbar = QWidget(panel)
        toolbar.setFixedHeight(40)
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(2)

        def button(attr: str, tooltip: str, icon_id: str, checkable=False):
            widget = IconButton.themed(tooltip, rsm_icon=_icon(icon_id), parent=toolbar)
            widget.setCheckable(checkable)
            setattr(self, attr, widget)
            bar.addWidget(widget)
            return widget

        button("btn_refresh", "Refresh run list", "icon_refresh").clicked.connect(
            self.reload
        )
        button("btn_verify", "Verify run log", "icon_verify").clicked.connect(
            self.verify
        )
        button("btn_folder", "Open run log folder", "icon_folder_open").clicked.connect(
            self.open_folder
        )
        bar.addSpacing(8)
        button(
            "btn_check_inputs",
            "Check inputs against selected run",
            "icon_check_inputs",
        ).clicked.connect(self.check_selected_inputs)
        button(
            "btn_compare", "Compare two selected runs", "icon_compare", checkable=True
        ).toggled.connect(self._on_compare_toggled)
        bar.addSpacing(8)
        button(
            "btn_export_json", "Export selected run as JSON", "icon_save"
        ).clicked.connect(self.export_json_dialog)
        button(
            "btn_export_html",
            "Export selected run as HTML report",
            "icon_external",
        ).clicked.connect(self.export_html_dialog)
        bar.addStretch(1)
        root.addWidget(toolbar)

        self.run_model = RunListModel(self)
        self.run_table = self._table("Runs", self.run_model)
        self.run_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.run_table.setMinimumHeight(90)

        self.summary_model = SummaryModel(self)
        self.summary_table = self._table("Run summary", self.summary_model)
        self.summary_table.horizontalHeader().setVisible(False)
        self.summary_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.summary_table.setColumnWidth(0, 110)
        summary = ConfigSection("Summary")
        summary.addWidget(self.summary_table, 1)
        summary.setMinimumWidth(240)

        self.node_model = NodeTableModel(self)
        self.node_table = self._table("Run nodes", self.node_model)
        self.diff_model = DiffTableModel(self)
        self.diff_table = self._table("Run differences", self.diff_model)
        self.lower_stack = QStackedWidget(self)
        self.lower_stack.addWidget(self.node_table)
        self.lower_stack.addWidget(self.diff_table)

        self.lower_split = QSplitter(Qt.Orientation.Horizontal, self)
        self.lower_split.addWidget(summary)
        self.lower_split.addWidget(self.lower_stack)
        self.lower_split.setStretchFactor(1, 1)
        self.lower_split.setSizes([300, 520])

        self.main_split = QSplitter(Qt.Orientation.Vertical, self)
        self.main_split.addWidget(self.run_table)
        self.main_split.addWidget(self.lower_split)
        self.main_split.setStretchFactor(0, 1)
        self.main_split.setStretchFactor(1, 1)
        root.addWidget(self.main_split, 1)

        self.empty_label = EmptyStateLabel("No runs recorded yet", panel)
        root.addWidget(self.empty_label, 1)

        self.status_label = QLabel("", panel)
        self.status_label.setObjectName("RunHistoryStatus")
        self.status_label.setAccessibleName("Run history status")
        root.addWidget(self.status_label)
        self.setWidget(panel)

        header = self.run_table.horizontalHeader()
        header.setStretchLastSection(False)
        for column, width in enumerate((46, 150, 84, 80, 60, 80, 90)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            header.resizeSection(column, width)
        self.run_table.selectionModel().selectionChanged.connect(self._on_selection)
        self.run_table.selectionModel().currentChanged.connect(
            lambda *_: self._show_current()
        )
        self._update_buttons()
        self._update_empty_state()

    # ------------------------------------------------------ follow window
    def switch_to_design_window(self, window: TriggerSubWindow | None) -> None:
        old = self._window
        if old is not None:
            try:
                old.runRecorded.disconnect(self._on_run_recorded)
            except TypeError, RuntimeError:
                pass
        self._window = window
        if window is not None:
            try:
                window.runRecorded.connect(self._on_run_recorded)
            except AttributeError, RuntimeError:
                pass
        self._last_report = None
        self._verified_at = None
        self.reload()

    def remove_design_window(self, window_id: str) -> None:
        if self._window is not None and str(id(self._window)) == window_id:
            self.switch_to_design_window(None)

    def _workflow_path(self) -> str | None:
        window = self._window
        if window is None:
            return None
        path = getattr(window, "filename", None)
        if not path:
            path = getattr(getattr(window, "scene", None), "filename", None)
        return os.fspath(path) if path else None

    def store_dir(self) -> Path | None:
        """The folder of the active window's records (it may not exist yet)."""
        if self._window is None:
            return None
        return store_from_preferences().store_dir_for(self._workflow_path())

    # ------------------------------------------------------------- loading
    def reload(self) -> None:
        """Re-read ``index.jsonl`` and keep the selection where possible."""
        keep = self.current_run_id()
        self._directory = self.store_dir()
        self._records.clear()
        headers = []
        if self._directory is not None:
            try:
                headers = store_from_preferences().list_runs(self._directory)
            except Exception as exc:  # noqa: BLE001 - never raise into a Qt slot
                logger.warning("cannot list the run log: {}", exc)
        self.run_model.set_runs(headers)
        self._update_empty_state()
        self._update_status()
        if headers:
            self._load_details(headers)
            target = keep if keep and self.run_model.row_of(keep) >= 0 else None
            self.select_run(target or self.run_model.run_at(0)["run_id"])
        else:
            self._show_current()
        self.reloaded.emit()

    def _load_details(self, headers: list) -> None:
        directory = self._directory
        recent = sorted(headers, key=lambda h: h.seq, reverse=True)[:DETAIL_LIMIT]
        files = {h.run_id: h.file for h in recent}

        def work(cancel, folder: Path, mapping: dict[str, str]):
            found = {}
            for run_id, file_name in mapping.items():
                if cancel.is_set():
                    break
                try:
                    found[run_id] = summarise_record(
                        orjson.loads((folder / file_name).read_bytes())
                    )
                except OSError, orjson.JSONDecodeError, TypeError:
                    found[run_id] = {"duration": None, "nodes": None, "rows_out": None}
            return found

        def done(result) -> None:
            if self._directory == directory:
                self.run_model.set_details(result)

        self._start(work, done, None, directory, files)

    # ------------------------------------------------------------ selection
    def current_run_id(self) -> str | None:
        index = self.run_table.currentIndex()
        row = self.run_model.run_at(index.row()) if index.isValid() else None
        return row["run_id"] if row else None

    def selected_run_ids(self) -> list[str]:
        rows = {i.row() for i in self.run_table.selectionModel().selectedRows()}
        return [self.run_model.run_at(r)["run_id"] for r in sorted(rows)]

    def select_run(self, run_id: str) -> None:
        row = self.run_model.row_of(run_id)
        if row < 0:
            return
        model = self.run_table.selectionModel()
        index = self.run_model.index(row, 0)
        model.select(
            index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        model.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
        self._show_current()

    def record_for(self, run_id: str) -> dict | None:
        """The raw record of one run (cached; ``None`` when unreadable)."""
        if run_id in self._records:
            return self._records[run_id]
        row = self.run_model.run_at(self.run_model.row_of(run_id))
        if row is None or self._directory is None:
            return None
        try:
            record = orjson.loads(
                _record_path(self._directory, row["file"]).read_bytes()
            )
        except OSError, orjson.JSONDecodeError:
            return None
        self._records[run_id] = record
        return record

    def _show_current(self) -> None:
        run_id = self.current_run_id()
        record = self.record_for(run_id) if run_id else None
        self.summary_model.set_rows(run_summary_rows(record) if record else [])
        self.node_model.set_record(record)
        self.node_table.resizeColumnsToContents()
        self.summary_table.setColumnWidth(0, 110)
        if self.btn_compare.isChecked():
            self._show_diff()
        self._update_buttons()

    def _on_selection(self, *_args) -> None:
        if len(self.selected_run_ids()) != 2 and self.btn_compare.isChecked():
            self.btn_compare.setChecked(False)
        self._update_buttons()
        self._show_current()

    def _update_buttons(self) -> None:
        selected = self.selected_run_ids()
        single = len(selected) == 1 or (
            bool(selected) and self.current_run_id() in selected
        )
        has_runs = self.run_model.rowCount() > 0
        self.btn_verify.setEnabled(has_runs)
        self.btn_folder.setEnabled(self._directory is not None)
        self.btn_check_inputs.setEnabled(single)
        self.btn_export_json.setEnabled(single)
        self.btn_export_html.setEnabled(single)
        self.btn_compare.setEnabled(len(selected) == 2)

    def _update_empty_state(self) -> None:
        empty = self.run_model.rowCount() == 0
        self.empty_label.setVisible(empty)
        self.main_split.setVisible(not empty)

    def _update_status(self) -> None:
        count = self.run_model.rowCount()
        if self._window is None:
            self.status_label.setText("")
            return
        parts = [f"{count} run{'' if count == 1 else 's'}"]
        report = self._last_report
        if report is None:
            parts.append("chain not verified")
        elif report.ok:
            parts.append(f"chain verified at {self._verified_at}")
            if report.head_hash:
                parts.append(f"head {report.head_hash[:8]}")
        else:
            parts.append(f"chain verification FAILED ({len(report.problems)})")
        self.status_label.setText(" - ".join(parts))

    # ------------------------------------------------------------- tasks
    def _start(self, fn, on_done, on_failed, *args) -> AuditTask:
        task = AuditTask(fn, *args)
        self._tasks.add(task)

        def finish() -> None:
            self._tasks.discard(task)

        def ok(result) -> None:
            try:
                on_done(result)
            except RuntimeError:
                pass  # the dock was destroyed while the task ran
            finally:
                finish()

        def failed(message: str) -> None:
            try:
                if on_failed is not None:
                    on_failed(message)
                else:
                    logger.warning("run history task failed: {}", message)
            except RuntimeError:
                pass  # the dock was destroyed while the task ran
            finally:
                finish()

        task.signals.done.connect(ok)
        task.signals.failed.connect(failed)
        from qtpy.QtCore import QThreadPool

        QThreadPool.globalInstance().start(task)
        return task

    def wait_for_tasks(self, timeout_ms: int = 10_000) -> bool:
        """Block until the background tasks are done (tests, shutdown)."""
        from qtpy.QtCore import QCoreApplication, QThreadPool

        pool = QThreadPool.globalInstance()
        ok = pool.waitForDone(timeout_ms)
        QCoreApplication.processEvents()
        return ok and not self._tasks

    # ----------------------------------------------------------- actions
    def verify(self) -> None:
        directory = self._directory
        if directory is None:
            return

        def work(_cancel, folder: Path):
            return verify_store(folder)

        def done(report: VerifyReport) -> None:
            self._last_report = report
            self._verified_at = datetime.now().strftime("%H:%M")
            by_run: dict[str, str] = {}
            for problem in report.problems:
                if problem.run_id and problem.run_id not in by_run:
                    by_run[problem.run_id] = problem.kind
            self.run_model.set_chain(by_run)
            self._update_status()
            if not report.ok:
                self._show_problems(report)
            self.verify_finished.emit(report)

        def failed(message: str) -> None:
            self.status_label.setText(f"Verification could not run: {message}")

        self._start(work, done, failed, directory)

    def _show_problems(self, report: VerifyReport) -> None:
        lines = [f"{p.kind}: {p.message}" for p in report.problems]
        if report.head_hash:
            lines.append(f"\nHead hash: {report.head_hash}")
        QMessageBox.warning(
            self,
            "Run log verification failed",
            "The run log does not match what was recorded:\n\n" + "\n".join(lines),
        )

    def open_folder(self) -> None:
        directory = self.store_dir()
        if directory is None:
            return
        directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def check_selected_inputs(self) -> None:
        run_id = self.current_run_id()
        record = self.record_for(run_id) if run_id else None
        if record is None:
            return

        def work(cancel, data: dict):
            return check_inputs(data, cancel=cancel, use_cache=False)

        def done(checks) -> None:
            self.check_finished.emit(checks)
            show_input_check(self, checks)

        def failed(message: str) -> None:
            self.status_label.setText(f"Check inputs failed: {message}")

        self._start(work, done, failed, record)

    def _on_compare_toggled(self, checked: bool) -> None:
        if checked:
            self._show_diff()
        else:
            self.lower_stack.setCurrentWidget(self.node_table)

    def _show_diff(self) -> None:
        selected = self.selected_run_ids()
        if len(selected) != 2:
            self.lower_stack.setCurrentWidget(self.node_table)
            return
        records = [self.record_for(run_id) for run_id in selected]
        if any(r is None for r in records):
            return
        old, new = sorted(records, key=lambda r: r.get("seq", 0))
        self.diff_model.set_items(compare_runs(old, new).items)
        self.lower_stack.setCurrentWidget(self.diff_table)

    def _default_name(self, suffix: str) -> str:
        run_id = self.current_run_id() or "run"
        row = self.run_model.run_at(self.run_model.row_of(run_id)) or {}
        return f"run-{row.get('seq', 0):04d}-{run_id[:8]}{suffix}"

    def export_json_dialog(self) -> None:
        run_id = self.current_run_id()
        row = self.run_model.run_at(self.run_model.row_of(run_id)) if run_id else None
        if row is None or self._directory is None:
            return
        target, _filter = QFileDialog.getSaveFileName(
            self,
            "Export run as JSON",
            self._default_name(".json"),
            "JSON (*.json)",
        )
        if not target:
            return
        source = _record_path(self._directory, row["file"])

        def work(_cancel, src: Path, dest: str):
            return export_json(src, dest)

        def done(path: str) -> None:
            self.status_label.setText(f"Exported {path}")
            self.export_finished.emit(path)

        self._start(work, done, self._export_failed, source, target)

    def export_html_dialog(self) -> None:
        run_id = self.current_run_id()
        record = self.record_for(run_id) if run_id else None
        if record is None:
            return
        target, _filter = QFileDialog.getSaveFileName(
            self,
            "Export run as HTML report",
            self._default_name(".html"),
            "HTML (*.html)",
        )
        if not target:
            return
        report = self._last_report

        def work(_cancel, data: dict, dest: str, verify_report):
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text(render_html(data, verify_report), encoding="utf-8")
            return dest

        def done(path: str) -> None:
            self.status_label.setText(f"Exported {path}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            self.export_finished.emit(path)

        self._start(work, done, self._export_failed, record, target, report)

    def _export_failed(self, message: str) -> None:
        self.status_label.setText(f"Export failed: {message}")

    # ------------------------------------------------------------- events
    def _on_run_recorded(self, path: str) -> None:
        self.reload()
        run_id = Path(path).stem
        self.select_run(run_id)
        self._update_status()

    def apply_theme(self) -> None:
        for name in (
            "btn_refresh",
            "btn_verify",
            "btn_folder",
            "btn_check_inputs",
            "btn_compare",
            "btn_export_json",
            "btn_export_html",
        ):
            button = getattr(self, name, None)
            if button is not None:
                button.apply_theme()
        self.run_model.refresh_colors()
        self.node_model.layoutChanged.emit()
