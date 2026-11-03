"""Excel writing (Qt-free). Only ``engine.py`` imports the Excel library.

``write_frame_xlsx`` is the shared one-sheet export used by File Output, the Data
Preview and the Data Profile; the workpaper writer lives in ``core/workpaper``.
"""

from __future__ import annotations

from trigger_designer.core.excel.errors import ExcelWriteError
from trigger_designer.core.excel.frame_export import write_frame_xlsx

__all__ = ["ExcelWriteError", "write_frame_xlsx"]
