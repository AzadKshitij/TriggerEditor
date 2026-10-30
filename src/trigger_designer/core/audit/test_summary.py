"""``TestSummary``: the record of one audit test, read by other features.

Built from the one-row Summary frame (``common.summary_frame``). The first block
of fields is the frozen contract of docs/plan/00-codebase-brief.md section 11.3;
later fields only ever get added, always with a default.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar

import polars as pl

from trigger_designer.core.audit.common import BASE_SUMMARY


@dataclass(frozen=True)
class TestSummary:
    __test__: ClassVar[bool] = False  # keep pytest from collecting this class

    # --- brief 11.3 fields (names and meaning frozen) ---
    test_id: str = ""  # "<op>#<node_id>", e.g. "audit.duplicates#139626"
    test_name: str = ""
    node_id: int | None = None
    status: str = "pass"  # "pass" | "warn" | "fail" | "error"
    population_rows: int | None = None
    exception_rows: int | None = None
    exception_rate: float | None = None
    criteria: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    exceptions_var: str | None = None  # generated-code variable with the exceptions
    # --- additions (defaulted; non-breaking) ---
    population_value: float | None = None
    exception_value: float | None = None
    code: str | None = None  # TD-AUDIT-101/102/103 when a warning applies
    details: dict[str, Any] = field(default_factory=dict)  # node extras

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestSummary:
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def from_summary_frame(
        cls,
        frame: pl.DataFrame,
        *,
        op: str,
        node_id: int | None,
        exceptions_var: str | None = None,
    ) -> TestSummary:
        row = frame.row(0, named=True)
        base = set(BASE_SUMMARY)
        return cls(
            test_id=f"{op}#{node_id}",
            test_name=row["test_name"],
            node_id=node_id,
            status=row["status"],
            population_rows=row["population_rows"],
            exception_rows=row["exception_rows"],
            exception_rate=row["exception_rate"],
            criteria=row["criteria"],
            parameters=json.loads(row["parameters"] or "{}"),
            message=row["message"],
            exceptions_var=exceptions_var,
            population_value=row["population_value"],
            exception_value=row["exception_value"],
            code=row["code"],
            details={k: v for k, v in row.items() if k not in base},
        )
