"""Notice when another tool rewrites the ``.tds`` the editor has open.

AI plan, phase 4. The owner gives the watcher the path and the bytes the editor
last read (the baseline), and calls :meth:`ExternalEditWatcher.accept` with the
bytes of every save of its own, so only outside writes are ever reported.

Nothing polls. A file-system event starts a single-shot debounce; only that
timer, or the one retry it may arm, reads the file.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from loguru import logger
from qtpy.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

if TYPE_CHECKING:
    from trigger_designer.core.authoring.external_edit import ExternalChange

#: Statuses worth telling the user about. "unchanged" never is.
_REPORTABLE = frozenset({"changed", "metadata_only", "invalid"})


def _key(path: str) -> str:
    """Absolute, case- and separator-normalised: the form Windows compares."""
    return os.path.normcase(os.path.abspath(path))


def _listed(paths: list[str], target: str) -> bool:
    key = _key(target)
    return any(_key(listed) == key for listed in paths)


class ExternalEditWatcher(QObject):
    """Reports a change to the open workflow that did not come from the app.

    :attr:`changeDetected` carries an ``ExternalChange`` whose status is
    ``"changed"``, ``"metadata_only"`` or ``"invalid"``, once per distinct
    content.
    """

    changeDetected = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        debounce_ms: int = 400,
        retry_ms: int = 1000,
    ) -> None:
        super().__init__(parent)
        self._path: str | None = None
        self._baseline: bytes | None = None
        #: Content the user dismissed ("keep mine").
        self._ignored_sha: str | None = None
        #: Content already emitted, so the same bytes again stay silent.
        self._last_reported_sha: str | None = None

        self._fs = QFileSystemWatcher(self)
        self._fs.fileChanged.connect(self._on_file_event)
        self._fs.directoryChanged.connect(self._on_file_event)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(debounce_ms)
        self._debounce.timeout.connect(self._on_debounce)

        self._retry = QTimer(self)
        self._retry.setSingleShot(True)
        self._retry.setInterval(retry_ms)
        self._retry.timeout.connect(self._on_retry)

    @property
    def path(self) -> str | None:
        """The absolute path being watched, or ``None``."""
        return self._path

    @property
    def baseline(self) -> bytes | None:
        """The bytes the file should hold, or ``None``."""
        return self._baseline

    def watch(self, path: str | None, baseline: bytes | None) -> None:
        """Watch ``path`` against ``baseline``, replacing any earlier target.

        ``None`` for either argument stops watching.
        """
        self.stop()
        if path is None or baseline is None:
            return
        self._path = os.path.abspath(os.fspath(path))
        self._baseline = bytes(baseline)
        self._ensure_watched()

    def stop(self) -> None:
        """Stop watching and forget the target.

        Call this when the window closes: on Windows a watched folder cannot be
        deleted or renamed while the watcher holds it.
        """
        self._debounce.stop()
        self._retry.stop()
        for listing in (self._fs.files(), self._fs.directories()):
            if listing:
                self._fs.removePaths(listing)
        self._path = None
        self._baseline = None
        self._ignored_sha = None
        self._last_reported_sha = None

    def accept(self, raw: bytes) -> None:
        """Make ``raw`` the baseline.

        Call it when the user takes an external change, and with the bytes the
        app has just saved, so neither is reported.
        """
        self._baseline = bytes(raw)
        self._ignored_sha = None
        self._last_reported_sha = None

    def dismiss(self, sha256: str) -> None:
        """Keep the editor's version: do not report this content again."""
        self._ignored_sha = sha256

    def check_now(self) -> ExternalChange | None:
        """Compare the file with the baseline now and return what to report.

        Synchronous and silent: it emits nothing. ``None`` means nothing to
        report: no target, the file is missing or unreadable, its bytes are the
        baseline, the content was dismissed, or the status is "unchanged".
        """
        change, _read_failed = self._probe()
        return change

    def _probe(self) -> tuple[ExternalChange | None, bool]:
        """One comparison: the change to report, and whether the read failed."""
        if self._path is None or self._baseline is None:
            return None, False
        target = _key(self._path)
        try:
            with open(target, "rb") as handle:
                raw = handle.read()
        except FileNotFoundError:
            return None, False  # deleted: not a change; a re-created file is seen
        except OSError:
            return None, True  # locked by a writer, or caught mid-replace
        if raw == self._baseline:
            return None, False

        from trigger_designer.core.authoring.external_edit import analyse_external_edit

        change = analyse_external_edit(self._baseline, raw, target)
        if change.status not in _REPORTABLE or change.sha256 == self._ignored_sha:
            return None, False
        return change, False

    def _ensure_watched(self) -> None:
        """Watch the folder, and the file when it exists.

        A replace drops the file from the watch list, so this also runs after
        every event, not only in :meth:`watch`.
        """
        path = self._path
        if path is None:
            return
        folder = os.path.dirname(path)
        missing: list[str] = []
        if os.path.isdir(folder) and not _listed(self._fs.directories(), folder):
            missing.append(folder)
        if os.path.isfile(path) and not _listed(self._fs.files(), path):
            missing.append(path)
        for target in missing:
            if not self._fs.addPath(target):
                logger.debug("Could not watch {}", target)

    def _on_file_event(self, *_args: object) -> None:
        """Re-arm the watch and restart the debounce."""
        try:
            if self._path is None:
                return
            self._ensure_watched()
            self._debounce.start()
        except Exception:  # noqa: BLE001 - a Qt slot must never raise
            logger.exception("External edit watcher could not handle a file event")

    def _on_debounce(self) -> None:
        self._scan(retried=False)

    def _on_retry(self) -> None:
        self._scan(retried=True)

    def _scan(self, *, retried: bool) -> None:
        """Look at the file and emit at most once per distinct content.

        A file that cannot be read, or that is invalid, is looked at once more
        after ``retry_ms``: its writer may still be at work.
        """
        try:
            change, read_failed = self._probe()
            if read_failed:
                if not retried:
                    self._retry.start()
                return
            if change is None or change.sha256 == self._last_reported_sha:
                return
            if change.status == "invalid" and not retried:
                self._retry.start()
                return
            self._last_reported_sha = change.sha256
            self.changeDetected.emit(change)
        except Exception:  # noqa: BLE001 - a Qt slot must never raise
            logger.exception("External edit check failed for {}", self._path)
