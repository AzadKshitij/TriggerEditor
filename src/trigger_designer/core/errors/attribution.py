"""Find the upstream step whose plan or data produced a failure."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

SCHEMA_CODES = {
    "TD-SCH-001",
    "TD-SCH-002",
    "TD-SCH-004",
    "TD-SCH-005",
    "TD-TYP-002",
    "TD-TYP-006",
    "TD-IN-001",
    "TD-IN-002",
    "TD-IN-003",
    "TD-IN-005",
    "TD-IN-006",
    "TD-SYS-100",
}
DATA_CODES = {
    "TD-TYP-001",
    "TD-TYP-003",
    "TD-TYP-004",
    "TD-TYP-005",
    "TD-IN-004",
    "TD-IN-007",
    "TD-SYS-100",
}


@dataclass(frozen=True)
class Ancestor:
    node_id: int
    frame: Any | None


def attribute_upstream(
    error_code: str,
    exc_type: str,
    ancestors: Sequence[Ancestor],
    *,
    row_cap: int = 100_000,
    budget_s: float = 3.0,
) -> int | None:
    """Return the id of the first ancestor that reproduces the failure."""
    started = time.monotonic()
    usable = [item for item in ancestors if item.frame is not None]
    if error_code in SCHEMA_CODES:
        for ancestor in usable:
            try:
                ancestor.frame.lazy().collect_schema()
            except Exception:  # noqa: BLE001 - this ancestor's plan is broken
                return ancestor.node_id
    if error_code not in DATA_CODES:
        return None
    for ancestor in usable:
        if time.monotonic() - started > budget_s:
            return None
        try:
            ancestor.frame.lazy().head(row_cap).collect(engine="streaming")
        except Exception as exc:  # noqa: BLE001 - match only the same failure
            if not exc_type or type(exc).__name__ == exc_type:
                return ancestor.node_id
    return None
