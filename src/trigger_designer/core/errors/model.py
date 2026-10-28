"""Structured, user-facing error data shared by every layer.

No Qt, no widgets: a NodeError is plain data so plans 02/03/08 can persist,
render and test it without a GUI.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

KNOCK_ON_CODES = frozenset({"TD-RUN-003", "TD-RUN-005", "TD-RUN-008"})

_WS = re.compile(r"\s+")


def shorten(text: str, limit: int = 160) -> str:
    """Collapse whitespace and truncate with an ellipsis."""
    value = _WS.sub(" ", str(text or "")).strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def normalise_path(path: str | None) -> str:
    if not path:
        return ""
    return os.path.normcase(os.path.normpath(str(path).replace("/", os.sep)))


def _first_sentence(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    match = re.split(r"(?<=[.!?])\s+", value, maxsplit=1)
    return match[0].strip()


@dataclass(frozen=True)
class SuggestedFix:
    text: str
    kind: str = "manual"
    params: dict[str, str] = field(default_factory=dict, compare=False)


@dataclass
class ErrorContext:
    """What the translator may know about the failing node; all optional."""

    node_id: int | None = None
    node_title: str | None = None
    node_label: str = ""
    op: str | None = None
    phase: str = "run"
    input_columns: tuple[str, ...] = ()
    input_dtypes: dict[str, str] = field(default_factory=dict)
    referenced_columns: tuple[str, ...] = ()
    input_paths: dict[str, int] = field(default_factory=dict)
    output_paths: dict[str, int] = field(default_factory=dict)
    node_labels: dict[int, str] = field(default_factory=dict)
    variable_owners: dict[str, int] = field(default_factory=dict)
    date_format: str | None = None

    @classmethod
    def from_node(cls, node, phase: str = "run") -> ErrorContext:
        """Best-effort context from a duck-typed node; never raises."""
        if node is None:
            return cls(phase=phase)
        try:
            title = getattr(type(node), "node_title", None) or getattr(
                node, "node_title", None
            )
            label = getattr(node, "label_text", "") or ""
            label = str(label).strip()
            node_label = f"{title} '{label}'" if title and label else (title or "")
            node_type = getattr(node, "node_type", None)
            node_code = getattr(node, "node_code", None)
            op = None
            if node_type is not None and node_code is not None:
                op = f"{node_type.value}.{node_code.name.lower()}"
            return cls(
                node_id=getattr(node, "id", None),
                node_title=title,
                node_label=node_label,
                op=op,
                phase=phase,
            )
        except Exception:  # noqa: BLE001 - context must never break translation
            return cls(phase=phase)


def _fingerprint(
    code: str,
    node_id: int | None,
    culprit_node_id: int | None,
    columns: tuple[str, ...],
    exc_type: str,
) -> str:
    raw = "|".join(
        [
            code,
            str(node_id),
            str(culprit_node_id),
            ",".join(columns),
            exc_type,
        ]
    )
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:12]


@dataclass(frozen=True)
class NodeError:
    code: str
    title: str
    detail: str = ""
    hint: str = ""
    technical: str = ""
    exc_type: str = ""
    severity: str = "error"
    node_id: int | None = None
    node_title: str | None = None
    op: str | None = None
    columns: tuple[str, ...] = ()
    path: str | None = None
    phase: str = "run"
    node_label: str = ""
    exc_module: str = ""
    traceback: str = field(default="", compare=False)
    suggested_fixes: tuple[SuggestedFix, ...] = ()
    row_index: int | None = None
    sample_values: tuple[str, ...] = ()
    failing_count: int | None = None
    did_you_mean: tuple[str, ...] = ()
    culprit_node_id: int | None = None
    culprit_node_title: str | None = None
    locate_status: str = ""
    redacted: bool = False
    params: dict[str, str] = field(default_factory=dict, compare=False)
    fingerprint: str = ""
    created_at: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if not self.fingerprint:
            object.__setattr__(
                self,
                "fingerprint",
                _fingerprint(
                    self.code,
                    self.node_id,
                    self.culprit_node_id,
                    self.columns,
                    self.exc_type,
                ),
            )
        if not self.created_at:
            object.__setattr__(
                self,
                "created_at",
                datetime.now(UTC).isoformat(timespec="seconds"),
            )

    @property
    def summary(self) -> str:
        return self.title

    @property
    def knock_on(self) -> bool:
        return self.code in KNOCK_ON_CODES

    def render_summary(self) -> str:
        return f"{self.node_label}: {self.title}" if self.node_label else self.title

    def render_tooltip(self) -> str:
        parts = [self.render_summary()]
        first = _first_sentence(self.detail)
        if first:
            parts.append(first)
        if self.hint:
            parts.append(f"Fix: {self.hint}")
        tail = self.code
        if self.row_index is not None:
            tail += f" · row {self.row_index:,}"
        parts.append(tail)
        return shorten("\n".join(parts), 600)

    def render_text(self, *, include_technical: bool = True) -> str:
        lines = [f"[{self.code}] {self.render_summary()}"]
        if self.hint:
            lines.append(f"Fix: {self.hint}")
        other_fixes = self.suggested_fixes[1:]
        if other_fixes:
            lines.append("Other fixes: " + " ".join(fix.text for fix in other_fixes))
        if self.columns:
            lines.append("Columns: " + ", ".join(self.columns))
        if self.redacted:
            if self.row_index is not None:
                lines.append(
                    f"Rows/values: row {self.row_index:,} "
                    "(values hidden by privacy setting)"
                )
        elif self.row_index is not None or self.sample_values:
            bits: list[str] = []
            if self.row_index is not None:
                row = f"row {self.row_index:,}"
                if self.sample_values:
                    row += f" ('{self.sample_values[0]}')"
                bits.append(row)
            elif self.sample_values:
                bits.append(f"'{self.sample_values[0]}'")
            if len(self.sample_values) > 1:
                rest = ", ".join(f"'{value}'" for value in self.sample_values[1:])
                bits.append(f"{len(self.sample_values) - 1} more: {rest}")
            lines.append("Rows/values: " + "; ".join(bits))
        if self.culprit_node_id is not None and self.culprit_node_id != self.node_id:
            label = self.culprit_node_title or f"node {self.culprit_node_id}"
            lines.append(f"Caused by: {label} (node {self.culprit_node_id})")
        lines.append(
            f"Phase: {self.phase}   Severity: {self.severity}   Time: {self.created_at}"
        )
        if include_technical and (self.technical or self.traceback):
            lines.append("--- technical ---")
            if self.technical:
                lines.append(
                    f"{self.exc_module + '.' if self.exc_module else ''}"
                    f"{self.exc_type}: {self.technical}".strip(": ")
                )
            if self.traceback:
                lines.append(self.traceback.rstrip())
        return "\n".join(lines)

    def with_updates(self, **changes: Any) -> NodeError:
        changed = replace(self, **changes)
        return replace(
            changed,
            fingerprint=_fingerprint(
                changed.code,
                changed.node_id,
                changed.culprit_node_id,
                changed.columns,
                changed.exc_type,
            ),
        )

    def to_dict(self) -> dict:
        data = asdict(self)

        def convert(value: Any) -> Any:
            if isinstance(value, tuple):
                return [convert(item) for item in value]
            if isinstance(value, list):
                return [convert(item) for item in value]
            if isinstance(value, dict):
                return {key: convert(item) for key, item in value.items()}
            return value

        return convert(data)

    @classmethod
    def from_dict(cls, data: dict) -> NodeError:
        known = {field.name for field in cls.__dataclass_fields__.values()}
        values = {key: value for key, value in (data or {}).items() if key in known}
        fixes = []
        for item in values.get("suggested_fixes") or ():
            if isinstance(item, SuggestedFix):
                fixes.append(item)
            elif isinstance(item, dict):
                fixes.append(
                    SuggestedFix(
                        text=str(item.get("text", "")),
                        kind=str(item.get("kind", "manual")),
                        params=dict(item.get("params") or {}),
                    )
                )
        values["suggested_fixes"] = tuple(fixes)
        for key in ("columns", "sample_values", "did_you_mean"):
            if key in values:
                values[key] = tuple(values[key] or ())
        if "params" in values:
            values["params"] = dict(values["params"] or {})
        return cls(**values)
