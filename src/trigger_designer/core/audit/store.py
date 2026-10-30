"""Run store: sealed records, the append-only index, locking and verification.

docs/plan/02-audit-trail.md 3.11. Qt-free. A record is immutable once sealed;
the hash chain (``prev_record_hash``) and the index make edits, deletions in the
middle of the chain and swaps detectable. Truncating the tail is not (the
verify report prints the head hash so a user can note it elsewhere).
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import stat
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

import orjson
from loguru import logger

from trigger_designer.core.audit.canonical import (
    GENESIS_HASH,
    canonical_json,
    compute_record_hash,
)
from trigger_designer.core.audit.schema import RunRecord, validate_record_dict

INDEX_NAME = "index.jsonl"
LOCK_NAME = ".lock"
CACHE_NAME = "hash_cache.json"

#: Seconds to wait for the store lock, and the age after which a lock file is
#: considered abandoned. Module level so tests can shrink them.
LOCK_TIMEOUT_S = 10.0
LOCK_STALE_S = 60.0
LOCK_POLL_S = 0.05


class RunAlreadySealed(Exception):
    """A run record was sealed already; sealed records are never rewritten."""


class StoreLockTimeout(Exception):
    """The store lock could not be taken in time."""


# ---------------------------------------------------------------- locations
def default_app_data_dir() -> Path:
    """Where headless callers keep fallback stores (mirrors the GUI's choice)."""
    override = os.getenv("TRIGGER_DESIGNER_DATA_DIR")
    if override:
        return Path(override)
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "Trigger Designer"
    return Path.home() / ".trigger_designer"


def _path_hash8(workflow_path: str | os.PathLike) -> str:
    absolute = os.path.abspath(os.fspath(workflow_path)).lower()
    return hashlib.sha1(absolute.encode("utf-8", "replace")).hexdigest()[:8]


def _stem(workflow_path: str | os.PathLike) -> str:
    return Path(os.fspath(workflow_path)).stem


def resolve_store_dir(
    workflow_path: str | os.PathLike | None,
    run_log_dir: str | os.PathLike | None = "",
    app_data_dir: str | os.PathLike | None = None,
) -> Path:
    """The folder that holds the records of one workflow (3.11)."""
    if run_log_dir:
        root = Path(run_log_dir)
        if workflow_path:
            return root / f"{_stem(workflow_path)}-{_path_hash8(workflow_path)}"
        return root / "_unsaved"
    if workflow_path:
        path = Path(os.path.abspath(os.fspath(workflow_path)))
        return path.parent / f"{path.stem}.runs"
    base = Path(app_data_dir) if app_data_dir else default_app_data_dir()
    return base / "runs" / "_unsaved"


def fallback_store_dir(
    workflow_path: str | os.PathLike | None, app_data_dir: str | os.PathLike | None
) -> Path:
    base = Path(app_data_dir) if app_data_dir else default_app_data_dir()
    if workflow_path:
        return base / "runs" / f"{_stem(workflow_path)}-{_path_hash8(workflow_path)}"
    return base / "runs" / "_unsaved"


def _ensure_writable(directory: Path) -> None:
    """Create ``directory`` and prove a file can be made in it (``OSError``)."""
    os.makedirs(directory, exist_ok=True)
    probe = directory / f".probe-{os.getpid()}-{threading.get_ident()}"
    with open(probe, "wb") as handle:
        handle.write(b"")
    os.unlink(probe)


# ----------------------------------------------------------------- the lock
@contextlib.contextmanager
def store_lock(directory: Path):
    """Exclusive lock for one store folder (``O_EXCL`` file, stale after 60 s)."""
    lock_path = directory / LOCK_NAME
    deadline = time.monotonic() + LOCK_TIMEOUT_S
    fd = None
    while fd is None:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > LOCK_STALE_S:
                    os.unlink(lock_path)
                    continue
            except OSError:
                continue  # it vanished between the two calls: just retry
            if time.monotonic() >= deadline:
                raise StoreLockTimeout(
                    f"run log folder is locked: {directory}"
                ) from None
            time.sleep(LOCK_POLL_S)
        except PermissionError:
            # Windows reports a file being deleted by its owner this way.
            if time.monotonic() >= deadline:
                raise StoreLockTimeout(
                    f"run log folder is locked: {directory}"
                ) from None
            time.sleep(LOCK_POLL_S)
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        for _ in range(20):
            try:
                os.unlink(lock_path)
                break
            except FileNotFoundError:
                break
            except PermissionError:
                time.sleep(LOCK_POLL_S)


# ------------------------------------------------------------- index access
@dataclass
class _IndexRead:
    entries: list[dict] = field(default_factory=list)
    #: A final fragment without a newline that is not valid JSON.
    truncated_tail: bool = False
    #: 1-based number of the first unparsable line before the end, if any.
    corrupt_line: int | None = None
    #: Byte offset just after the last complete line (where a repair truncates).
    good_length: int = 0


def _read_index(directory: Path) -> _IndexRead:
    result = _IndexRead()
    path = directory / INDEX_NAME
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return result
    offset = 0
    lines = raw.split(b"\n")
    for number, line in enumerate(lines, start=1):
        is_last = number == len(lines)
        consumed = len(line) + (0 if is_last else 1)
        if not line.strip():
            offset += consumed
            if not is_last:
                result.good_length = offset
            continue
        try:
            entry = orjson.loads(line)
            if not isinstance(entry, dict):
                raise TypeError("index line is not an object")
        except orjson.JSONDecodeError, TypeError:
            if is_last:
                result.truncated_tail = True
            elif result.corrupt_line is None:
                result.corrupt_line = number
            offset += consumed
            continue
        result.entries.append(entry)
        offset += consumed
        result.good_length = offset
    return result


@dataclass(frozen=True)
class RunHeader:
    seq: int
    run_id: str
    started_at: str
    status: str
    record_hash: str
    prev_record_hash: str
    file: str


@dataclass(frozen=True)
class VerifyProblem:
    run_id: str | None
    # record_hash_mismatch | prev_hash_mismatch | missing_record | index_mismatch
    # | seq_gap | schema_invalid | unreadable | index_corrupt
    kind: str
    message: str


@dataclass(frozen=True)
class VerifyReport:
    ok: bool
    checked: int
    problems: list[VerifyProblem]
    warnings: list[str]
    head_hash: str | None


def _read_record_dict(path: Path) -> dict:
    data = orjson.loads(path.read_bytes())
    if not isinstance(data, dict):
        raise TypeError("record is not a JSON object")
    return data


def verify_store(directory: str | os.PathLike) -> VerifyReport:
    """Walk the chain of one store folder; see 4/Step 3 of the plan."""
    folder = Path(directory)
    problems: list[VerifyProblem] = []
    warnings: list[str] = []
    index = _read_index(folder)
    record_files = (
        {p.name for p in folder.glob("*.json") if p.name != CACHE_NAME}
        if folder.is_dir()
        else set()
    )
    if not (folder / INDEX_NAME).is_file():
        if record_files:
            problems.append(
                VerifyProblem(
                    None,
                    "index_corrupt",
                    f"index missing but {len(record_files)} record files present",
                )
            )
        return VerifyReport(not problems, 0, problems, warnings, None)
    if index.truncated_tail:
        warnings.append(
            "index_truncated_line: the last index line is incomplete and was ignored"
        )

    expected_prev = GENESIS_HASH
    expected_seq = 1
    checked = 0
    previous_finished: str | None = None
    listed: set[str] = set()
    if index.corrupt_line is not None:
        problems.append(
            VerifyProblem(
                None,
                "index_corrupt",
                f"index line {index.corrupt_line} cannot be read",
            )
        )
    # Entries are those parsed before the first corrupt line (the walk stops).
    entries = index.entries
    if index.corrupt_line is not None:
        entries = _entries_before(folder, index.corrupt_line)
    for entry in entries:
        run_id = entry.get("run_id")
        label = f"run #{entry.get('seq')} ({run_id})"
        file_name = entry.get("file") or f"{run_id}.json"
        listed.add(file_name)
        checked += 1
        if entry.get("seq") != expected_seq:
            problems.append(
                VerifyProblem(
                    run_id,
                    "seq_gap",
                    f"{label}: expected sequence {expected_seq}, "
                    f"found {entry.get('seq')}",
                )
            )
        raw = None
        try:
            raw = _read_record_dict(folder / file_name)
        except FileNotFoundError:
            problems.append(
                VerifyProblem(
                    run_id, "missing_record", f"{label}: {file_name} is missing"
                )
            )
        except (OSError, orjson.JSONDecodeError, TypeError) as exc:
            problems.append(
                VerifyProblem(
                    run_id,
                    "unreadable",
                    f"{label}: {file_name} cannot be read ({type(exc).__name__})",
                )
            )
        if raw is not None:
            bad = validate_record_dict(raw)
            if bad:
                problems.append(
                    VerifyProblem(
                        run_id,
                        "schema_invalid",
                        f"{label}: " + "; ".join(bad[:5]),
                    )
                )
            try:
                recomputed = compute_record_hash(raw)
            except TypeError:
                recomputed = None
            if recomputed != raw.get("record_hash"):
                problems.append(
                    VerifyProblem(
                        run_id,
                        "record_hash_mismatch",
                        f"{label}: the record was changed after it was written",
                    )
                )
            if (
                raw.get("record_hash") != entry.get("record_hash")
                or raw.get("run_id") != run_id
                or raw.get("seq") != entry.get("seq")
            ):
                problems.append(
                    VerifyProblem(
                        run_id,
                        "index_mismatch",
                        f"{label}: the record does not match its index line",
                    )
                )
            if raw.get("prev_record_hash") != expected_prev:
                problems.append(
                    VerifyProblem(
                        run_id,
                        "prev_hash_mismatch",
                        f"{label}: it does not follow the previous run in the chain",
                    )
                )
            started = raw.get("started_at")
            if (
                previous_finished
                and isinstance(started, str)
                and started < previous_finished
            ):
                warnings.append(
                    f"clock_skew: {label} started before the previous run finished"
                )
            finished = raw.get("finished_at")
            if isinstance(finished, str):
                previous_finished = finished
        # Chain on the index values so one bad record is reported once.
        expected_prev = entry.get("record_hash") or expected_prev
        expected_seq = (
            entry["seq"] + 1 if isinstance(entry.get("seq"), int) else expected_seq + 1
        )

    for name in sorted(record_files - listed):
        warnings.append(f"orphan_record: {name} is not listed in the index")
    if folder.is_dir():
        for marker in sorted(folder.glob("*.started")):
            if f"{marker.stem}.json" not in listed:
                warnings.append(
                    f"incomplete_run: run {marker.stem} started but was never sealed"
                )
    head = expected_prev if checked > 0 else None
    return VerifyReport(not problems, checked, problems, warnings, head)


def _entries_before(folder: Path, corrupt_line: int) -> list[dict]:
    """Parsed index entries that precede the first unparsable line."""
    out: list[dict] = []
    try:
        lines = (folder / INDEX_NAME).read_bytes().split(b"\n")
    except OSError:
        return out
    for line in lines[: corrupt_line - 1]:
        if not line.strip():
            continue
        try:
            entry = orjson.loads(line)
        except orjson.JSONDecodeError:
            break
        if isinstance(entry, dict):
            out.append(entry)
    return out


def verify_record_file(path: str | os.PathLike) -> VerifyReport:
    """Check the schema and hash of one record file (no chain)."""
    problems: list[VerifyProblem] = []
    run_id = None
    try:
        raw = _read_record_dict(Path(path))
    except (OSError, orjson.JSONDecodeError, TypeError) as exc:
        problems.append(
            VerifyProblem(
                None, "unreadable", f"cannot read record ({type(exc).__name__})"
            )
        )
        return VerifyReport(False, 1, problems, [], None)
    run_id = raw.get("run_id")
    bad = validate_record_dict(raw)
    if bad:
        problems.append(VerifyProblem(run_id, "schema_invalid", "; ".join(bad[:5])))
    try:
        recomputed = compute_record_hash(raw)
    except TypeError:
        recomputed = None
    if recomputed != raw.get("record_hash"):
        problems.append(
            VerifyProblem(
                run_id,
                "record_hash_mismatch",
                "the record was changed after it was written",
            )
        )
    head = raw.get("record_hash") if not problems else None
    return VerifyReport(not problems, 1, problems, [], head)


# ----------------------------------------------------------------- the store
class RunStore:
    """Reads and writes sealed run records.

    ``run_log_dir`` relocates every store (preference ``audit/run_log_dir``);
    ``app_data_dir`` hosts unsaved-workflow runs and the read-only fallback.
    """

    def __init__(
        self,
        run_log_dir: str = "",
        app_data_dir: str | os.PathLike | None = None,
    ) -> None:
        self.run_log_dir = run_log_dir or ""
        self.app_data_dir = Path(app_data_dir) if app_data_dir else None

    # -- locations -----------------------------------------------------
    def store_dir_for(self, workflow_path: str | None) -> Path:
        return resolve_store_dir(workflow_path, self.run_log_dir, self.app_data_dir)

    def fallback_dir_for(self, workflow_path: str | None) -> Path:
        return fallback_store_dir(workflow_path, self.app_data_dir)

    def _directory(self, directory, workflow_path) -> Path:
        return Path(directory) if directory else self.store_dir_for(workflow_path)

    def resolve_writable(
        self, workflow_path: str | None, directory: str | os.PathLike | None = None
    ) -> tuple[Path, str | None]:
        """The folder a run will be written to, plus a fallback warning."""
        primary = self._directory(directory, workflow_path)
        try:
            _ensure_writable(primary)
            return primary, None
        except OSError:
            fallback = self.fallback_dir_for(workflow_path)
            if fallback == primary:
                raise
            _ensure_writable(fallback)
            return fallback, (
                f"run log stored in fallback folder: {fallback.as_posix()} "
                "(workflow folder is read-only)"
            )

    # -- crash marker ---------------------------------------------------
    def mark_started(
        self,
        run_id: str,
        workflow_path: str | None,
        directory: str | os.PathLike | None = None,
    ) -> Path | None:
        """Drop ``<run_id>.started`` so a crash mid-run can be detected."""
        try:
            folder, _warning = self.resolve_writable(workflow_path, directory)
            marker = folder / f"{run_id}.started"
            marker.write_bytes(b"")
            return marker
        except OSError as exc:
            logger.debug("cannot write the run marker: {}", exc)
            return None

    # -- writing --------------------------------------------------------
    def seal_and_save(
        self, record: RunRecord, directory: str | os.PathLike | None = None
    ) -> tuple[RunRecord, str]:
        """Assign ``seq`` and the chain hashes, write the record, append the index.

        Falls back to the app-data store when the preferred folder is read-only
        or its lock cannot be taken, and says so in ``record.warnings``.
        """
        if record.status not in ("ok", "failed", "cancelled"):
            raise ValueError(f"cannot seal a record with status {record.status!r}")
        primary = self._directory(directory, record.workflow_path)
        fallback = self.fallback_dir_for(record.workflow_path)
        try:
            _ensure_writable(primary)
            return self._seal(record, primary)
        except (OSError, StoreLockTimeout) as exc:
            if fallback == primary:
                raise
            logger.warning(
                "run log folder {} unusable ({}); using fallback", primary, exc
            )
            reason = (
                "workflow folder is read-only"
                if isinstance(exc, OSError)
                else "the run log folder was locked"
            )
            note = (
                f"run log stored in fallback folder: {fallback.as_posix()} ({reason})"
            )
            record = replace(record, warnings=[*record.warnings, note])
            _ensure_writable(fallback)
            sealed, path = self._seal(record, fallback)
            self._drop_marker(primary, record.run_id)
            return sealed, path

    def _seal(self, record: RunRecord, folder: Path) -> tuple[RunRecord, str]:
        target = folder / f"{record.run_id}.json"
        with store_lock(folder):
            if target.exists():
                raise RunAlreadySealed(record.run_id)
            index = _read_index(folder)
            notes: list[str] = []
            if index.truncated_tail:
                self._repair_index_tail(folder, index)
                notes.append(
                    "index_truncated_line: an incomplete index line was discarded"
                )
            previous = index.entries[-1] if index.entries else None
            prev_hash = (previous or {}).get("record_hash") or GENESIS_HASH
            seq = int((previous or {}).get("seq") or 0) + 1
            data = record.to_dict()
            if notes:
                data["warnings"] = [*data["warnings"], *notes]
            data["seq"] = seq
            data["prev_record_hash"] = prev_hash
            data["record_hash"] = compute_record_hash(data)
            payload = orjson.dumps(
                data, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
            )
            tmp = folder / f"{record.run_id}.json.tmp"
            with open(tmp, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, target)
            with contextlib.suppress(OSError):
                os.chmod(target, stat.S_IREAD)
            line = canonical_json(
                {
                    "file": target.name,
                    "prev_record_hash": prev_hash,
                    "record_hash": data["record_hash"],
                    "run_id": record.run_id,
                    "seq": seq,
                    "started_at": data["started_at"],
                    "status": data["status"],
                }
            )
            with open(folder / INDEX_NAME, "ab") as handle:
                if self._needs_newline(folder):
                    handle.write(b"\n")
                handle.write(line + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._drop_marker(folder, record.run_id)
        return RunRecord.from_dict(data), str(target)

    @staticmethod
    def _needs_newline(folder: Path) -> bool:
        try:
            with open(folder / INDEX_NAME, "rb") as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    return False
                handle.seek(-1, os.SEEK_END)
                return handle.read(1) != b"\n"
        except OSError:
            return False

    @staticmethod
    def _repair_index_tail(folder: Path, index: _IndexRead) -> None:
        with open(folder / INDEX_NAME, "r+b") as handle:
            handle.truncate(index.good_length)

    @staticmethod
    def _drop_marker(folder: Path, run_id: str) -> None:
        with contextlib.suppress(OSError):
            os.unlink(folder / f"{run_id}.started")

    def save(
        self, record: RunRecord, directory: str | os.PathLike | None = None
    ) -> str:
        return self.seal_and_save(record, directory)[1]

    # -- reading --------------------------------------------------------
    def load_dict(self, path: str | os.PathLike) -> dict:
        return _read_record_dict(Path(path))

    def load(self, path: str | os.PathLike) -> RunRecord:
        return RunRecord.from_dict(self.load_dict(path))

    def list_runs(
        self,
        directory: str | os.PathLike | None = None,
        workflow_path: str | None = None,
    ) -> list[RunHeader]:
        """Runs in sequence order, from the index alone (no record is opened)."""
        folder = self._directory(directory, workflow_path)
        headers: list[RunHeader] = []
        for entry in _read_index(folder).entries:
            try:
                headers.append(
                    RunHeader(
                        seq=int(entry["seq"]),
                        run_id=str(entry["run_id"]),
                        started_at=str(entry.get("started_at", "")),
                        status=str(entry.get("status", "")),
                        record_hash=str(entry.get("record_hash", "")),
                        prev_record_hash=str(entry.get("prev_record_hash", "")),
                        file=str(entry.get("file") or f"{entry['run_id']}.json"),
                    )
                )
            except KeyError, TypeError, ValueError:
                continue
        return headers

    def latest_record_dict(
        self,
        directory: str | os.PathLike | None = None,
        workflow_path: str | None = None,
    ) -> dict | None:
        """The newest sealed record of a store, or ``None``."""
        folder = self._directory(directory, workflow_path)
        runs = self.list_runs(folder)
        if not runs:
            return None
        try:
            return self.load_dict(folder / runs[-1].file)
        except OSError, orjson.JSONDecodeError, TypeError:
            return None

    def verify(
        self,
        directory: str | os.PathLike | None = None,
        workflow_path: str | None = None,
    ) -> VerifyReport:
        return verify_store(self._directory(directory, workflow_path))
