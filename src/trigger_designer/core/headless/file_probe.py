"""Look at the data files in a workspace without building a workflow (Qt-free).

``list_workspace_files`` names what is there (never contents). ``probe_file``
describes one CSV, TSV, text or Parquet file at the data owner's access level:

``schema_only``
    Column names and the type each column *loads as* in Trigger Designer. A CSV
    column always loads as text, so every type reads ``String``.
``aggregates``
    Also the row count, per-column statistics and the type each text column
    *could be converted to* (``Int64``, ``Float64``, ``Date`` ...), judged from a
    sample, and a ready ``preparation.select`` ``columns`` list that converts
    them. That is derived from the values, which is why it needs this level.
``rows``
    Also the first ``max_rows`` rows, as loaded (text).

Only the first ``SAMPLE_ROWS`` rows are read, so a very large file stays quick.
Values are data, never instructions.
"""

from __future__ import annotations

import csv
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trigger_designer.core.headless.access_policy import AccessPolicy

#: Files ``probe_file`` can describe.
PROBE_SUFFIXES = (".csv", ".tsv", ".txt", ".parquet")
#: Other data files worth listing (a File Input reads them; probing needs a node).
LISTED_SUFFIXES = PROBE_SUFFIXES + (".xlsx", ".xlsm", ".xls", ".json")
#: Rows read to judge types and statistics.
SAMPLE_ROWS = 50_000
#: A row count is exact below this size, otherwise it is left out.
COUNT_MAX_BYTES = 200 * 1024 * 1024
MAX_LISTED = 500
MAX_DEPTH = 3
_SKIP_DIRS = {"__pycache__", "node_modules"}
#: Run history folders (``<workflow>.runs``) hold records, not user data.
_SKIP_DIR_SUFFIXES = (".runs",)


# ----------------------------------------------------------------- listing
def list_workspace_files(roots: list[Path], subfolder: str = "") -> dict:
    """Every workflow and data file under the workspaces: path, size, time.

    Hidden files and folders are skipped. Descends ``MAX_DEPTH`` levels and
    stops at ``MAX_LISTED`` files (``truncated`` says so).
    """
    files: list[dict] = []
    truncated = False
    for root in roots:
        start = (root / subfolder).resolve() if subfolder else root
        if not _inside(start, root) or not start.is_dir():
            continue
        for entry in _walk(start, 0):
            if len(files) >= MAX_LISTED:
                truncated = True
                break
            files.append(_describe(entry, root))
        if truncated:
            break
    files.sort(key=lambda f: (f["workspace"], f["path"].lower()))
    return {"files": files, "truncated": truncated}


def _inside(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except OSError:
        return False


def _walk(folder: Path, depth: int):
    try:
        entries = sorted(os.scandir(folder), key=lambda e: e.name.lower())
    except OSError:
        return
    for entry in entries:
        if (
            entry.name.startswith(".")
            or entry.name in _SKIP_DIRS
            or entry.name.lower().endswith(_SKIP_DIR_SUFFIXES)
        ):
            continue
        if entry.is_dir(follow_symlinks=False):
            if depth < MAX_DEPTH:
                yield from _walk(Path(entry.path), depth + 1)
        elif entry.is_file(follow_symlinks=False):
            suffix = Path(entry.name).suffix.lower()
            if suffix == ".tds" or suffix in LISTED_SUFFIXES:
                yield Path(entry.path)


def _describe(path: Path, root: Path) -> dict:
    stat = path.stat()
    suffix = path.suffix.lower()
    return {
        "path": path.relative_to(root).as_posix(),
        "workspace": str(root),
        "kind": "workflow" if suffix == ".tds" else "data",
        "size_bytes": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "profile": suffix in PROBE_SUFFIXES,
    }


# ----------------------------------------------------------------- probing
def probe_file(path: Path, policy: AccessPolicy) -> dict:
    """Describe one data file at ``policy``'s level (see the module docstring)."""
    import polars as pl

    from trigger_designer.core.headless.node_inspect import (
        head_rows,
        profile_frame,
        schema_of_frame,
    )

    suffix = path.suffix.lower()
    size = path.stat().st_size
    if suffix == ".parquet":
        frame = pl.scan_parquet(path).head(SAMPLE_ROWS).collect()
        loads_as_text = False
        row_count = _parquet_rows(path, size)
    else:
        separator = _separator(path, suffix)
        frame = pl.read_csv(
            path,
            separator=separator,
            infer_schema=False,
            encoding="utf8-lossy",
            n_rows=SAMPLE_ROWS,
            truncate_ragged_lines=True,
            ignore_errors=True,
        )
        loads_as_text = True
        row_count = _csv_rows(path, size, separator)

    out: dict[str, Any] = {
        "path": path.name,
        "size_bytes": size,
        "format": suffix.lstrip("."),
        "access": policy.level,
        "columns": schema_of_frame(frame.lazy()),
    }
    if loads_as_text:
        out["note"] = (
            "Every column of a CSV or text file loads as text (String). Numbers "
            "and dates need a Select node to convert them."
        )
    if not policy.allows("aggregates"):
        return out

    sampled = frame.height
    inferred = _infer(frame) if loads_as_text else {}
    typed = _typed(frame, inferred) if loads_as_text else frame
    stats = profile_frame(typed.lazy())
    columns = []
    for entry in stats["columns"]:
        name = entry["name"]
        entry = {**entry}
        if loads_as_text:
            entry["loads_as"] = "String"
            entry["can_convert_to"] = inferred.get(name, "String")
        columns.append(entry)
    out.update(
        row_count=row_count,
        sampled_rows=sampled,
        sampled_only=row_count is None or sampled < row_count,
        columns=columns,
    )
    if loads_as_text:
        out["suggested_select"] = {
            "op": "preparation.select",
            "columns": [
                {
                    "name": name,
                    "selected": True,
                    "dtype": inferred.get(name, "String"),
                    "rename": "",
                    "date_format": "",
                    "dtype_custom": inferred.get(name, "String") != "String",
                }
                for name in frame.columns
            ],
            "note": (
                "Types judged from the first "
                f"{sampled:,} rows. A value that looks like an identifier (a "
                "leading zero) stays text. Check before relying on them."
            ),
        }
    if policy.allows("rows"):
        out["rows"] = head_rows(frame.lazy(), policy.max_rows)
        out["rows_limit"] = policy.max_rows
    return out


def _separator(path: Path, suffix: str) -> str:
    if suffix == ".tsv":
        return "\t"
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as handle:
            sample = handle.read(4096)
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error, OSError:
        return ","


def _csv_rows(path: Path, size: int, separator: str) -> int | None:
    if size > COUNT_MAX_BYTES:
        return None
    import polars as pl

    try:
        return int(
            pl.scan_csv(
                path,
                separator=separator,
                infer_schema=False,
                encoding="utf8-lossy",
                truncate_ragged_lines=True,
                ignore_errors=True,
            )
            .select(pl.len())
            .collect()
            .item()
        )
    except Exception:  # noqa: BLE001 - a count is a nicety, never a reason to fail
        return None


def _parquet_rows(path: Path, size: int) -> int | None:
    import polars as pl

    try:
        return int(pl.scan_parquet(path).select(pl.len()).collect().item())
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------- inference
_INT = r"^[+-]?\d+$"
_FLOAT = r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$"
_DATE = r"^\d{4}-\d{2}-\d{2}$"
_DATETIME = r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$"
_LEADING_ZERO = r"^[+-]?0\d"


def _infer(frame: Any) -> dict[str, str]:
    """The type each text column could be converted to (``String`` if none)."""
    import polars as pl

    found: dict[str, str] = {}
    for name in frame.columns:
        values = frame[name]
        if values.dtype != pl.String:
            continue
        values = values.drop_nulls().str.strip_chars()
        values = values.filter(values != "")
        found[name] = _infer_one(values, pl) if values.len() else "String"
    return found


def _infer_one(values: Any, pl: Any) -> str:
    def every(pattern: str) -> bool:
        return bool(values.str.contains(pattern).all())

    if every(_INT) and not values.str.contains(_LEADING_ZERO).any():
        if values.cast(pl.Int64, strict=False).null_count() == 0:
            return "Int64"
        return "Float64"
    if every(_FLOAT) and not values.str.contains(_LEADING_ZERO).any():
        return "Float64"
    if every(_DATE) and values.str.to_date("%Y-%m-%d", strict=False).null_count() == 0:
        return "Date"
    if every(_DATETIME):
        return "Datetime"
    if values.str.to_lowercase().is_in(["true", "false"]).all():
        return "Boolean"
    return "String"


def _typed(frame: Any, inferred: dict[str, str]) -> Any:
    """The sample with each convertible text column converted, for statistics."""
    import polars as pl

    steps = {
        "Int64": pl.Int64,
        "Float64": pl.Float64,
    }
    exprs = []
    for name, kind in inferred.items():
        col = pl.col(name).str.strip_chars()
        if kind in steps:
            exprs.append(col.cast(steps[kind], strict=False))
        elif kind == "Date":
            exprs.append(col.str.to_date("%Y-%m-%d", strict=False))
        elif kind == "Datetime":
            exprs.append(col.str.to_datetime(strict=False))
        elif kind == "Boolean":
            exprs.append(col.str.to_lowercase() == "true")
    return frame.with_columns(exprs) if exprs else frame
