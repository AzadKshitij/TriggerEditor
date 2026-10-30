"""File fingerprints: streamed SHA-256, a persistent cache, output row counts.

docs/plan/02-audit-trail.md 3.5 and 3.6. Qt-free; ``polars`` and ``openpyxl``
are imported lazily so importing this module stays cheap.
"""

from __future__ import annotations

import hashlib
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson
from loguru import logger

from trigger_designer.core.audit.schema import FileFingerprint

DEFAULT_CHUNK = 8 * 1024 * 1024
DEFAULT_HASH_MAX_BYTES = 2 * 1024**3
CACHE_FILENAME = "hash_cache.json"


def normalise_path(path: str | os.PathLike) -> str:
    """Cache key form: absolute and case-folded on Windows."""
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def recorded_path(path: str | os.PathLike) -> str:
    """The form stored in a record: absolute, forward slashes."""
    return os.path.abspath(os.fspath(path)).replace("\\", "/")


def _mtime_iso(mtime_ns: int) -> str:
    seconds, nanos = divmod(mtime_ns, 1_000_000_000)
    stamp = datetime.fromtimestamp(seconds, UTC).replace(microsecond=nanos // 1000)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class FingerprintCache:
    """``(path, size, mtime_ns) -> sha256``, in memory and optionally on disk.

    The disk copy is advisory and not part of the hash chain; a corrupt file is
    renamed to ``hash_cache.json.bad`` and ignored.
    """

    def __init__(self, path: Path | None = None, max_entries: int = 2000) -> None:
        self._path = Path(path) if path else None
        self._max = max_entries
        self._entries: dict[str, str] = {}
        self._loaded = False
        self._dirty = False
        self._lock = threading.Lock()

    @staticmethod
    def _key(path: str, size: int, mtime_ns: int) -> str:
        return f"{normalise_path(path)}|{size}|{mtime_ns}"

    def bind(self, path: Path | None) -> None:
        """Point the cache at a file (the store folder is only known at begin)."""
        with self._lock:
            if path != self._path:
                self._path = Path(path) if path else None
                self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if self._path is None or not self._path.is_file():
            return
        try:
            data = orjson.loads(self._path.read_bytes())
            entries = data.get("entries") if isinstance(data, dict) else None
            if not isinstance(entries, dict):
                raise ValueError("no entries")
            for key, value in entries.items():
                if isinstance(key, str) and isinstance(value, str):
                    self._entries.setdefault(key, value)
        except Exception:  # noqa: BLE001 - an advisory file must never stop a run
            try:
                os.replace(self._path, str(self._path) + ".bad")
            except OSError:
                pass

    def get(self, path: str, size: int, mtime_ns: int) -> str | None:
        with self._lock:
            self._load()
            return self._entries.get(self._key(path, size, mtime_ns))

    def put(self, path: str, size: int, mtime_ns: int, sha256: str) -> None:
        with self._lock:
            self._load()
            key = self._key(path, size, mtime_ns)
            self._entries.pop(key, None)  # re-insert: newest last
            self._entries[key] = sha256
            while len(self._entries) > self._max:
                self._entries.pop(next(iter(self._entries)))
            self._dirty = True

    def save(self) -> None:
        """Atomic tmp + replace; every ``OSError`` is swallowed."""
        with self._lock:
            if self._path is None or not self._dirty:
                return
            tmp = self._path.with_name(self._path.name + ".tmp")
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_bytes(orjson.dumps({"entries": self._entries}))
                os.replace(tmp, self._path)
                self._dirty = False
            except OSError as exc:
                logger.debug("hash cache not saved: {}", exc)
                try:
                    tmp.unlink()
                except OSError:
                    pass

    def __len__(self) -> int:
        with self._lock:
            self._load()
            return len(self._entries)


def sha256_stream(
    path: str | os.PathLike,
    *,
    cancel: threading.Event | None = None,
    chunk: int = DEFAULT_CHUNK,
) -> str | None:
    """SHA-256 of a file, ``None`` when ``cancel`` was set before it finished."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            if cancel is not None and cancel.is_set():
                return None
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def fingerprint_file(
    path: str | os.PathLike,
    role: str,
    node_id: int | None = None,
    sheet: str | None = None,
    *,
    cache: FingerprintCache | None = None,
    cancel: threading.Event | None = None,
    hash_enabled: bool = True,
    hash_max_bytes: int = DEFAULT_HASH_MAX_BYTES,
    use_cache: bool = True,
    chunk: int = DEFAULT_CHUNK,
) -> FileFingerprint:
    """Stat (and normally hash) one file; never raises."""
    shown = recorded_path(path)
    base = {"role": role, "path": shown, "node_id": node_id, "sheet": sheet or None}
    try:
        info = os.stat(path)
    except FileNotFoundError:
        return FileFingerprint(
            **base, sha256_status="missing", error="FileNotFoundError"
        )
    except OSError as exc:
        return FileFingerprint(
            **base, sha256_status="error", error=f"{type(exc).__name__}: {exc}"
        )
    size, mtime_ns = info.st_size, info.st_mtime_ns
    stat_fields = {
        **base,
        "size_bytes": size,
        "mtime_ns": mtime_ns,
        "modified_time": _mtime_iso(mtime_ns),
    }
    if not hash_enabled:
        return FileFingerprint(**stat_fields, sha256_status="disabled")
    if size > hash_max_bytes:
        return FileFingerprint(**stat_fields, sha256_status="skipped_size_limit")
    if cache is not None and use_cache:
        hit = cache.get(shown, size, mtime_ns)
        if hit:
            return FileFingerprint(**stat_fields, sha256=hit, sha256_status="cached")
    try:
        digest = sha256_stream(path, cancel=cancel, chunk=chunk)
    except OSError as exc:
        return FileFingerprint(
            **stat_fields,
            sha256_status="error",
            error=f"{type(exc).__name__}: {exc}",
        )
    if digest is None:
        return FileFingerprint(**stat_fields, sha256_status="cancelled")
    if cache is not None:
        cache.put(shown, size, mtime_ns, digest)
    return FileFingerprint(**stat_fields, sha256=digest, sha256_status="computed")


def _scan_len(scan: Any) -> int:
    import polars as pl

    return int(scan.select(pl.len()).collect(engine="streaming").item())


def count_rows_in_file(
    path: str | os.PathLike, fmt: str, delimiter: str = ","
) -> int | None:
    """Rows written to an output file, ``None`` when it cannot be counted.

    Never counts newlines: quoted CSV fields may contain them.
    """
    try:
        import polars as pl

        path = os.fspath(path)
        if fmt in ("csv", "custom_delimited"):
            return _scan_len(
                pl.scan_csv(
                    path,
                    separator=delimiter or ",",
                    infer_schema=False,
                    has_header=True,
                )
            )
        if fmt == "parquet":
            return _scan_len(pl.scan_parquet(path))
        if fmt == "ipc":
            return _scan_len(pl.scan_ipc(path))
        if fmt == "ndjson":
            return _scan_len(pl.scan_ndjson(path))
        if fmt == "json":
            return int(pl.read_json(path).height)
        if fmt == "excel":
            import openpyxl  # lazy: slow import, optional

            workbook = openpyxl.load_workbook(path, read_only=True)
            try:
                sheet = workbook.worksheets[0]
                return max(0, int(sheet.max_row or 0) - 1)
            finally:
                workbook.close()
    except Exception as exc:  # noqa: BLE001 - counting is best effort
        logger.debug("cannot count rows of {}: {}", path, exc)
    return None
