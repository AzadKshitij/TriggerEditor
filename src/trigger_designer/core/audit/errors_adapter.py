"""Turn a failed node into the ``error`` dict of a run record (plan 02 3.8a).

Qt-free. Plan 03's :class:`NodeError` is a frozen dataclass without ``to_dict``;
this adapter owns the stored shape. The stable key set (the first twelve) is
always present; enrichment details (culprit, row, sample values) ride along
when the error has them. Tuples become lists so ``canonical_json`` accepts the
result, and ``technical`` is capped.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

TECHNICAL_CAP = 8000

#: Keys every stored error has, in the order of plan 03's NodeError.
STABLE_KEYS = (
    "code",
    "title",
    "detail",
    "hint",
    "technical",
    "exc_type",
    "severity",
    "node_id",
    "node_title",
    "op",
    "columns",
    "path",
)

#: Extra NodeError fields kept when present (None/empty ones are still written
#: so the stored shape does not depend on the error).
_EXTRA_KEYS = (
    "phase",
    "node_label",
    "exc_module",
    "row_index",
    "failing_count",
    "culprit_node_id",
    "culprit_node_title",
    "locate_status",
    "redacted",
    "fingerprint",
)
_EXTRA_LISTS = ("sample_values", "did_you_mean")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(v) for v in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def node_error_to_dict(error: Any) -> dict:
    """The stored dict for a :class:`NodeError` (or any object shaped like one)."""
    out: dict[str, Any] = {}
    for key in STABLE_KEYS:
        value = getattr(error, key, None)
        if key == "columns":
            value = list(value or ())
        elif key in ("code", "title", "severity"):
            value = str(value or ("error" if key == "severity" else ""))
        elif key in ("detail", "hint", "technical", "exc_type"):
            value = str(value or "")
        out[key] = value
    out["technical"] = out["technical"][:TECHNICAL_CAP]
    for key in _EXTRA_KEYS:
        out[key] = getattr(error, key, None)
    for key in _EXTRA_LISTS:
        out[key] = list(getattr(error, key, ()) or ())
    fixes = getattr(error, "suggested_fixes", ()) or ()
    out["suggested_fixes"] = [str(getattr(fix, "text", fix)) for fix in fixes]
    params = getattr(error, "params", None)
    out["params"] = _json_safe(params) if isinstance(params, dict) else {}
    return _json_safe(out)


def _fallback_dict(text: str, node: Any) -> dict:
    """Used only when plan 03's translator cannot be imported."""
    return {
        "code": "TD-SYS-999",
        "title": "The step failed",
        "detail": "",
        "hint": "",
        "technical": str(text)[:TECHNICAL_CAP],
        "exc_type": "",
        "severity": "error",
        "node_id": getattr(node, "id", None),
        "node_title": getattr(node, "node_title", None),
        "op": None,
        "columns": [],
        "path": None,
    }


def _translate(
    source: Any,
    node: Any,
    *,
    redact: bool,
    traceback_text: str,
    enricher: Callable[[Any, Any], Any] | None,
    enrich: bool,
) -> dict:
    try:
        from trigger_designer.core.errors import enrich_sync, translate_exception
    except Exception:  # noqa: BLE001 - plan 03 absent: keep the record writable
        return _fallback_dict(str(source), node)
    try:
        error = translate_exception(
            source,
            node=node,
            phase="run",
            redact=redact,
            traceback_text=traceback_text,
        )
        if enricher is not None:
            error = enricher(error, node) or error
        elif enrich:
            error = enrich_sync(error, redact=redact).root
        return node_error_to_dict(error)
    except Exception:  # noqa: BLE001 - never let a record fail on its error text
        return _fallback_dict(str(source), node)


def error_to_dict(
    result: Any,
    node: Any = None,
    *,
    enrich: bool = False,
    redact: bool = False,
    enricher: Callable[[Any, Any], Any] | None = None,
) -> dict:
    """The ``error`` dict for a failed ``ExecutionResult``."""
    exc = getattr(result, "exception", None)
    exc = getattr(exc, "original_exception", None) or exc
    source = exc if exc is not None else str(getattr(result, "error", "") or "")
    return _translate(
        source,
        node,
        redact=redact,
        traceback_text=str(getattr(result, "traceback_text", "") or ""),
        enricher=enricher,
        enrich=enrich,
    )


def exception_to_dict(
    exc: BaseException,
    node: Any = None,
    *,
    enrich: bool = False,
    redact: bool = False,
    enricher: Callable[[Any, Any], Any] | None = None,
) -> dict:
    """The ``error`` dict for an exception raised outside the executor."""
    exc = getattr(exc, "original_exception", None) or exc
    return _translate(
        exc, node, redact=redact, traceback_text="", enricher=enricher, enrich=enrich
    )
