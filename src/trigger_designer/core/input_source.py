"""Readers and union logic behind File Input's new source types.

Qt-free. Live evaluation and generated code both call :func:`build_source`,
so they cannot disagree. CSV stays all-``String``; typed formats keep their
native dtypes and cross-file dtype conflicts resolve deterministically.
"""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl
import sqlglot

from trigger_designer.core.inputs import (
    DEFAULT_EXCLUDE,
    FILE_TYPES,
    InputReadError,
    ListedFile,
    effective_mode,
    io_path,
    list_source_files,
)

SOURCE_KEYS = (
    "filePath",
    "file_type",
    "record_limit",
    "output_filename_as_field",
    "delimiter",
    "first_row_contains_field_names",
    "selected_sheet",
    "start_row",
    "include_patterns",
    "exclude_patterns",
    "recursive",
    "file_order",
    "file_name_column_name",
    "file_name_value",
    "schema_mismatch",
    "on_file_error",
    "max_files",
    "encoding",
    "read_as_text",
    "json_nested",
    "sheet_mode",
    "selected_sheets",
    "add_sheet_name_column",
    "sheet_name_column_name",
    "db_mode",
    "db_table",
    "db_query",
)

SOURCE_DEFAULTS: dict[str, Any] = {
    "filePath": "",
    "file_type": "csv",
    "record_limit": 0,
    "output_filename_as_field": False,
    "delimiter": ",",
    "first_row_contains_field_names": True,
    "selected_sheet": "",
    "start_row": 1,
    "include_patterns": (),
    "exclude_patterns": DEFAULT_EXCLUDE,
    "recursive": False,
    "file_order": "name",
    "file_name_column_name": "FileName",
    "file_name_value": "name",
    "schema_mismatch": "union",
    "on_file_error": "stop",
    "max_files": 10000,
    "encoding": "utf8",
    "read_as_text": False,
    "json_nested": "text",
    "sheet_mode": "one",
    "selected_sheets": (),
    "add_sheet_name_column": False,
    "sheet_name_column_name": "SheetName",
    "db_mode": "table",
    "db_table": "",
    "db_query": "",
}

_DB_TYPES = ("sqlite", "duckdb")
_COLUMN_RE = re.compile(r"column\s+[\"']([^\"']+)[\"']", re.IGNORECASE)


@dataclass(frozen=True)
class SourceSettings:
    filePath: str
    file_type: str
    record_limit: int
    output_filename_as_field: bool
    delimiter: str
    first_row_contains_field_names: bool
    selected_sheet: str
    start_row: int
    include_patterns: tuple[str, ...]
    exclude_patterns: tuple[str, ...]
    recursive: bool
    file_order: str
    file_name_column_name: str
    file_name_value: str
    schema_mismatch: str
    on_file_error: str
    max_files: int
    encoding: str
    read_as_text: bool
    json_nested: str
    sheet_mode: str
    selected_sheets: tuple[str, ...]
    add_sheet_name_column: bool
    sheet_name_column_name: str
    db_mode: str
    db_table: str
    db_query: str

    @property
    def mode(self) -> str:
        return effective_mode(self.filePath)

    @classmethod
    def from_state(cls, state: dict) -> SourceSettings:
        values: dict[str, Any] = {}
        for key in SOURCE_KEYS:
            default = SOURCE_DEFAULTS[key]
            value = state.get(key, default)
            if value is None:
                value = default
            if key in ("include_patterns", "exclude_patterns", "selected_sheets"):
                if isinstance(value, str):
                    value = tuple(
                        part.strip() for part in value.split(";") if part.strip()
                    )
                else:
                    value = tuple(value)
            elif key in (
                "recursive",
                "read_as_text",
                "add_sheet_name_column",
                "output_filename_as_field",
                "first_row_contains_field_names",
            ):
                value = bool(value)
            elif key in ("record_limit", "start_row", "max_files"):
                try:
                    value = int(value)
                except TypeError, ValueError:
                    raise InputReadError(
                        "config",
                        f"'{key}' must be a whole number.",
                        path=str(state.get("filePath") or ""),
                    ) from None
            else:
                value = str(value)
            values[key] = value

        if values["file_type"] not in FILE_TYPES:
            raise InputReadError(
                "config",
                f"Unknown file type '{values['file_type']}'.",
                path=values["filePath"],
            )
        allowed = {
            "file_order": ("name", "modified"),
            "file_name_value": ("name", "path", "relative"),
            "schema_mismatch": ("union", "error"),
            "on_file_error": ("stop", "skip"),
            "encoding": ("utf8", "utf8-lossy"),
            "json_nested": ("text", "keep"),
            "sheet_mode": ("one", "all", "chosen"),
            "db_mode": ("table", "query"),
        }
        for key, choices in allowed.items():
            if values[key] not in choices:
                raise InputReadError(
                    "config",
                    f"'{values[key]}' is not a valid {key.replace('_', ' ')}.",
                    path=values["filePath"],
                )
        values["start_row"] = max(values["start_row"], 1)
        return cls(**values)


@dataclass
class FileReport:
    path: str
    relative_path: str
    sheet: str | None
    status: str
    columns: list[str] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)
    extra_columns: list[str] = field(default_factory=list)
    dtype_conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: dict | None = None
    size_bytes: int | None = None

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "relative_path": self.relative_path,
            "sheet": self.sheet,
            "status": self.status,
            "columns": list(self.columns),
            "missing_columns": list(self.missing_columns),
            "extra_columns": list(self.extra_columns),
            "dtype_conflicts": list(self.dtype_conflicts),
            "warnings": list(self.warnings),
            "error": self.error,
            "size_bytes": self.size_bytes,
        }


@dataclass
class SourceReport:
    mode: str
    root: str
    file_count: int
    ok_count: int
    skipped_count: int
    excluded_count: int
    union_columns: list[str]
    reference_columns: list[str]
    warnings: list[str] = field(default_factory=list)
    files: list[FileReport] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "root": self.root,
            "file_count": self.file_count,
            "ok_count": self.ok_count,
            "skipped_count": self.skipped_count,
            "excluded_count": self.excluded_count,
            "union_columns": list(self.union_columns),
            "reference_columns": list(self.reference_columns),
            "warnings": list(self.warnings),
            "files": [item.as_dict() for item in self.files],
        }

    def differing_files(self) -> list[FileReport]:
        return [
            item
            for item in self.files
            if item.missing_columns or item.extra_columns or item.dtype_conflicts
        ]

    def summary(self) -> str:
        if not self.files:
            return "No files read."
        if self.skipped_count and not self.ok_count:
            return f"{self.file_count} files, none readable."
        parts = [f"{self.file_count} files"]
        differing = self.differing_files()
        if differing:
            first = differing[0]
            detail = ""
            name = first.relative_path or os.path.basename(first.path)
            if first.extra_columns:
                detail = f" (first: {name}: +{', +'.join(first.extra_columns)})"
            elif first.missing_columns:
                detail = f" (first: {name}: missing {', '.join(first.missing_columns)})"
            parts.append(f"{len(differing)} differ{detail}")
        if self.skipped_count:
            parts.append(f"{self.skipped_count} skipped")
        return ", ".join(parts)


@dataclass
class SourceResult:
    frame: pl.LazyFrame
    report: SourceReport


@dataclass(frozen=True)
class _Unit:
    sheet: str | None = None


@dataclass
class _Part:
    listed: ListedFile
    unit: _Unit
    frame: pl.LazyFrame
    columns: dict[str, Any]


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _sqlite_uri(path: str) -> str:
    posix = Path(os.path.abspath(path)).as_posix()
    escaped = posix.replace("%", "%25").replace("?", "%3f").replace("#", "%23")
    return "file:" + escaped + "?mode=ro"


@contextmanager
def _open_sqlite_ro(path: str):
    connection = sqlite3.connect(_sqlite_uri(io_path(path)), uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        allowed = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
            sqlite3.SQLITE_RECURSIVE,
        }
        connection.set_authorizer(
            lambda action, _a, _b, _db, _trig: (
                sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY
            )
        )
        yield connection
    finally:
        connection.close()


@contextmanager
def _open_duckdb_ro(path: str):
    import duckdb

    connection = duckdb.connect(os.path.abspath(path), read_only=True)
    try:
        connection.execute("SET enable_external_access=false")
        try:
            connection.execute("SET lock_configuration=true")
        except Exception:  # noqa: BLE001, S110 - older engines may not allow it
            pass
        yield connection
    finally:
        connection.close()


def list_db_tables(path: str, kind: str) -> list[str]:
    """Sorted table and view names, opened read-only."""
    try:
        if kind == "sqlite":
            with _open_sqlite_ro(path) as connection:
                rows = connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name"
                ).fetchall()
                return [row[0] for row in rows]
        with _open_duckdb_ro(path) as connection:
            rows = connection.execute(
                "SELECT table_name FROM information_schema.tables ORDER BY table_name"
            ).fetchall()
            return [row[0] for row in rows]
    except InputReadError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise InputReadError(
            "db_error",
            f"Cannot list tables in '{path}': {exc}",
            path=path,
            technical=str(exc),
            cause_type=type(exc).__name__,
        ) from None


def _reject_multi_statement(query: str, dialect: str) -> None:
    try:
        statements = sqlglot.parse(query, read=dialect)
    except Exception:  # noqa: BLE001 - let the engine be the guard
        return
    if len(statements) != 1:
        raise InputReadError(
            "db_forbidden",
            "Only one SELECT statement is allowed.",
            technical=str(query),
        )


def _sql_for(settings: SourceSettings, dialect: str) -> str:
    if settings.db_mode == "table":
        if not settings.db_table:
            raise InputReadError("config", "Choose a table.", path=settings.filePath)
        base = f"SELECT * FROM {_quote_ident(settings.db_table)}"
    else:
        raw = settings.db_query.strip()
        if not raw:
            raise InputReadError(
                "config", "Write a SELECT query.", path=settings.filePath
            )
        _reject_multi_statement(raw, dialect)
        base = raw.rstrip(";").strip()
    if settings.record_limit > 0:
        base = f"SELECT * FROM ({base}) AS _q LIMIT {int(settings.record_limit)}"
    return base


def _classify(
    exc: BaseException, path: str, sheet: str | None = None
) -> InputReadError:
    if isinstance(exc, InputReadError):
        return exc
    message = str(exc)
    technical = message
    cause_type = type(exc).__name__
    if isinstance(exc, FileNotFoundError):
        return InputReadError(
            "file_not_found",
            f"Cannot find the input file '{path}'.",
            path=path,
            sheet=sheet,
            technical=technical,
            cause_type=cause_type,
        )
    winerror = getattr(exc, "winerror", None)
    if (
        isinstance(exc, PermissionError)
        or winerror in (5, 32)
        or ("being used by another process" in message)
    ):
        return InputReadError(
            "locked",
            f"Cannot read '{path}': the file is open in another program or not allowed.",
            path=path,
            sheet=sheet,
            technical=technical,
            cause_type=cause_type,
        )
    if isinstance(exc, pl.exceptions.NoDataError):
        return InputReadError(
            "empty_file",
            f"'{path}' is empty.",
            path=path,
            sheet=sheet,
            technical=technical,
            cause_type=cause_type,
        )
    lowered = message.lower()
    if "invalid utf-8" in lowered or ("utf8" in lowered and "invalid" in lowered):
        return InputReadError(
            "encoding",
            f"'{path}' is not UTF-8 text. Set Encoding to 'UTF-8 (replace bad bytes)'.",
            path=path,
            sheet=sheet,
            technical=technical,
            cause_type=cause_type,
        )
    column = _extract_column(message)
    if cause_type == "SheetNotFoundError" or (
        "sheet" in lowered and "not found" in lowered
    ):
        return InputReadError(
            "sheet_missing",
            f"Worksheet '{sheet or 'requested'}' is missing from '{path}'.",
            path=path,
            sheet=sheet,
            technical=technical,
            cause_type=cause_type,
        )
    if "invalid Zip archive" in message or "EOCD" in message:
        return InputReadError(
            "parse",
            f"'{path}' is not a valid Excel workbook.",
            path=path,
            sheet=sheet,
            technical=technical,
            cause_type=cause_type,
        )
    if isinstance(exc, pl.exceptions.PolarsError):
        return InputReadError(
            "parse",
            f"Cannot read the data in '{path}': {message}",
            path=path,
            sheet=sheet,
            column=column,
            technical=technical,
            cause_type=cause_type,
        )
    if isinstance(exc, OSError):
        return InputReadError(
            "unreadable",
            f"Cannot open '{path}': {message}",
            path=path,
            sheet=sheet,
            technical=technical,
            cause_type=cause_type,
        )
    return InputReadError(
        "parse",
        f"Cannot read '{path}': {message}",
        path=path,
        sheet=sheet,
        column=column,
        technical=technical,
        cause_type=cause_type,
    )


def _extract_column(message: str) -> str | None:
    match = _COLUMN_RE.search(message)
    return match.group(1) if match else None


def _sql_error(exc: BaseException, path: str) -> InputReadError:
    message = str(exc)
    lowered = message.lower()
    if "could not set lock" in lowered or "being used by another process" in lowered:
        return InputReadError(
            "locked",
            f"Cannot read '{path}': the database is open for writing in another program.",
            path=path,
            technical=message,
            cause_type=type(exc).__name__,
        )
    if any(
        marker in lowered
        for marker in (
            "not authorized",
            "read-only",
            "cannot execute statement",
            "file system operations are disabled",
            "permission error",
            "not allowed",
        )
    ):
        return InputReadError(
            "db_forbidden",
            f"The query on '{path}' tried to change data or use files. Only SELECT is read.",
            path=path,
            technical=message,
            cause_type=type(exc).__name__,
        )
    return InputReadError(
        "db_error",
        f"Cannot read the database '{path}': {message}",
        path=path,
        technical=message,
        cause_type=type(exc).__name__,
    )


def _read_csv(path: str, settings: SourceSettings) -> pl.LazyFrame:
    options: dict[str, Any] = {"infer_schema": False, "encoding": settings.encoding}
    if settings.delimiter != ",":
        options["separator"] = settings.delimiter
    if not settings.first_row_contains_field_names:
        options["has_header"] = False
    return pl.scan_csv(io_path(path), **options)


def _read_parquet(path: str, settings: SourceSettings) -> pl.LazyFrame:
    del settings
    return pl.scan_parquet(io_path(path))


def _read_ndjson(path: str, settings: SourceSettings) -> pl.LazyFrame:
    del settings
    return pl.scan_ndjson(io_path(path))


def _read_json(path: str, settings: SourceSettings) -> pl.LazyFrame:
    del settings
    return pl.read_json(io_path(path)).lazy()


def _excel_reader(path: str, cache: dict[str, Any]):
    import fastexcel

    if path not in cache:
        cache[path] = fastexcel.read_excel(io_path(path))
    return cache[path]


def _read_excel(
    path: str,
    sheet: str | None,
    settings: SourceSettings,
    cache: dict[str, Any],
    *,
    multi_file: bool,
) -> pl.LazyFrame:
    reader = _excel_reader(path, cache)
    skip = settings.start_row - 1
    kwargs: dict[str, Any] = {}
    if settings.first_row_contains_field_names:
        kwargs["header_row"] = skip
    else:
        kwargs["header_row"] = None
        if skip:
            kwargs["skip_rows"] = skip
    if settings.record_limit > 0 and settings.sheet_mode == "one" and not multi_file:
        kwargs["n_rows"] = settings.record_limit
    loaded = reader.load_sheet(idx_or_name=sheet, **kwargs)
    if hasattr(loaded, "to_polars"):
        frame = loaded.to_polars()
    else:
        frame = pl.from_arrow(loaded.to_arrow())
    return frame.lazy()


def _read_db(path: str, settings: SourceSettings) -> pl.LazyFrame:
    dialect = settings.file_type
    query = _sql_for(settings, dialect)
    try:
        if dialect == "sqlite":
            with _open_sqlite_ro(path) as connection:
                frame = pl.read_database(query, connection)
        else:
            with _open_duckdb_ro(path) as connection:
                frame = connection.sql(query).pl()
    except InputReadError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _sql_error(exc, path) from None
    return frame.lazy()


def _preflight(path: str) -> None:
    with open(io_path(path), "rb"):
        pass


def _excel_sheet_names(path: str, cache: dict[str, Any]) -> list[str]:
    return list(_excel_reader(path, cache).sheet_names)


def _units_for(
    listed: ListedFile,
    settings: SourceSettings,
    cache: dict[str, Any],
) -> list[_Unit]:
    if settings.file_type != "excel":
        return [_Unit()]
    if settings.sheet_mode == "one":
        names = _excel_sheet_names(listed.path, cache)
        sheet = settings.selected_sheet or (names[0] if names else None)
        if not sheet:
            raise InputReadError(
                "config",
                f"The workbook '{listed.path}' has no worksheets.",
                path=listed.path,
            )
        return [_Unit(sheet)]
    if settings.sheet_mode == "all":
        return [_Unit(name) for name in _excel_sheet_names(listed.path, cache)]
    if not settings.selected_sheets:
        raise InputReadError("config", "Choose at least one sheet.", path=listed.path)
    return [_Unit(name) for name in settings.selected_sheets]


def _stringify_nested(frame: pl.LazyFrame) -> pl.LazyFrame:
    schema = frame.collect_schema()
    expressions = [
        pl.when(pl.col(name).is_null())
        .then(None)
        .otherwise(
            pl.struct(pl.col(name).alias("v"))
            .struct.json_encode()
            .str.json_path_match("$.v")
        )
        .alias(name)
        for name, dtype in schema.items()
        if isinstance(dtype, (pl.Struct, pl.List, pl.Array))
    ]
    return frame.with_columns(expressions) if expressions else frame


def _compute_differences(
    parts: list[_Part],
    reports: list[FileReport],
    settings: SourceSettings,
) -> list[str]:
    if not parts:
        return []
    reference = list(parts[0].columns)
    union = list(reference)
    for part in parts[1:]:
        for name in part.columns:
            if name not in union:
                union.append(name)
    by_key = {(item.path, item.sheet): item for item in reports if item.status == "ok"}
    ordered: list[FileReport] = []
    for part in parts:
        report = by_key.get((part.listed.path, part.unit.sheet))
        if report is None:
            continue
        report.missing_columns = [name for name in union if name not in part.columns]
        report.extra_columns = [name for name in part.columns if name not in reference]
        ordered.append(report)
    if settings.schema_mismatch == "error":
        offenders = [
            report
            for report in ordered
            if report.extra_columns or report.missing_columns
        ]
        if offenders:
            # Name the file that introduces a column first: that is the one
            # an auditor has to open, rather than every earlier file that
            # simply lacks it.
            report = next(
                (item for item in offenders if item.extra_columns), offenders[0]
            )
            column = (report.extra_columns or report.missing_columns)[0]
            raise InputReadError(
                "schema_mismatch",
                (
                    f"The files have different columns: "
                    f"'{report.relative_path or os.path.basename(report.path)}' "
                    f"differs at '{column}'."
                ),
                path=report.path,
                sheet=report.sheet,
                column=column,
            )
    return union


def _resolve_dtype_conflicts(parts: list[_Part], reports: list[FileReport]) -> None:
    if len(parts) < 2:
        return
    by_key = {(item.path, item.sheet): item for item in reports if item.status == "ok"}
    names: set[str] = set()
    for part in parts:
        names.update(part.columns)
    for name in names:
        dtypes = [part.columns[name] for part in parts if name in part.columns]
        if len({str(dtype) for dtype in dtypes}) <= 1:
            continue
        if all(dtype.is_numeric() for dtype in dtypes):
            continue
        for part in parts:
            if name not in part.columns:
                continue
            part.frame = part.frame.with_columns(
                pl.col(name).cast(pl.String, strict=False).alias(name)
            )
            part.columns[name] = pl.String
            report = by_key.get((part.listed.path, part.unit.sheet))
            if report is not None and name not in report.dtype_conflicts:
                report.dtype_conflicts.append(name)


def _decorate(part: _Part, settings: SourceSettings) -> pl.LazyFrame:
    frame = part.frame
    if settings.output_filename_as_field:
        column = settings.file_name_column_name or "FileName"
        if column in part.columns:
            raise InputReadError(
                "column_conflict",
                (
                    f"'{part.listed.path}' already has a column named "
                    f"'{column}'. Rename the filename column in File Input."
                ),
                path=part.listed.path,
                column=column,
            )
        if settings.file_name_value == "path":
            value = part.listed.path
        elif settings.file_name_value == "relative":
            value = part.listed.relative_path or os.path.basename(part.listed.path)
        else:
            value = os.path.basename(part.listed.path)
        frame = frame.with_columns(pl.lit(value).alias(column))
        part.columns[column] = pl.String
    if settings.add_sheet_name_column and part.unit.sheet is not None:
        column = settings.sheet_name_column_name or "SheetName"
        if column in part.columns:
            raise InputReadError(
                "column_conflict",
                (
                    f"'{part.listed.path}' already has a column named "
                    f"'{column}'. Rename the sheet name column in File Input."
                ),
                path=part.listed.path,
                sheet=part.unit.sheet,
                column=column,
            )
        frame = frame.with_columns(pl.lit(part.unit.sheet).alias(column))
        part.columns[column] = pl.String
    return frame


def build_source(state: dict) -> SourceResult:
    """Build one LazyFrame from a File Input settings dict.

    Live evaluation and generated code share this function. Listing happens
    first, then every file (and Excel sheet) contributes one part. Missing
    columns become nulls, extra columns append in first-seen order, and dtype
    conflicts that are not numeric resolve to ``String``.
    """
    settings = SourceSettings.from_state(state)

    if settings.mode == "empty":
        raise InputReadError("config", "Choose a file, folder or pattern.")

    listing = list_source_files(
        settings.filePath,
        settings.file_type,
        include=settings.include_patterns,
        exclude=settings.exclude_patterns,
        recursive=settings.recursive,
        order=settings.file_order,
        max_files=settings.max_files,
    )

    if settings.file_type in _DB_TYPES and listing.mode != "single":
        raise InputReadError(
            "unsupported_source",
            "Database sources take exactly one file.",
            path=settings.filePath,
        )

    parts: list[_Part] = []
    reports: list[FileReport] = []
    cache: dict[str, Any] = {}
    multi_file = len(listing.files) > 1
    duplicate_notes: list[str] = []

    for listed in listing.files:
        try:
            _preflight(listed.path)
            units = _units_for(listed, settings, cache)
        except Exception as exc:  # noqa: BLE001
            error = _classify(exc, listed.path)
            if settings.on_file_error == "stop":
                raise error from None
            reports.append(
                FileReport(
                    path=listed.path,
                    relative_path=listed.relative_path,
                    sheet=getattr(exc, "sheet", None),
                    status="skipped",
                    error=error.as_dict(),
                    size_bytes=listed.size_bytes,
                )
            )
            continue

        for unit in units:
            try:
                if settings.file_type in ("csv", "txt"):
                    frame = _read_csv(listed.path, settings)
                elif settings.file_type == "parquet":
                    frame = _read_parquet(listed.path, settings)
                elif settings.file_type == "json":
                    frame = _read_json(listed.path, settings)
                elif settings.file_type == "ndjson":
                    frame = _read_ndjson(listed.path, settings)
                elif settings.file_type == "excel":
                    frame = _read_excel(
                        listed.path,
                        unit.sheet,
                        settings,
                        cache,
                        multi_file=multi_file,
                    )
                elif settings.file_type in _DB_TYPES:
                    frame = _read_db(listed.path, settings)
                else:  # pragma: no cover - SourceSettings validates the type
                    raise InputReadError(
                        "config", f"Unsupported file type '{settings.file_type}'."
                    )
                columns = dict(frame.collect_schema())
            except Exception as exc:  # noqa: BLE001
                error = (
                    exc
                    if isinstance(exc, InputReadError)
                    else _classify(exc, listed.path, unit.sheet)
                )
                if isinstance(exc, InputReadError) and error.sheet is None:
                    error.sheet = unit.sheet
                if settings.on_file_error == "stop":
                    raise error from None
                reports.append(
                    FileReport(
                        path=listed.path,
                        relative_path=listed.relative_path,
                        sheet=unit.sheet,
                        status="skipped",
                        error=error.as_dict(),
                        size_bytes=listed.size_bytes,
                    )
                )
                continue
            parts.append(_Part(listed, unit, frame, columns))
            duplicate_notes.extend(_duplicate_warnings(listed, columns))
            reports.append(
                FileReport(
                    path=listed.path,
                    relative_path=listed.relative_path,
                    sheet=unit.sheet,
                    status="ok",
                    columns=list(columns),
                    size_bytes=listed.size_bytes,
                )
            )

    if not parts:
        raise InputReadError(
            "no_readable_files",
            f"None of the {len(listing.files)} files in '{settings.filePath}' could be read.",
            path=settings.filePath,
        )

    reference = _compute_differences(parts, reports, settings)
    _resolve_dtype_conflicts(parts, reports)
    frames = [_decorate(part, settings) for part in parts]
    frame = frames[0] if len(frames) == 1 else pl.concat(frames, how="diagonal_relaxed")
    frame = _added_columns_last(frame, settings)

    if settings.file_type in ("json", "ndjson") and settings.json_nested == "text":
        frame = _stringify_nested(frame)
    if settings.read_as_text:
        frame = _stringify_nested(frame)
        frame = frame.with_columns(pl.all().cast(pl.String, strict=False))
    if settings.record_limit > 0:
        frame = frame.head(settings.record_limit)

    union_columns = list(frame.collect_schema())
    report = SourceReport(
        mode=listing.mode,
        root=listing.root,
        file_count=len(listing.files),
        ok_count=sum(1 for item in reports if item.status == "ok"),
        skipped_count=sum(1 for item in reports if item.status == "skipped"),
        excluded_count=listing.excluded_count,
        union_columns=union_columns,
        reference_columns=reference,
        warnings=list(listing.warnings) + duplicate_notes,
        files=reports,
    )
    return SourceResult(frame=frame, report=report)


def _added_columns_last(frame: pl.LazyFrame, settings: SourceSettings) -> pl.LazyFrame:
    """Keep configured columns after the data's own columns.

    Decorating each part before the union is required (the value differs per
    file), but a diagonal concat then places the first part's added column
    before columns that only later files carry. Readers expect the data's
    first-seen order followed by the configured columns.
    """
    added: list[str] = []
    if settings.output_filename_as_field:
        added.append(settings.file_name_column_name or "FileName")
    if settings.add_sheet_name_column:
        added.append(settings.sheet_name_column_name or "SheetName")
    if not added:
        return frame
    schema = list(frame.collect_schema())
    order = [name for name in schema if name not in added]
    order.extend(name for name in added if name in schema)
    return frame.select(order)


def _duplicate_warnings(listed: ListedFile, columns: dict[str, Any]) -> list[str]:
    duplicates = [name for name in columns if "_duplicated_" in name]
    if not duplicates:
        return []
    return [
        (
            f"{listed.relative_path or os.path.basename(listed.path)} had duplicate "
            f"column names; Polars renamed them to {', '.join(duplicates)} "
            "(TD-SCH-002)."
        )
    ]


def diagnose_collect_error(
    exc: BaseException, report: SourceReport | None
) -> InputReadError:
    """Turn a late ``collect()`` failure into a file/column-aware error."""
    message = str(exc)
    lowered = message.lower()
    path: str | None = None
    if report is not None:
        for item in report.files:
            if item.path and (
                item.path in message or os.path.basename(item.path) in message
            ):
                path = item.path
                break
        if path is None and len(report.files) == 1:
            # A body-level parse error usually omits the file name; with one
            # file there is no ambiguity about which one it was.
            path = report.files[0].path
    column = _extract_column(message)
    if "invalid utf-8" in lowered:
        return InputReadError(
            "encoding",
            (
                f"'{path or 'The input'}' is not UTF-8 text. "
                "Set Encoding to 'UTF-8 (replace bad bytes)'."
            ),
            path=path,
            column=column,
            technical=message,
            cause_type=type(exc).__name__,
        )
    technical = message
    if report is not None:
        technical = (
            message + "\nFiles: " + ", ".join(item.path for item in report.files)
        )
    return InputReadError(
        "parse",
        f"Cannot read the data in '{path or 'the input files'}': {message}",
        path=path,
        column=column,
        technical=technical,
        cause_type=type(exc).__name__,
    )
