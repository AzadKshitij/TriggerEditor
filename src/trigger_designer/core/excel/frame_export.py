"""``write_frame_xlsx``: one frame -> one sheet (File Output, Data Preview, Profile).

Streams in ``constant_memory`` mode from a spooled Parquet file, so memory is
bounded by the batch size whatever the table size. Excel's own limits are the
only caps; a larger table is refused (never truncated) with TD-OUT-013.
"""

from __future__ import annotations

import errno
import os
import shutil
import tempfile
from typing import Any

import polars as pl

from trigger_designer.core.excel import engine
from trigger_designer.core.excel.cells import (
    FormatBook,
    column_plan,
    column_values,
    safe_sheet_name,
    write_text,
    write_value,
)
from trigger_designer.core.excel.errors import (
    TD_BAD_WORKBOOK,
    TD_DISK_FULL,
    TD_FILE_LOCKED,
    TD_FOLDER_MISSING,
    TD_TOO_MANY_COLUMNS,
    TD_TOO_MANY_ROWS,
    ExcelWriteError,
)
from trigger_designer.core.excel.spool import frame_schema, spool_parquet


def check_target_folder(path: str) -> None:
    """TD-OUT-001 when the folder of ``path`` does not exist (no silent mkdir)."""
    folder = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(folder):
        raise ExcelWriteError(
            f"The folder '{folder}' does not exist. Create it or choose another folder.",
            code=TD_FOLDER_MISSING,
            path=path,
        )


def publish(tmp_file: str, final: str) -> None:
    """Move the finished workbook into place; a locked target is a plain TD-OUT-002."""
    try:
        os.replace(tmp_file, final)
    except PermissionError as exc:
        raise ExcelWriteError(
            f"The file '{os.path.basename(final)}' is open in Excel or another program. "
            "Close it and run again.",
            code=TD_FILE_LOCKED,
            path=final,
        ) from exc
    except OSError as exc:
        code = TD_DISK_FULL if exc.errno == errno.ENOSPC else TD_BAD_WORKBOOK
        raise ExcelWriteError(
            f"The workbook '{os.path.basename(final)}' could not be saved: {exc}",
            code=code,
            path=final,
        ) from exc


def write_frame_xlsx(
    frame: pl.LazyFrame | pl.DataFrame, path: str, *, sheet_name: str = "Sheet1"
) -> int:
    """Write ``frame`` to ``path`` as a one-sheet workbook; returns the data rows.

    Bold frozen header with filter buttons, formats from the dtypes, nulls as real
    blanks, strings never interpreted as formulas. Limits are Excel's own:
    1,048,575 data rows and 16,384 columns (beyond them ``ExcelWriteError``).
    """
    engine.require_xlsxwriter()
    path = os.fspath(path)
    schema = frame_schema(frame)
    if not schema:
        raise ExcelWriteError(
            "The table has no columns, so there is nothing to write.",
            code=TD_BAD_WORKBOOK,
        )
    if len(schema) > engine.MAX_COLS:
        raise ExcelWriteError(
            f"This table has {len(schema):,} columns; Excel allows at most "
            f"{engine.MAX_COLS:,}. Select fewer columns first.",
            code=TD_TOO_MANY_COLUMNS,
        )
    check_target_folder(path)
    tmp = tempfile.mkdtemp(prefix="td_xl_")
    try:
        spooled = spool_parquet(frame, tmp)
        total = spooled.height()
        if total + 1 > engine.MAX_ROWS:
            raise ExcelWriteError(
                f"This table has {total:,} rows; an Excel sheet holds at most "
                f"{engine.MAX_ROWS - 1:,} data rows. Save it as CSV or Parquet instead.",
                code=TD_TOO_MANY_ROWS,
            )
        tmp_file = os.path.join(tmp, "out.xlsx")
        try:
            _write_sheet(tmp_file, tmp, spooled, schema, total, sheet_name)
        except engine.library_errors() as exc:
            raise ExcelWriteError(
                f"Excel could not create the workbook: {exc}", code=TD_BAD_WORKBOOK
            ) from exc
        publish(tmp_file, path)
        return total
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _write_sheet(
    tmp_file: str, tmp: str, spooled: Any, schema: dict, total: int, sheet_name: str
) -> None:
    wb = engine.new_workbook(tmp_file, tmp)
    try:
        book = FormatBook(wb)
        ws = wb.add_worksheet(safe_sheet_name(sheet_name, default="Sheet1"))
        plans = column_plan(schema, reserved=())
        for c, plan in enumerate(plans):
            write_text(ws, 0, c, plan.header, book, "hdr")
        widths = [min(60, max(8, len(p.header) + 2)) for p in plans]
        row = 1
        for index, batch in enumerate(spooled.batches()):
            columns = [column_values(batch[p.name], p) for p in plans]
            for i in range(batch.height):
                for c, plan in enumerate(plans):
                    write_value(
                        ws, row, c, columns[c][i], plan.kind, book, plan.fmt_key
                    )
                row += 1
            if index == 0:
                for c, plan in enumerate(plans):
                    if plan.kind == "str":
                        longest = max((len(v) for v in columns[c] if v), default=0)
                        widths[c] = min(60, max(widths[c], longest + 2))
        for c, width in enumerate(widths):
            ws.set_column(c, c, width)
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, max(total, 1), len(plans) - 1)
    finally:
        wb.close()
