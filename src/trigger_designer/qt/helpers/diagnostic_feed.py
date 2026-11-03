"""One ordered feed of diagnostic records: log lines and node problems.

The feed is owned by the design window (``window.diagnostics``) and is the only
thing the Logs dock paints. ``NodeErrorState.by_source`` stays the badge
authority: a problem record is a copy of what the badge shows, so the panel can
never disagree with the canvas about which nodes are red.

Records are immutable. An upsert keeps the slot (``seq``) and the first sighting
and rewrites only the payload, so a row does not jump when a node re-reports the
same failure. Only a new fingerprint appends.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from qtpy.QtCore import QObject, Signal

from trigger_designer.core.errors import NodeError

#: A plain log line.
KIND_LOG = "log"
#: A node problem, carrying the whole :class:`NodeError`.
KIND_PROBLEM = "problem"

#: The last run reported it.
ORIGIN_RUN = "run"
#: The current workflow configuration reported it.
ORIGIN_LIVE = "live"

#: Filter-strip categories. Derived, never stored on the record.
CATEGORY_ALL = "all"
CATEGORY_ERRORS = "errors"
CATEGORY_CONV = "conv"
CATEGORY_WARNINGS = "warnings"
CATEGORY_MESSAGES = "messages"

#: The type-conversion family. The strip shows it as its own bucket because a
#: conversion failure is a data problem, not a broken workflow.
_CONVERSION_PREFIX = "TD-TYP-"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class DiagnosticRecord:
    """One row: either a log line or a node problem."""

    seq: int
    kind: str
    first_seen: datetime
    level: str = ""
    message: str = ""
    error: NodeError | None = None
    source: str = ""

    @property
    def category(self) -> str:
        if self.kind == KIND_LOG:
            return CATEGORY_MESSAGES
        error = self.error
        if error is None:
            return CATEGORY_ERRORS
        if error.code.startswith(_CONVERSION_PREFIX):
            return CATEGORY_CONV
        if error.severity == "warning":
            return CATEGORY_WARNINGS
        return CATEGORY_ERRORS

    @property
    def severity(self) -> str:
        """What the delegate paints the glyph with."""
        if self.kind == KIND_PROBLEM and self.error is not None:
            return self.error.severity
        return self.level.lower()

    @property
    def node_label(self) -> str:
        if self.error is None:
            return ""
        return self.error.node_label or self.error.node_title or ""

    @property
    def searchable(self) -> str:
        """Everything the text filter matches against, casefolded by callers."""
        if self.kind == KIND_LOG:
            return f"{self.level} {self.message}"
        error = self.error
        if error is None:
            return ""
        return " ".join(
            part
            for part in (
                error.code,
                error.title,
                error.detail,
                error.hint,
                error.node_label,
            )
            if part
        )


class DiagnosticFeed(QObject):
    """Every log line and problem of one workflow document, in one order."""

    changed = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        max_log_records: int = 1000,
    ) -> None:
        super().__init__(parent)
        self.max_log_records = max_log_records
        self._seq = 0
        self._logs: list[DiagnosticRecord] = []
        self._problems: dict[tuple[int | None, str, str], DiagnosticRecord] = {}

    # -- writes -----------------------------------------------------------
    def _notify(self) -> None:
        """Tell the dock the projection changed; a closed window is not an error."""
        try:
            self.changed.emit()
        except RuntimeError:
            # The C++ object can be gone while a scene still holds the wrapper.
            pass

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    @staticmethod
    def _key(error: NodeError, source: str) -> tuple[int | None, str, str]:
        # ``node_id is None`` covers every system error, so the fingerprint is
        # the discriminator that keeps two of them from overwriting each other.
        # The fingerprint is code+node+columns+exception, which is identical for
        # two system errors of the same code, so the title separates them too.
        discriminator = (
            "" if error.node_id is not None else f"{error.fingerprint}:{error.title}"
        )
        return (error.node_id, source, discriminator)

    def upsert(self, error: NodeError, source: str = "live") -> bool:
        """Record a node problem; ``False`` when it changed nothing."""
        key = self._key(error, source)
        old = self._problems.get(key)
        if old is not None:
            if old.error == error:
                return False
            self._problems[key] = replace(old, error=error)
            self._notify()
            return True
        self._problems[key] = DiagnosticRecord(
            seq=self._next_seq(),
            kind=KIND_PROBLEM,
            first_seen=_utc_now(),
            error=error,
            source=source,
        )
        self._notify()
        return True

    def add_log(self, level: str, message: str) -> DiagnosticRecord:
        """Append a log line and trim the oldest ones past the cap."""
        record = DiagnosticRecord(
            seq=self._next_seq(),
            kind=KIND_LOG,
            first_seen=_utc_now(),
            level=level.upper(),
            message=message,
        )
        self._logs.append(record)
        overflow = len(self._logs) - self.max_log_records
        if overflow > 0:
            del self._logs[:overflow]
        self._notify()
        return record

    def remove(self, node_id: int, source: str | None = None) -> None:
        keys = [
            key
            for key in self._problems
            if key[0] == node_id and (source is None or key[1] == source)
        ]
        if not keys:
            return
        for key in keys:
            del self._problems[key]
        self._notify()

    def clear_source(self, source: str) -> None:
        keys = [key for key in self._problems if key[1] == source]
        if not keys:
            return
        for key in keys:
            del self._problems[key]
        self._notify()

    def clear(self) -> None:
        """Drop every problem record. Log lines are untouched."""
        if not self._problems:
            return
        self._problems.clear()
        self._notify()

    def clear_logs(self) -> None:
        """Drop every log line. Live problems are untouched."""
        if not self._logs:
            return
        self._logs.clear()
        self._notify()

    # -- reads ------------------------------------------------------------
    def _visible_problem_records(self) -> list[DiagnosticRecord]:
        """One record per node: a run error outranks a live one."""
        run = [
            record for record in self._problems.values() if record.source == ORIGIN_RUN
        ]
        run_ids = {
            record.error.node_id
            for record in run
            if record.error is not None and record.error.node_id is not None
        }
        live = [
            record
            for record in self._problems.values()
            if record.source != ORIGIN_RUN
            and (record.error is None or record.error.node_id not in run_ids)
        ]
        return run + live

    def records(self) -> list[DiagnosticRecord]:
        """Every visible record, oldest first, both kinds interleaved by ``seq``."""
        return sorted(
            [*self._logs, *self._visible_problem_records()],
            key=lambda record: record.seq,
        )

    def entries(self) -> list[tuple[str, NodeError]]:
        """Problem records as ``(source, error)``, run entries first."""
        return [
            (record.source, record.error)
            for record in self._visible_problem_records()
            if record.error is not None
        ]

    def count(self, severity: str | None = None, *, roots_only: bool = False) -> int:
        return sum(
            1
            for _source, error in self.entries()
            if (severity is None or error.severity == severity)
            and (not roots_only or not error.knock_on)
        )

    def counts(self) -> dict[str, int]:
        """Per-category totals for the filter strip, computed over one pass."""
        counts = {
            CATEGORY_ALL: 0,
            CATEGORY_ERRORS: 0,
            CATEGORY_CONV: 0,
            CATEGORY_WARNINGS: 0,
            CATEGORY_MESSAGES: 0,
        }
        for record in self.records():
            counts[CATEGORY_ALL] += 1
            counts[record.category] += 1
        return counts

    def __len__(self) -> int:
        return len(self.records())
