"""``write_workpaper``: the audit workpaper (.xlsx) writer (Qt-free).

Layout and rules: docs/plan/06-workpaper-export.md and docs/workpaper.md. The
exceptions plan runs exactly once (spooled to Parquet); the workbook is built in
``constant_memory`` mode in a temp folder and moved into place last, so a failure
or a locked target never leaves a half-written file.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from typing import Any

import polars as pl

from trigger_designer.core.excel import engine
from trigger_designer.core.excel.cells import FormatBook, column_plan, safe_sheet_name
from trigger_designer.core.excel.errors import (
    TD_BAD_WORKBOOK,
    TD_EXISTS,
    TD_FILE_LOCKED,
    TD_TOO_MANY_COLUMNS,
    ExcelWriteError,
)
from trigger_designer.core.excel.frame_export import check_target_folder, publish
from trigger_designer.core.excel.spool import spool_parquet
from trigger_designer.core.workpaper.paths import unique_path
from trigger_designer.core.workpaper.sanitize import (
    MAX_DATA_COLUMNS,
    MAX_LISTED,
    RESERVED_SHEETS,
)
from trigger_designer.core.workpaper.sheets_exceptions import write_exceptions_sheet
from trigger_designer.core.workpaper.sheets_runlog import (
    write_runlog_sheet,
    write_workflow_sheet,
)
from trigger_designer.core.workpaper.sheets_summary import (
    SummaryInputs,
    write_summary_sheet,
)
from trigger_designer.core.workpaper.spec import (
    IF_EXISTS_MODES,
    SourceFile,
    TestInfo,
    WorkpaperError,
    WorkpaperResult,
    WorkpaperSpec,
)
from trigger_designer.core.workpaper.stream import (
    compute_stats,
    population_stats,
    sha256_file,
    write_csv_sidecar,
)

NO_RECORD_REASON = "no run record is available (run recording is off or not installed)"
OFF_REASON = "turned off in the node settings"
NO_WORKFLOW_REASON = "no workflow information was supplied"


# ----------------------------------------------------------------- validation
def _validated(spec: WorkpaperSpec) -> tuple[WorkpaperSpec, date | None, list[str]]:
    notes: list[str] = []
    path = (spec.output_path or "").strip()
    if not path:
        raise WorkpaperError("Choose the file the workpaper is written to.")
    if not path.lower().endswith(".xlsx"):
        raise WorkpaperError(
            f"'{os.path.basename(path)}' must end in .xlsx.", path=path
        )
    publish = (spec.publish_path or "").strip()
    if publish and not publish.lower().endswith(".xlsx"):
        raise WorkpaperError(
            f"'{os.path.basename(publish)}' must end in .xlsx.", path=publish
        )
    if spec.if_exists not in IF_EXISTS_MODES:
        raise WorkpaperError(
            f"'If the file exists' must be one of {', '.join(IF_EXISTS_MODES)}."
        )
    prepared: date | None = None
    if spec.prepared_date.strip():
        try:
            prepared = date.fromisoformat(spec.prepared_date.strip())
        except ValueError as exc:
            raise WorkpaperError(
                f"The Prepared on date '{spec.prepared_date}' is not valid; use YYYY-MM-DD."
            ) from exc
    decimals = max(0, min(6, int(spec.value_decimals)))
    limit = max(1, int(spec.row_limit))
    if limit > MAX_LISTED:
        notes.append(
            f"The row limit {limit:,} is above what one Excel sheet holds; "
            f"it was lowered to {MAX_LISTED:,}."
        )
        limit = MAX_LISTED
    return (
        replace(
            spec,
            value_decimals=decimals,
            row_limit=limit,
            output_path=path,
            publish_path=publish,
        ),
        prepared,
        notes,
    )


def _choose_path(path: str, mode: str) -> str:
    """The final workbook path for ``if_exists`` mode ``mode``."""
    check_target_folder(path)
    name = os.path.basename(path)
    if mode == "version":
        return unique_path(path)
    if mode == "fail" and os.path.exists(path):
        raise WorkpaperError(
            f"A workpaper named '{name}' already exists. Choose another name or set "
            "'If the file exists' to New version.",
            code=TD_EXISTS,
            path=path,
        )
    lock = os.path.join(os.path.dirname(os.path.abspath(path)), "~$" + name)
    if mode == "replace" and os.path.exists(path) and os.path.exists(lock):
        raise WorkpaperError(
            f"The file '{name}' is open in Excel or another program. Close it and run again.",
            code=TD_FILE_LOCKED,
            path=path,
        )
    return path


def _sidecar_target(final: str, mode: str) -> str:
    stem = os.path.splitext(final)[0]
    target = f"{stem}_exceptions_full.csv"
    if os.path.exists(target):
        if mode == "fail":
            raise WorkpaperError(
                f"A file named '{os.path.basename(target)}' already exists.",
                code=TD_EXISTS,
                path=target,
            )
        if mode == "version":
            target = unique_path(target)
    return target


# -------------------------------------------------------------------- sources
def _iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rows_from_node(record: Mapping[str, Any], item: Mapping[str, Any]) -> int | None:
    """Rows a source file gave, from its input node's ``rows_out`` (in-flight records
    get ``inputs[].row_count`` only when the run ends). Only when the node read
    exactly one file, so the count is not shared between files."""
    node_id = item.get("node_id")
    if node_id is None:
        return None
    siblings = [
        i
        for i in record.get("inputs") or []
        if isinstance(i, Mapping) and i.get("node_id") == node_id
    ]
    if len(siblings) != 1:
        return None
    for node in record.get("nodes") or []:
        if isinstance(node, Mapping) and node.get("node_id") == node_id:
            counts = [
                v
                for v in (node.get("rows_out") or {}).values()
                if isinstance(v, int) and not isinstance(v, bool)
            ]
            return counts[0] if len(counts) == 1 else None
    return None


def gather_sources(
    spec: WorkpaperSpec, run_record: Mapping[str, Any] | None
) -> list[SourceFile]:
    """Source files: run-record inputs first (run-time hashes), then the configured ones.

    Missing size / time / hash are filled from the file system; a file that is gone
    keeps its row (the hash cell then says so).
    """
    found: dict[str, SourceFile] = {}
    sheets_seen: list[SourceFile] = []
    record = run_record or {}
    for item in record.get("inputs") or []:
        if isinstance(item, Mapping) and item.get("path"):
            src = SourceFile.from_mapping(item)
            if src.rows is None:
                src = replace(src, rows=_rows_from_node(record, item))
            sheets_seen.append(src)
    sheets_seen.extend(spec.source_files)
    for src in sheets_seen:
        key = os.path.normcase(os.path.normpath(src.path)) + "|" + str(src.sheet or "")
        old = found.get(key)
        if old is None or (old.sha256 is None and src.sha256):
            found[key] = src
    out = []
    for src in found.values():
        size, mtime, digest = src.size_bytes, src.modified_time, src.sha256
        try:
            stat = os.stat(src.path)
            size = size if size is not None else stat.st_size
            mtime = mtime or _iso_utc(stat.st_mtime)
        except OSError:
            pass
        if digest is None:
            digest = sha256_file(src.path)
        out.append(replace(src, size_bytes=size, modified_time=mtime, sha256=digest))
    return out


# ---------------------------------------------------------------- the layouts
@dataclass
class _Names:
    summary: str = "Summary"
    exceptions: str | None = None
    runlog: str | None = None
    workflow: str | None = None
    omitted: dict[str, str] = field(default_factory=dict)

    def ordered(self) -> list[str]:
        return [
            n for n in (self.summary, self.exceptions, self.runlog, self.workflow) if n
        ]

    def contents(self) -> list[str]:
        lines = ["Summary"]
        if self.exceptions:
            lines.append(self.exceptions)
        lines.append(
            self.runlog or f"Run log - omitted: {self.omitted.get('Run log', '')}"
        )
        lines.append(
            self.workflow or f"Workflow - omitted: {self.omitted.get('Workflow', '')}"
        )
        return lines


def _sheet_names(
    spec: WorkpaperSpec,
    run_record: Mapping[str, Any] | None,
    workflow: Sequence[Mapping[str, Any]] | None,
    *,
    with_exceptions: bool,
) -> _Names:
    names = _Names()
    used = list(RESERVED_SHEETS)
    if with_exceptions:
        names.exceptions = safe_sheet_name(
            spec.exceptions_sheet_name, used, "Exceptions"
        )
    if not spec.include_run_record:
        names.omitted["Run log"] = OFF_REASON
    elif not run_record:
        names.omitted["Run log"] = NO_RECORD_REASON
    else:
        names.runlog = "Run log"
    if not spec.include_workflow:
        names.omitted["Workflow"] = OFF_REASON
    elif not workflow:
        names.omitted["Workflow"] = NO_WORKFLOW_REASON
    else:
        names.workflow = "Workflow"
    return names


def _properties(spec: WorkpaperSpec, now: datetime) -> dict[str, Any]:
    version = f" {spec.app_version}" if spec.app_version else ""
    return {
        "title": spec.title,
        "author": spec.preparer,
        "company": spec.client,
        "comments": f"Generated by Trigger Designer{version}",
        "created": now,
    }


def _finish(wb: Any, tmp_xlsx: str, final: str) -> str:
    try:
        wb.close()
    except engine.library_errors() as exc:
        raise ExcelWriteError(
            f"Excel could not create the workbook: {exc}", code=TD_BAD_WORKBOOK
        ) from exc
    publish(tmp_xlsx, final)
    return sha256_file(final) or ""


def write_workpaper(
    spec: WorkpaperSpec,
    exceptions: pl.LazyFrame | pl.DataFrame,
    *,
    population: pl.LazyFrame | pl.DataFrame | None = None,
    test: TestInfo | Mapping[str, Any] | None = None,
    run_record: Mapping[str, Any] | None = None,
    workflow: Sequence[Mapping[str, Any]] | None = None,
    now: datetime | None = None,
) -> WorkpaperResult:
    """Write the workpaper for one test: Summary, Exceptions, Run log, Workflow."""
    started = time.perf_counter()
    now = now or datetime.now()
    spec, prepared, notes = _validated(spec)
    engine.require_xlsxwriter()
    if not isinstance(test, TestInfo):
        test = TestInfo.from_mapping(test)
    final = _choose_path(spec.output_path, spec.if_exists)
    tmp = tempfile.mkdtemp(prefix="td_wp_")
    try:
        spooled = spool_parquet(exceptions, tmp)
        if not spooled.schema:
            raise WorkpaperError(
                "The Exceptions input has no columns, so there is nothing to list."
            )
        if len(spooled.schema) > MAX_DATA_COLUMNS:
            raise WorkpaperError(
                f"The Exceptions input has {len(spooled.schema):,} columns; a workpaper holds "
                f"at most {MAX_DATA_COLUMNS:,}. Select fewer columns first.",
                code=TD_TOO_MANY_COLUMNS,
            )
        plans = column_plan(spooled.schema, spec.amount_column)
        stats = compute_stats(spooled, plans, spec.amount_column)
        pop_rows = pop_value = None
        if population is not None:
            pop_rows, pop_value, pop_note = population_stats(
                population, spec.amount_column
            )
            if pop_note:
                notes.append(pop_note)
        limit = spec.row_limit
        truncated = stats.total > limit
        too_long = any(n > 32_767 for n in stats.max_len.values())
        csv_name = csv_rows = csv_sha = None
        csv_final: str | None = None
        csv_tmp: str | None = None
        if truncated or too_long:
            csv_final = _sidecar_target(spec.publish_path or final, spec.if_exists)
            csv_tmp = os.path.join(tmp, "full.csv")
            csv_rows = write_csv_sidecar(spooled, plans, csv_tmp)
            csv_sha = sha256_file(csv_tmp)
            csv_name = os.path.basename(csv_final)
        names = _sheet_names(spec, run_record, workflow, with_exceptions=True)

        tmp_xlsx = os.path.join(tmp, "workpaper.xlsx")
        wb = engine.new_workbook(tmp_xlsx, tmp)
        try:
            book = FormatBook(wb)
            sheets = {n: wb.add_worksheet(n) for n in names.ordered()}
            wb.set_properties(_properties(spec, now))
            layout = write_exceptions_sheet(
                wb,
                sheets[names.exceptions],
                book,
                spec,
                stats,
                spooled,
                plans,
                limit=limit,
                csv_name=csv_name,
            )
            sources = gather_sources(spec, run_record)
            info = SummaryInputs(
                spec=spec,
                now=now,
                test=test,
                exceptions_sheet=names.exceptions,
                exceptions_total=stats.total,
                exceptions_value=stats.amount_sum,
                listed=layout.written,
                listed_value=layout.value_listed,
                last_row=layout.last_row,
                amount_col_letter=layout.amount_col_letter,
                truncated=truncated,
                limit=limit,
                pop_rows=pop_rows,
                pop_value=pop_value,
                csv_text=(
                    f"{csv_name} - {csv_rows:,} rows - SHA-256 {csv_sha}"
                    if csv_name
                    else "Not needed - all exceptions are listed in this workbook"
                ),
                decimals=spec.value_decimals,
                sources=sources,
                notes=[*notes, *layout.notes],
                contents=names.contents(),
                prepared_on=prepared,
            )
            if truncated:
                info.notes.append(
                    f"Only the first {limit:,} of {stats.total:,} exceptions are listed in the "
                    f"Exceptions sheet; the complete list is in {csv_name}."
                )
            for sheet, reason in names.omitted.items():
                info.notes.append(f"The {sheet} sheet was omitted: {reason}.")
            warnings = write_summary_sheet(wb, sheets["Summary"], book, info)
            if names.runlog:
                write_runlog_sheet(
                    sheets[names.runlog],
                    book,
                    run_record or {},
                    in_progress_step=True,
                )
            if names.workflow:
                write_workflow_sheet(sheets[names.workflow], book, workflow or [])
            sha = _finish(wb, tmp_xlsx, final)
        except BaseException:
            _abort(wb)
            raise
        if csv_tmp and csv_final:
            publish(csv_tmp, csv_final)
        all_notes = [*info.notes]
        return WorkpaperResult(
            path=final,
            csv_path=csv_final,
            exceptions_total=stats.total,
            exceptions_written=layout.written,
            truncated=truncated,
            population_rows=pop_rows,
            population_value=pop_value,
            exceptions_value=stats.amount_sum,
            workbook_sha256=sha,
            sheets=names.ordered(),
            omitted=dict(names.omitted),
            warnings=[*all_notes, *warnings],
            duration_s=time.perf_counter() - started,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _abort(wb: Any) -> None:
    """Release a half-built workbook's streaming temp files (Windows cannot delete open files)."""
    try:
        wb.fileclosed = True  # nothing is published
        for sheet in wb.worksheets():
            handle = getattr(sheet, "fh", None)
            if handle is not None:
                handle.close()
    except Exception:  # noqa: BLE001, S110 - best effort, the original error is re-raised
        pass


def tests_from_record(run_record: Mapping[str, Any] | None) -> list[TestInfo]:
    """The audit-test summaries stored in a run record, in run order."""
    found = []
    for node in (run_record or {}).get("nodes") or []:
        info = (
            TestInfo.from_mapping(node.get("test_summary"))
            if node.get("test_summary")
            else None
        )
        if info is not None:
            found.append(info)
    return found


def write_run_workpaper(
    spec: WorkpaperSpec,
    *,
    run_record: Mapping[str, Any],
    workflow: Sequence[Mapping[str, Any]] | None = None,
    now: datetime | None = None,
) -> WorkpaperResult:
    """Workpaper for a whole run: Summary (one row per audit test), Run log, Workflow."""
    started = time.perf_counter()
    now = now or datetime.now()
    spec, prepared, notes = _validated(spec)
    engine.require_xlsxwriter()
    final = _choose_path(spec.output_path, spec.if_exists)
    tmp = tempfile.mkdtemp(prefix="td_wp_")
    try:
        names = _sheet_names(spec, run_record, workflow, with_exceptions=False)
        tests = tests_from_record(run_record)
        tmp_xlsx = os.path.join(tmp, "workpaper.xlsx")
        wb = engine.new_workbook(tmp_xlsx, tmp)
        try:
            book = FormatBook(wb)
            sheets = {n: wb.add_worksheet(n) for n in names.ordered()}
            wb.set_properties(_properties(spec, now))
            info = SummaryInputs(
                spec=spec,
                now=now,
                mode="run",
                tests=tests,
                sources=gather_sources(spec, run_record),
                notes=notes,
                contents=names.contents(),
                prepared_on=prepared,
            )
            for sheet, reason in names.omitted.items():
                info.notes.append(f"The {sheet} sheet was omitted: {reason}.")
            warnings = write_summary_sheet(wb, sheets["Summary"], book, info)
            if names.runlog:
                write_runlog_sheet(sheets[names.runlog], book, run_record)
            if names.workflow:
                write_workflow_sheet(sheets[names.workflow], book, workflow or [])
            sha = _finish(wb, tmp_xlsx, final)
        except BaseException:
            _abort(wb)
            raise
        return WorkpaperResult(
            path=final,
            csv_path=None,
            exceptions_total=sum(t.exception_rows or 0 for t in tests),
            exceptions_written=0,
            truncated=False,
            population_rows=None,
            population_value=None,
            exceptions_value=None,
            workbook_sha256=sha,
            sheets=names.ordered(),
            omitted=dict(names.omitted),
            warnings=[*info.notes, *warnings],
            duration_s=time.perf_counter() - started,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
