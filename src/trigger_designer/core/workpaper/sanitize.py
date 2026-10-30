"""Sheet names, headers, column plan and the formula-injection predicates.

The rules themselves live in ``core/excel/cells.py`` (shared with the one-sheet
export); this module is the workpaper-facing name for them plus the workpaper
limits.
"""

from __future__ import annotations

from trigger_designer.core.excel.cells import (
    ID_NAME,
    MAX_CELL_CHARS,
    RESERVED_HEADERS,
    ColumnPlan,
    column_plan,
    danger_expr,
    guard_text,
    needs_quote_prefix,
    quote_sheet,
    safe_sheet_name,
    unique_headers,
)

EXCEL_MAX_ROWS = 1_048_576
HEADER_ROWS = 2  # banner + header
MAX_LISTED = EXCEL_MAX_ROWS - HEADER_ROWS  # 1_048_574
MAX_DATA_COLUMNS = 16_384 - 3
RESERVED_SHEETS = ("summary", "run log", "workflow", "tests")

__all__ = [
    "EXCEL_MAX_ROWS",
    "HEADER_ROWS",
    "ID_NAME",
    "MAX_CELL_CHARS",
    "MAX_DATA_COLUMNS",
    "MAX_LISTED",
    "RESERVED_HEADERS",
    "RESERVED_SHEETS",
    "ColumnPlan",
    "column_plan",
    "danger_expr",
    "guard_text",
    "needs_quote_prefix",
    "quote_sheet",
    "safe_sheet_name",
    "unique_headers",
]
