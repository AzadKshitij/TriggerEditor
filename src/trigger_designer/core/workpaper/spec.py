"""Workpaper data model: spec, test info, result (Qt-free, JSON round-trippable)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields
from typing import Any, ClassVar

from trigger_designer.core.excel.errors import TD_BAD_SETTINGS, ExcelWriteError

DEFAULT_TICKS = (
    ("✓", "Agreed to source document"),
    ("X", "Exception confirmed"),
    ("E", "Explained - see comment"),
    ("F", "Follow-up required"),
    ("N/A", "Not applicable"),
)
CONCLUSIONS = (
    "No exceptions",
    "Exceptions - explained",
    "Exceptions - require follow-up",
)
IF_EXISTS_MODES = ("version", "replace", "fail")
NOT_PROVIDED = "Not provided - complete manually"


class WorkpaperError(ExcelWriteError):
    """A workpaper could not be written; ``str(e)`` is plain language."""

    def __init__(
        self, message: str, *, code: str = TD_BAD_SETTINGS, path: str | None = None
    ) -> None:
        super().__init__(message, code=code, path=path)


@dataclass(frozen=True)
class SourceFile:
    path: str
    sheet: str | None = None
    rows: int | None = None
    size_bytes: int | None = None
    modified_time: str | None = None
    sha256: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> SourceFile:
        rows = data.get("rows", data.get("row_count"))
        return cls(
            path=str(data.get("path") or ""),
            sheet=data.get("sheet"),
            rows=rows if isinstance(rows, int) else None,
            size_bytes=data.get("size_bytes"),
            modified_time=data.get("modified_time"),
            sha256=data.get("sha256"),
        )


@dataclass(frozen=True)
class WorkpaperSpec:
    title: str = "Audit workpaper"
    preparer: str = ""
    reviewer: str = ""
    purpose: str = ""
    sections: tuple[str, ...] = ()  # reserved, ignored
    include_run_record: bool = True
    include_tests: bool = True  # reserved, ignored
    include_profile: bool = False  # reserved, ignored
    output_path: str = ""
    format: str = "xlsx"
    workpaper_ref: str = ""
    client: str = ""
    engagement: str = ""
    period: str = ""
    prepared_date: str = ""
    test_name: str = ""
    procedure: str = ""
    criteria: str = ""
    amount_column: str = ""
    value_decimals: int = 2
    row_limit: int = 100_000
    include_workflow: bool = True
    if_exists: str = "version"
    exceptions_sheet_name: str = "Exceptions"
    logo_path: str = ""
    tick_marks: tuple[tuple[str, str], ...] = DEFAULT_TICKS
    source_files: tuple[SourceFile, ...] = ()
    app_version: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> WorkpaperSpec:
        data = json.loads(text)
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        if "sections" in kwargs:
            kwargs["sections"] = tuple(kwargs["sections"])
        if "tick_marks" in kwargs:
            kwargs["tick_marks"] = tuple(
                (str(a), str(b)) for a, b in kwargs["tick_marks"]
            )
        if "source_files" in kwargs:
            kwargs["source_files"] = tuple(
                SourceFile.from_mapping(x)
                if isinstance(x, Mapping)
                else SourceFile(str(x))
                for x in kwargs["source_files"]
            )
        return cls(**kwargs)


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


@dataclass(frozen=True)
class TestInfo:
    """What one audit test reported (the one-row Summary frame of plan 04)."""

    __test__: ClassVar[bool] = False  # not a pytest class

    test_name: str = ""
    criteria: str = ""
    status: str = ""
    message: str = ""
    population_rows: int | None = None
    exception_rows: int | None = None
    exception_rate: float | None = None
    population_value: float | None = None
    exception_value: float | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> TestInfo | None:
        if not isinstance(data, Mapping):
            return None
        params = data.get("parameters") or {}
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except ValueError:
                params = {"parameters": params}
        if not isinstance(params, Mapping):
            params = {}
        return cls(
            test_name=str(data.get("test_name") or ""),
            criteria=str(data.get("criteria") or ""),
            status=str(data.get("status") or ""),
            message=str(data.get("message") or ""),
            population_rows=_int(data.get("population_rows")),
            exception_rows=_int(data.get("exception_rows")),
            exception_rate=_float(data.get("exception_rate")),
            population_value=_float(data.get("population_value")),
            exception_value=_float(data.get("exception_value")),
            parameters=dict(params),
        )

    @classmethod
    def from_frame(cls, df: Any) -> TestInfo | None:
        """First row of a Summary frame (unknown columns ignored); empty -> None."""
        if df is None or getattr(df, "height", 0) == 0:
            return None
        return cls.from_mapping(df.row(0, named=True))


@dataclass
class WorkpaperResult:
    path: str
    csv_path: str | None
    exceptions_total: int
    exceptions_written: int
    truncated: bool
    population_rows: int | None
    population_value: float | None
    exceptions_value: float | None
    workbook_sha256: str
    sheets: list[str]
    omitted: dict[str, str]
    warnings: list[str]
    duration_s: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
