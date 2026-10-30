"""The xlsxwriter facade: the ONLY module in the application that imports it.

Everything else receives workbook / worksheet objects from here. ``xlsxwriter``
is imported lazily so a missing package becomes a plain ``ExcelWriteError``
(TD-OUT-003) instead of an ``ImportError`` at start-up.
"""

from __future__ import annotations

import importlib
from typing import Any

from trigger_designer.core.excel.errors import TD_NO_WRITER, ExcelWriteError

MAX_ROWS = 1_048_576
MAX_COLS = 16_384

_MISSING = "Excel export needs the 'xlsxwriter' package, which is missing from this installation."


def require_xlsxwriter() -> Any:
    """Import and return ``xlsxwriter``; raise ``ExcelWriteError`` if it is absent."""
    try:
        return importlib.import_module("xlsxwriter")
    except ImportError as exc:
        raise ExcelWriteError(_MISSING, code=TD_NO_WRITER) from exc


def library_errors() -> tuple[type[BaseException], ...]:
    """Exception types the library raises for bad names / cell content."""
    xw = require_xlsxwriter()
    return (xw.exceptions.XlsxWriterException,)


def col_name(idx0: int) -> str:
    from xlsxwriter.utility import xl_col_to_name

    return xl_col_to_name(idx0)


def cell_ref(row0: int, col0: int, abs_: bool = False) -> str:
    from xlsxwriter.utility import xl_rowcol_to_cell

    return xl_rowcol_to_cell(row0, col0, row_abs=abs_, col_abs=abs_)


def new_workbook(path: str, tmp_dir: str) -> Any:
    """A streaming (``constant_memory``) workbook with safe cell-type options.

    Strings never turn into numbers, formulas or URLs; NaN/Inf are handled by
    ``cells.write_value`` (the library raises on them).
    """
    xw = require_xlsxwriter()
    return xw.Workbook(
        path,
        {
            "constant_memory": True,
            "tmpdir": tmp_dir,
            "strings_to_numbers": False,
            "strings_to_formulas": False,
            "strings_to_urls": False,
            "nan_inf_to_errors": False,
            "remove_timezone": True,
            "default_format_properties": {"font_name": "Calibri", "font_size": 10},
        },
    )
