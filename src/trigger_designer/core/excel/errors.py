"""Errors raised by the Excel writer (Qt-free).

``code`` is a ``TD-OUT-nnn`` catalogue code; ``core/errors`` looks it up for the
plain-language title and hint, and ``str(exc)`` is already readable without it.
"""

from __future__ import annotations


class ExcelWriteError(Exception):
    """An Excel file could not be written; never a bare library traceback."""

    def __init__(
        self, message: str, *, code: str = "TD-OUT-014", path: str | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.path = path


TD_FOLDER_MISSING = "TD-OUT-001"
TD_FILE_LOCKED = "TD-OUT-002"
TD_NO_WRITER = "TD-OUT-003"
TD_DISK_FULL = "TD-OUT-005"
TD_EXISTS = "TD-OUT-010"
TD_TOO_MANY_COLUMNS = "TD-OUT-011"
TD_BAD_SETTINGS = "TD-OUT-012"
TD_TOO_MANY_ROWS = "TD-OUT-013"
TD_BAD_WORKBOOK = "TD-OUT-014"
