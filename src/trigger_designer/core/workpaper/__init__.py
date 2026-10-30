"""Audit workpaper export (Qt-free): ``write_workpaper`` and friends.

Importing this package is cheap; the writer pulls in polars and the Excel
library only when it is called.
"""

from __future__ import annotations

from trigger_designer.core.workpaper.spec import (
    SourceFile,
    TestInfo,
    WorkpaperError,
    WorkpaperResult,
    WorkpaperSpec,
)

__all__ = [
    "SourceFile",
    "TestInfo",
    "WorkpaperError",
    "WorkpaperResult",
    "WorkpaperSpec",
    "write_run_workpaper",
    "write_workpaper",
]


def write_workpaper(*args, **kwargs):
    from trigger_designer.core.workpaper.writer import write_workpaper as _fn

    return _fn(*args, **kwargs)


def write_run_workpaper(*args, **kwargs):
    from trigger_designer.core.workpaper.writer import write_run_workpaper as _fn

    return _fn(*args, **kwargs)
