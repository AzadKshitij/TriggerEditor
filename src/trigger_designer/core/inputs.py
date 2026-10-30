"""Input file discovery and path helpers for File Input.

This module is deliberately free of Polars, Qt and heavy readers. Reading lives
in ``trigger_designer.core.input_source``.
"""

from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from functools import cache
from typing import Any

FILE_TYPES = ("csv", "txt", "excel", "parquet", "json", "ndjson", "sqlite", "duckdb")

DEFAULT_INCLUDE: dict[str, tuple[str, ...]] = {
    "csv": ("*.csv",),
    "txt": ("*.txt",),
    "excel": ("*.xlsx", "*.xlsm", "*.xls"),
    "parquet": ("*.parquet", "*.pq"),
    "json": ("*.json",),
    "ndjson": ("*.ndjson", "*.jsonl"),
    "sqlite": (),
    "duckdb": (),
}

#: Largest ``max_files`` the dock and the command line accept.
MAX_FILES_LIMIT = 100_000

DEFAULT_EXCLUDE = ("~$*", ".*", "Thumbs.db", "desktop.ini")
GLOB_CHARS = "*?["

_EXTENSION_TO_TYPE = {
    ".csv": "csv",
    ".tsv": "csv",
    ".txt": "txt",
    ".xlsx": "excel",
    ".xlsm": "excel",
    ".xls": "excel",
    ".parquet": "parquet",
    ".pq": "parquet",
    ".json": "json",
    ".ndjson": "ndjson",
    ".jsonl": "ndjson",
    ".sqlite": "sqlite",
    ".sqlite3": "sqlite",
    ".duckdb": "duckdb",
    ".ddb": "duckdb",
}

_DB_TYPES = ("sqlite", "duckdb")

#: ``kind`` -> plan-03 error code. Kinds not listed fall back to TD-IN-014.
_KIND_TO_CODE = {
    "file_not_found": "TD-IN-001",
    "no_match": "TD-IN-001",
    "permission": "TD-IN-002",
    "locked": "TD-IN-002",
    "sheet_missing": "TD-IN-003",
    "encoding": "TD-IN-004",
    "empty_file": "TD-IN-005",
    "parse": "TD-IN-010",
    "unreadable": "TD-IN-011",
    "too_many_files": "TD-IN-012",
    "db_error": "TD-IN-013",
    "db_forbidden": "TD-IN-013",
    "config": "TD-IN-014",
    "unsupported_source": "TD-IN-014",
    "no_readable_files": "TD-IN-014",
    "schema_mismatch": "TD-SCH-011",
    "column_conflict": "TD-SCH-010",
}


class InputReadError(Exception):
    """A structured input failure that keeps the file, sheet and column.

    The human sentence in ``message`` always names the file; plan 03 turns
    this object into a :class:`NodeError` using :attr:`code` without regex
    matching. ``kind`` stays the stable internal key.
    """

    def __init__(
        self,
        kind: str,
        message: str,
        *,
        path: str | None = None,
        sheet: str | None = None,
        column: str | None = None,
        technical: str = "",
        cause_type: str = "",
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.path = path
        self.sheet = sheet
        self.column = column
        self.technical = technical
        self.cause_type = cause_type

    @property
    def code(self) -> str:
        if self.kind == "parse" and (
            "invalid Zip archive" in self.technical or "EOCD" in self.technical
        ):
            return "TD-IN-006"
        return _KIND_TO_CODE.get(self.kind, "TD-IN-014")

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": self.message,
            "path": self.path,
            "sheet": self.sheet,
            "column": self.column,
            "technical": self.technical,
            "cause_type": self.cause_type,
            "code": self.code,
        }


@dataclass(frozen=True)
class ListedFile:
    path: str
    relative_path: str
    size_bytes: int
    mtime_ns: int


@dataclass
class FileListing:
    files: list[ListedFile]
    mode: str
    root: str
    excluded_count: int
    warnings: list[str]


_NUM = re.compile(r"(\d+)")


def natural_key(text: str) -> tuple:
    """Sort key where ``part_2`` comes before ``part_10`` and case is ignored."""
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in _NUM.split(text)
        if part != ""
    ) + ((2, text),)


@cache
def glob_to_regex(pattern: str) -> re.Pattern:
    """Compile a shell-like pattern; ``**`` crosses directories, always ci."""
    return re.compile(
        glob.translate(
            pattern.replace("\\", "/"),
            recursive=True,
            include_hidden=True,
            seps="/",
        ),
        re.IGNORECASE,
    )


def has_glob(text: str) -> bool:
    return any(char in text for char in GLOB_CHARS)


def effective_mode(path_text: str) -> str:
    """Derive the source mode from the path text alone.

    Derived, never stored, so a CLI override of ``filePath`` cannot leave the
    mode out of sync with the path.
    """
    text = (path_text or "").strip()
    if not text:
        return "empty"
    if os.path.isdir(io_path(text)):
        return "folder"
    # An existing file wins over glob characters: "[" and "]" are legal in names.
    if os.path.isfile(io_path(text)):
        return "single"
    if has_glob(text):
        return "pattern"
    return "single"


def detect_file_type(path_text: str) -> str:
    """Extension table from the plan; ``.db`` sniffs the SQLite header."""
    extension = os.path.splitext(path_text)[1].lower()
    if extension == ".db":
        try:
            with open(io_path(path_text), "rb") as handle:
                header = handle.read(16)
        except OSError:
            return "sqlite"
        return "sqlite" if header == b"SQLite format 3\x00" else "duckdb"
    return _EXTENSION_TO_TYPE.get(extension, "csv")


def io_path(path: str) -> str:
    """Windows long-path safe form; identity elsewhere and for short paths."""
    if os.name != "nt" or not path:
        return path
    expanded = os.path.abspath(path)
    if len(expanded) <= 240 or expanded.startswith("\\\\?\\"):
        return expanded
    if expanded.startswith("\\\\"):
        return "\\\\?\\UNC\\" + expanded[2:]
    return "\\\\?\\" + expanded


def _glob_dir(text: str) -> str:
    """Directory prefix before the first glob segment, for existence checks."""
    parts = text.replace("\\", "/").split("/")
    fixed: list[str] = []
    for part in parts:
        if has_glob(part):
            break
        fixed.append(part)
    prefix = "/".join(fixed)
    if not prefix:
        return os.path.abspath(os.sep)
    if len(fixed) == len(parts):
        return prefix
    return prefix or os.path.abspath(os.sep)


def _matches(name: str, patterns) -> bool:
    return any(glob_to_regex(pattern).match(name) for pattern in patterns)


def _walk_files(
    root: str, *, recursive: bool, max_depth: int | None = None
) -> tuple[list[tuple[str, str]], list[str]]:
    """Yield ``(absolute, relative_posix)`` under ``root``.

    Directory symlinks are never descended. File symlinks are followed and a
    broken one becomes a warning instead of a crash.
    """
    found: list[tuple[str, str]] = []
    warnings: list[str] = []
    stack: list[tuple[str, int]] = [(root, 0)]
    while stack:
        directory, depth = stack.pop()
        try:
            entries = list(os.scandir(io_path(directory)))
        except OSError as exc:
            warnings.append(f"Cannot list '{directory}': {exc}")
            continue
        for entry in entries:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                is_dir = False
            if is_dir:
                if recursive or (max_depth is not None and depth < max_depth):
                    stack.append((entry.path, depth + 1))
                continue
            try:
                is_file = entry.is_file()
            except OSError:
                warnings.append(f"Skipping broken link '{entry.path}'")
                continue
            if not is_file:
                continue
            relative = os.path.relpath(entry.path, root).replace("\\", "/")
            found.append((os.path.normpath(entry.path), relative))
    return found, warnings


def list_source_files(
    path_text: str,
    file_type: str,
    *,
    include: tuple[str, ...] | list[str] = (),
    exclude: tuple[str, ...] | list[str] = DEFAULT_EXCLUDE,
    recursive: bool = False,
    order: str = "name",
    max_files: int = 10000,
) -> FileListing:
    """List the files a File Input will read, in deterministic order.

    Raises :class:`InputReadError` for a missing path, a pattern with no
    matches, a database given a folder/pattern, or more files than ``max_files``.
    """
    mode = effective_mode(path_text)
    text = (path_text or "").strip()
    include_patterns = tuple(include or DEFAULT_INCLUDE.get(file_type, ()))
    exclude_patterns = tuple(exclude or ())
    warnings: list[str] = []
    excluded_count = 0

    if mode == "empty":
        raise InputReadError("config", "Choose a file, folder or pattern.")

    if mode == "single":
        if not os.path.exists(io_path(text)):
            raise InputReadError(
                "file_not_found",
                f"Cannot find the input file '{text}'.",
                path=text,
            )
        stat = os.stat(io_path(text))
        relative = os.path.basename(text)
        files = [ListedFile(text, relative, stat.st_size, stat.st_mtime_ns)]
        return FileListing(files, mode, os.path.dirname(text), 0, warnings)

    if file_type in _DB_TYPES:
        raise InputReadError(
            "unsupported_source",
            f"Database sources take exactly one file, not a folder or pattern: '{text}'.",
            path=text,
        )

    files: list[ListedFile] = []
    if mode == "folder":
        root = text
        candidates, walk_warnings = _walk_files(root, recursive=recursive)
        warnings.extend(walk_warnings)
        for path, relative in candidates:
            name = os.path.basename(path)
            if _matches(name, exclude_patterns) or not _matches(name, include_patterns):
                excluded_count += 1
                continue
            stat = os.stat(io_path(path))
            files.append(ListedFile(path, relative, stat.st_size, stat.st_mtime_ns))
    else:  # pattern
        normalized = text.replace("\\", "/")
        parts = normalized.split("/")
        fixed: list[str] = []
        remainder_parts: list[str] = []
        for index, part in enumerate(parts):
            if has_glob(part):
                remainder_parts = parts[index:]
                break
            fixed.append(part)
        root = "/".join(fixed) or "."
        if os.name == "nt" and len(root) == 2 and root[1] == ":":
            root += "/"
        remainder = "/".join(remainder_parts)
        if not remainder:
            remainder = os.path.basename(normalized)
            root = os.path.dirname(normalized) or "."
        max_depth = None if "**" in remainder else remainder.count("/")
        candidates, walk_warnings = _walk_files(
            root, recursive="**" in remainder, max_depth=max_depth
        )
        warnings.extend(walk_warnings)
        matcher = glob_to_regex(remainder)
        for path, relative in candidates:
            name = os.path.basename(path)
            if _matches(name, exclude_patterns) or not matcher.match(relative):
                excluded_count += 1
                continue
            stat = os.stat(io_path(path))
            files.append(ListedFile(path, relative, stat.st_size, stat.st_mtime_ns))

    if not files:
        pattern = remainder if mode == "pattern" else ", ".join(include_patterns)
        raise InputReadError(
            "no_match",
            f"No files in '{text}' match {pattern}.",
            path=text,
        )
    if len(files) > max_files:
        raise InputReadError(
            "too_many_files",
            f"'{text}' matches {len(files)} files (limit {max_files}).",
            path=text,
        )
    if order == "modified":
        files.sort(key=lambda item: (item.mtime_ns, natural_key(item.relative_path)))
    else:
        files.sort(key=lambda item: natural_key(item.relative_path))
    return FileListing(files, mode, root, excluded_count, warnings)


def to_stored_paths(abs_path: str, workflow_dir: str | None) -> tuple[str, str]:
    """Return ``(absolute, relative-or-empty)`` for a stored ``.tds``."""
    if not abs_path or not workflow_dir:
        return abs_path, ""
    try:
        relative = os.path.relpath(abs_path, workflow_dir).replace("\\", "/")
    except ValueError:
        return abs_path, ""
    parents = 0
    probe = relative
    while probe == ".." or probe.startswith("../"):
        parents += 1
        probe = probe[2:] if probe.startswith("../") else ""
    if parents > 6:
        return abs_path, ""
    return abs_path, relative


def resolve_stored_path(abs_path: str, rel_path: str, workflow_dir: str | None) -> str:
    """Prefer the relative target, fall back to the stored absolute path."""
    if rel_path and workflow_dir:
        candidate = os.path.normpath(os.path.join(workflow_dir, rel_path))
        check = _glob_dir(candidate) if has_glob(candidate) else candidate
        if os.path.exists(io_path(check)):
            return candidate
    return abs_path
