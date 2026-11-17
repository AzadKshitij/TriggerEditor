"""Optional modules dialog: see what is available, then install, verify or remove.

Trigger Designer works fully offline without optional modules. This dialog is the
only place in the GUI that can start a download, and it does so only after the
user presses Download on ``ModuleConsentDialog``. Every call that touches the
store, the catalogue or the installer goes through the seam given to the
constructor, so tests substitute fakes and this module imports no network code.

Install and Verify run on a ``QThread`` with a ``QObject`` worker. The worker
reports progress and its outcome through signals, and Cancel sets the
``threading.Event`` the installer polls. Qt aborts the process when a running
QThread is destroyed, so every live thread is held in ``_LIVE_TASKS`` until it
has stopped, and ``aboutToQuit`` cancels and waits for whatever still runs.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from loguru import logger
from qtpy.QtCore import QCoreApplication, QObject, Qt, QThread, Signal, Slot
from qtpy.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.modules import (
    Consent,
    ModuleError,
    ModuleManifest,
    ModuleStore,
    consent_summary,
    install_module,
    load_catalogue,
)
from trigger_designer.core.modules.consent import size_text
from trigger_designer.qt.widgets.common.config_widgets import (
    ROW_H,
    ConfigSection,
    EmptyStateLabel,
    TextButton,
)

#: What ``install_module`` raises when the user cancels. Cancelling is not an error.
CANCELLED_CODE = "TD-MOD-009"

STATUS_NOT_INSTALLED = "Not installed"
STATUS_INSTALLED = "Installed"
STATUS_CHANGED = "Installed (changed on disk)"
STATUS_UPDATE = "Update available"

_INTRO = (
    "Optional modules add extra capabilities. Trigger Designer works fully offline "
    "without them. A module is downloaded only when you choose Install, after you "
    "agree on the next screen."
)
_EMPTY_CATALOGUE = "No optional modules are available in this version."
_NO_SELECTION = "Select a module to see what it does and which hosts it contacts."
_COLUMNS = ("Name", "Version", "Size", "Status")
_INSTALL = "install"
_VERIFY = "verify"
_PROGRESS_STEPS = 1000


# -- helpers ------------------------------------------------------------------


def _plain_label(text: str) -> QLabel:
    """A wrapping label that shows its text literally, never as markup."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def _cell(text: str, *, align_right: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    if align_right:
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
    return item


def _problem_text(problem: object) -> str:
    code = getattr(problem, "code", "")
    message = getattr(problem, "message", "")
    if code and message:
        return f"{code}: {message}"
    return str(problem)


def _failure_text(message: str, hint: str, code: str) -> str:
    parts = [message or "The operation did not finish."]
    if hint:
        parts.append(hint)
    if code:
        parts.append(f"Error code: {code}")
    return "\n\n".join(parts)


def _row_status(manifest: ModuleManifest | None, installed: Any, changed: bool) -> str:
    if installed is None:
        return STATUS_NOT_INSTALLED
    if changed:
        return STATUS_CHANGED
    if manifest is not None and manifest.version != installed.version:
        return STATUS_UPDATE
    return STATUS_INSTALLED


@dataclass(frozen=True)
class _Row:
    """One table line: a catalogue module, an installed module, or both."""

    module_id: str
    name: str
    version: str
    size_bytes: int
    status: str
    catalogue: ModuleManifest | None
    installed: Any


def _build_rows(
    catalogue: tuple[ModuleManifest, ...],
    installed: tuple[Any, ...],
    changed: set[str],
) -> list[_Row]:
    """Catalogue modules in catalogue order, then installed ones it no longer lists."""
    installed_by_id = {module.id: module for module in installed}
    rows: list[_Row] = []
    for manifest in catalogue:
        current = installed_by_id.get(manifest.id)
        rows.append(
            _Row(
                module_id=manifest.id,
                name=manifest.name,
                version=manifest.version,
                size_bytes=(
                    current.size_bytes if current is not None else manifest.total_size
                ),
                status=_row_status(manifest, current, manifest.id in changed),
                catalogue=manifest,
                installed=current,
            )
        )
    listed = {manifest.id for manifest in catalogue}
    for module in sorted(installed, key=lambda item: item.manifest.name.lower()):
        if module.id in listed:
            continue
        rows.append(
            _Row(
                module_id=module.id,
                name=module.manifest.name,
                version=module.version,
                size_bytes=module.size_bytes,
                status=_row_status(None, module, module.id in changed),
                catalogue=None,
                installed=module,
            )
        )
    return rows


def _details_text(row: _Row) -> str:
    manifest = row.catalogue if row.catalogue is not None else row.installed.manifest
    hosts = ", ".join(manifest.hosts) or "no hosts"
    lines = [
        manifest.description,
        "",
        f"License: {manifest.license}",
        f"Connects to: {hosts}",
    ]
    if row.installed is not None:
        lines.append(f"Installed at: {row.installed.path}")
    return "\n".join(lines)


@dataclass
class _Busy:
    """The one background operation the dialog is waiting on."""

    kind: str
    module_id: str
    name: str
    version: str
    progress: _InstallProgressDialog | None = None


# -- background work ----------------------------------------------------------


class _Task(QObject):
    """Runs one piece of work on the thread it is moved to.

    ``work(report, cancelled)`` runs off the GUI thread: ``report(done, total)``
    forwards progress and ``cancelled()`` says whether the user asked to stop.
    """

    progress = Signal(int, int)  # done, total
    finished = Signal(object)  # what the work returned
    failed = Signal(str, str, str)  # code, message, hint

    def __init__(
        self,
        work: Callable[[Callable[[int, int], None], Callable[[], bool]], Any],
        cancel: threading.Event,
    ) -> None:
        super().__init__()
        self._work = work
        self._cancel = cancel

    @Slot()
    def run(self) -> None:
        try:
            result = self._work(self._report, self._cancel.is_set)
        except ModuleError as exc:
            self.failed.emit(str(exc.code), str(exc.message), str(exc.hint or ""))
        except Exception as exc:  # noqa: BLE001 - the worker boundary reports failure
            logger.exception("Optional module task failed unexpectedly")
            self.failed.emit("", str(exc) or type(exc).__name__, "")
        else:
            self.finished.emit(result)

    def _report(self, done: int, total: int) -> None:
        self.progress.emit(int(done), int(total))


#: Threads still running, each with the cancel flag its work polls. Held until the
#: thread has stopped: destroying a running QThread aborts the process.
_LIVE_TASKS: dict[QThread, tuple[threading.Event, _Task]] = {}
_quit_hook_connected = False


def _release_task(thread: QThread) -> None:
    _LIVE_TASKS.pop(thread, None)
    thread.deleteLater()


def _connect_quit_hook() -> None:
    global _quit_hook_connected
    app = QCoreApplication.instance()
    if _quit_hook_connected or app is None:
        return
    app.aboutToQuit.connect(_stop_live_tasks)
    _quit_hook_connected = True


def _stop_live_tasks(timeout_ms: int = 5000) -> bool:
    """Cancel every running task, then wait (bounded) for its thread to stop."""
    for cancel, _task in list(_LIVE_TASKS.values()):
        cancel.set()
    deadline = time.monotonic() + timeout_ms / 1000.0
    stopped = True
    for thread in list(_LIVE_TASKS):
        remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
        try:
            stopped = thread.wait(remaining_ms) and stopped
        except RuntimeError:  # the C++ thread object is already gone
            continue
    return stopped


# -- widgets ------------------------------------------------------------------


class _InstallProgressDialog(QDialog):
    """Modal progress for one installation.

    Cancel, Escape and the window's close button all ask the installer to stop.
    The dialog stays up until the installer reports back, so the user sees
    "Cancelling..." rather than an install that seems to ignore them.
    """

    cancel_requested = Signal()

    def __init__(self, name: str, version: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ModuleInstallProgress")
        self.setWindowTitle("Installing optional module")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(360)
        self._cancelling = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        self._label = _plain_label(f"Installing {name} {version}...")
        layout.addWidget(self._label)

        self._bar = QProgressBar(self)
        self._bar.setObjectName("ModuleProgressBar")
        self._bar.setRange(0, 0)  # busy until the installer reports a total
        layout.addWidget(self._bar)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        footer.addStretch(1)
        self.cancel_button = TextButton("Cancel", "Cancel the installation")
        self.cancel_button.clicked.connect(self._request_cancel)
        footer.addWidget(self.cancel_button)
        layout.addLayout(footer)

    @property
    def bar(self) -> QProgressBar:
        return self._bar

    def set_progress(self, done: int, total: int) -> None:
        if total <= 0:
            self._bar.setRange(0, 0)
            return
        # The installer reports bytes and a module may be several GiB, which a Qt
        # bar (C ints) cannot hold, so the bar counts in fixed steps instead.
        self._bar.setRange(0, _PROGRESS_STEPS)
        self._bar.setValue(min(max(done, 0), total) * _PROGRESS_STEPS // total)

    def reject(self) -> None:
        """Escape and the window's close button both ask for a stop."""
        self._request_cancel()

    def _request_cancel(self, *_args: object) -> None:
        if self._cancelling:
            return
        self._cancelling = True
        self._label.setText("Cancelling...")
        self.cancel_button.setEnabled(False)
        self.cancel_requested.emit()


class ModuleConsentDialog(QDialog):
    """What a download will fetch, and the only door to starting it.

    Accepting creates no consent here: the caller builds ``Consent.granted`` after
    ``exec()`` returns ``Accepted``. Cancel is the default button, so Enter never
    starts a download by accident.
    """

    def __init__(self, manifest: ModuleManifest, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        summary = consent_summary(manifest)
        self.setObjectName("ModuleConsentDialog")
        self.setWindowTitle(f"Download {summary.name} {summary.version}?")
        self.setModal(True)
        self.setMinimumWidth(640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(_plain_label(summary.notice))

        details = ConfigSection("Details")
        hosts = ", ".join(summary.hosts) or "none"
        details.addWidget(_plain_label(f"Downloads from: {hosts}"))
        details.addWidget(_plain_label(f"Total download: {summary.total_size_text}"))
        details.addWidget(_plain_label(f"License: {summary.license}"))
        layout.addWidget(details)

        files = ConfigSection("Files")
        table = QTableWidget(len(summary.files), 3, self)
        table.setObjectName("ModuleFilesTable")
        table.setHorizontalHeaderLabels(["File", "Size", "SHA-256"])
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(ROW_H)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for index, (name, url, size_bytes, sha256) in enumerate(summary.files):
            name_item = _cell(str(name))
            name_item.setToolTip(str(url))
            table.setItem(index, 0, name_item)
            table.setItem(index, 1, _cell(size_text(size_bytes), align_right=True))
            table.setItem(index, 2, _cell(str(sha256)))
        files.addWidget(table)
        layout.addWidget(files, 1)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        footer.addStretch(1)
        self.cancel_button = TextButton("Cancel", "Do not download this module")
        self.cancel_button.clicked.connect(self.reject)
        footer.addWidget(self.cancel_button)
        self.download_button = TextButton(
            "Download", f"Download {summary.name} {summary.version}"
        )
        self.download_button.setObjectName("PrimaryButton")
        self.download_button.setAutoDefault(False)
        self.download_button.clicked.connect(self.accept)
        footer.addWidget(self.download_button)
        layout.addLayout(footer)

        self.cancel_button.setDefault(True)
        self.cancel_button.setFocus()


class ModulesDialog(QDialog):
    """Lists the optional modules and runs install, verify and remove on them."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        store: ModuleStore | None = None,
        catalogue_loader: Callable[[], Any] = load_catalogue,
        installer: Callable[..., Any] = install_module,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ModulesDialog")
        self.setWindowTitle("Optional modules")
        self.setModal(True)
        self.setMinimumSize(640, 480)

        self._store = store if store is not None else ModuleStore()
        self._catalogue_loader = catalogue_loader
        self._installer = installer
        self._catalogue: tuple[ModuleManifest, ...] = ()
        self._rows: list[_Row] = []
        #: Installed modules whose last Verify found changes on disk.
        self._changed: set[str] = set()
        self._busy: _Busy | None = None

        self._build_ui()
        self._reload()

    # -- construction -----------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(_plain_label(_INTRO))

        self._empty = EmptyStateLabel(_EMPTY_CATALOGUE)
        layout.addWidget(self._empty, 1)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setObjectName("ModulesTable")
        self._table.setHorizontalHeaderLabels(list(_COLUMNS))
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(ROW_H)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(_COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._table, 1)

        self._problems = _plain_label("")
        self._problems.setObjectName("FieldHint")
        layout.addWidget(self._problems)

        details = ConfigSection("Details")
        self._details = _plain_label(_NO_SELECTION)
        details.addWidget(self._details)
        layout.addWidget(details)

        self._status = _plain_label("")
        self._status.hide()
        layout.addWidget(self._status)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        self._verify_button = TextButton(
            "Verify", "Check the installed files against their recorded hashes"
        )
        self._verify_button.clicked.connect(self._on_verify)
        footer.addWidget(self._verify_button)
        self._remove_button = TextButton(
            "Remove", "Remove the selected module from this computer"
        )
        self._remove_button.setObjectName("DangerButton")
        self._remove_button.clicked.connect(self._on_remove)
        footer.addWidget(self._remove_button)
        footer.addStretch(1)
        close = TextButton("Close", "Close optional modules")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        self._install_button = TextButton("Install", "Select a module to install it")
        self._install_button.setObjectName("PrimaryButton")
        self._install_button.clicked.connect(self._on_install)
        footer.addWidget(self._install_button)
        layout.addLayout(footer)

    # -- reading state ----------------------------------------------------
    def _reload(self, select: str | None = None) -> None:
        """Re-read the catalogue and the store, then rebuild the table."""
        if select is None:
            select = self._selected_id()
        problems: list[str] = []
        self._catalogue = self._read_catalogue(problems)
        installed = self._read_installed(problems)
        self._rows = _build_rows(self._catalogue, installed, self._changed)
        self._populate(select)
        self._empty.setVisible(not self._catalogue)
        self._table.setVisible(bool(self._rows))
        self._problems.setText("\n".join(problems))
        self._problems.setVisible(bool(problems))
        self._on_selection_changed()

    def _read_catalogue(self, problems: list[str]) -> tuple[ModuleManifest, ...]:
        try:
            catalogue = self._catalogue_loader()
        except Exception as exc:  # noqa: BLE001 - a broken catalogue must not
            # block the dialog; the failure is shown on the problem line instead.
            logger.exception("Could not read the optional module catalogue")
            problems.append(f"The module catalogue could not be read: {exc}")
            return ()
        problems.extend(_problem_text(problem) for problem in catalogue.problems)
        return tuple(catalogue.modules)

    def _read_installed(self, problems: list[str]) -> tuple[Any, ...]:
        try:
            return tuple(self._store.installed())
        except Exception as exc:  # noqa: BLE001 - listing failures are shown, not raised
            logger.exception("Could not list the installed optional modules")
            problems.append(f"Installed modules could not be listed: {exc}")
            return ()

    def _populate(self, select: str | None) -> None:
        self._table.blockSignals(True)
        try:
            self._table.setRowCount(len(self._rows))
            for index, row in enumerate(self._rows):
                self._table.setItem(index, 0, _cell(row.name))
                self._table.setItem(index, 1, _cell(row.version))
                self._table.setItem(
                    index, 2, _cell(size_text(row.size_bytes), align_right=True)
                )
                self._table.setItem(index, 3, _cell(row.status))
            for index, row in enumerate(self._rows):
                if row.module_id == select:
                    self._table.selectRow(index)
                    break
        finally:
            self._table.blockSignals(False)

    def _selected_row(self) -> _Row | None:
        selection = self._table.selectionModel()
        indexes = selection.selectedRows() if selection is not None else []
        if not indexes:
            return None
        index = indexes[0].row()
        return self._rows[index] if 0 <= index < len(self._rows) else None

    def _selected_id(self) -> str | None:
        row = self._selected_row()
        return row.module_id if row is not None else None

    # -- state of the controls -------------------------------------------
    def _on_selection_changed(self) -> None:
        row = self._selected_row()
        self._details.setText(_details_text(row) if row is not None else _NO_SELECTION)
        self._update_buttons(row)

    def _update_buttons(self, row: _Row | None) -> None:
        busy = self._busy is not None
        installed = row is not None and row.installed is not None
        if row is None:
            label, tip, can_install = "Install", "Select a module to install it", False
        elif row.catalogue is None:
            label, tip, can_install = (
                "Install",
                "This module is not in this version's catalogue",
                False,
            )
        elif row.installed is None:
            label, tip, can_install = (
                "Install",
                f"Download and install {row.name} {row.version}",
                True,
            )
        elif row.status == STATUS_UPDATE:
            label, tip, can_install = (
                "Update",
                f"Download {row.name} {row.version} and replace the installed version",
                True,
            )
        else:
            label, tip, can_install = (
                "Reinstall",
                f"Download {row.name} {row.version} again",
                True,
            )
        self._install_button.setText(label)
        self._install_button.setToolTip(tip)
        self._install_button.setEnabled(can_install and not busy)
        self._verify_button.setEnabled(installed and not busy)
        self._remove_button.setEnabled(installed and not busy)

    def _set_status(self, text: str) -> None:
        self._status.setText(text)
        self._status.setVisible(bool(text))

    # -- actions ----------------------------------------------------------
    def _on_install(self) -> None:
        row = self._selected_row()
        if row is None or row.catalogue is None or self._busy is not None:
            return
        manifest = row.catalogue
        try:
            if not self._ask_consent(manifest):
                return
            # The consent is created here and nowhere else, after Download was pressed.
            consent = Consent.granted(manifest)
        except ModuleError as exc:
            QMessageBox.warning(
                self,
                f"Could not install {manifest.name}",
                _failure_text(str(exc.message), str(exc.hint or ""), str(exc.code)),
            )
            return

        cancel = threading.Event()
        progress = _InstallProgressDialog(manifest.name, manifest.version, self)
        progress.cancel_requested.connect(lambda: cancel.set())
        self._busy = _Busy(
            kind=_INSTALL,
            module_id=manifest.id,
            name=manifest.name,
            version=manifest.version,
            progress=progress,
        )
        progress.show()
        store, installer = self._store, self._installer
        self._start(
            lambda report, cancelled: installer(
                manifest, consent, store, progress=report, cancel=cancelled
            ),
            cancel,
        )
        self._update_buttons(self._selected_row())

    def _ask_consent(self, manifest: ModuleManifest) -> bool:
        """Show the consent screen; True only when the user pressed Download."""
        consent_dialog = ModuleConsentDialog(manifest, self)
        try:
            return consent_dialog.exec() == QDialog.DialogCode.Accepted
        finally:
            consent_dialog.deleteLater()

    def _on_verify(self) -> None:
        row = self._selected_row()
        if row is None or row.installed is None or self._busy is not None:
            return
        store, module_id = self._store, row.module_id
        self._busy = _Busy(
            kind=_VERIFY,
            module_id=module_id,
            name=row.name,
            version=row.installed.version,
        )
        self._set_status(f"Checking {row.name}...")
        self._update_buttons(row)
        self._start(
            lambda _report, _cancelled: store.verify(module_id), threading.Event()
        )

    def _on_remove(self) -> None:
        row = self._selected_row()
        if row is None or row.installed is None or self._busy is not None:
            return
        answer = QMessageBox.question(
            self,
            f"Remove {row.name}?",
            f"Remove {row.name} {row.installed.version} from this computer? "
            "Its files are deleted. You can install it again later.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            removed = self._store.remove(row.module_id)
        except ModuleError as exc:
            QMessageBox.warning(
                self,
                f"Could not remove {row.name}",
                _failure_text(str(exc.message), str(exc.hint or ""), str(exc.code)),
            )
            return
        self._changed.discard(row.module_id)
        self._reload()
        self._set_status(
            f"Removed {row.name}." if removed else f"{row.name} was not installed."
        )

    def _start(self, work: Callable[..., Any], cancel: threading.Event) -> None:
        """Run ``work`` on a fresh QThread; the signals report back to this dialog."""
        thread = QThread()
        task = _Task(work, cancel)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.progress.connect(self._on_progress)
        task.finished.connect(self._on_finished)
        task.failed.connect(self._on_failed)
        task.finished.connect(thread.quit)
        task.failed.connect(thread.quit)
        thread.finished.connect(partial(_release_task, thread))
        _LIVE_TASKS[thread] = (cancel, task)
        _connect_quit_hook()
        thread.start()

    def _end_busy(self) -> _Busy | None:
        busy, self._busy = self._busy, None
        if busy is not None and busy.progress is not None:
            busy.progress.hide()
            busy.progress.deleteLater()
        self._update_buttons(self._selected_row())
        return busy

    # -- worker signals (delivered on the GUI thread) ---------------------
    @Slot(int, int)
    def _on_progress(self, done: int, total: int) -> None:
        busy = self._busy
        if busy is not None and busy.progress is not None:
            busy.progress.set_progress(done, total)

    @Slot(object)
    def _on_finished(self, result: object) -> None:
        busy = self._end_busy()
        if busy is None:
            return
        if busy.kind == _INSTALL:
            self._reload(select=busy.module_id)
            self._set_status(f"Installed {busy.name} {busy.version}.")
            return
        ok = bool(result.ok)
        problems = [str(problem) for problem in result.problems]
        if ok:
            self._changed.discard(busy.module_id)
        else:
            self._changed.add(busy.module_id)
        self._reload(select=busy.module_id)
        if ok:
            self._set_status(f"{busy.name} {busy.version} matches what was installed.")
        else:
            QMessageBox.warning(
                self,
                f"{busy.name} changed on disk",
                "The installed files no longer match what was installed:\n\n"
                + "\n".join(problems),
            )

    @Slot(str, str, str)
    def _on_failed(self, code: str, message: str, hint: str) -> None:
        busy = self._end_busy()
        if busy is None:
            return
        self._reload(select=busy.module_id)
        if code == CANCELLED_CODE:
            self._set_status("Installation cancelled.")
            return
        action = "install" if busy.kind == _INSTALL else "verify"
        QMessageBox.warning(
            self,
            f"Could not {action} {busy.name}",
            _failure_text(message, hint, code),
        )
