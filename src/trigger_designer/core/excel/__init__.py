"""Excel writing (Qt-free): the one module that talks to the Excel library.

Polars' ``write_excel`` is a thin layer over XlsxWriter, so a missing
``xlsxwriter`` is the only way this fails for a reason other than the file
itself (a path that cannot be written, a workbook already open in Excel).
"""

from __future__ import annotations

import polars as pl


def write_frame_xlsx(
    frame: pl.DataFrame, path: str, *, sheet_name: str = "Sheet1"
) -> None:
    """Write ``frame`` to ``path`` as a single-sheet workbook.

    The data is written as an Excel table (so every column has filter buttons),
    with a bold header row frozen in place, column widths fitted to the content
    and nulls left blank. Raises on failure.
    """
    frame.write_excel(
        workbook=path,
        worksheet=sheet_name,
        autofit=True,
        freeze_panes=(1, 0),
        header_format={"bold": True},
    )
