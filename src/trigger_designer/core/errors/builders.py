"""Build errors that are not exceptions (knock-on, config, skipped)."""

from __future__ import annotations

from typing import Any

from trigger_designer.core.errors.catalogue import CATALOGUE, render_entry
from trigger_designer.core.errors.model import ErrorContext, NodeError, SuggestedFix


def make_error(
    code: str,
    ctx: ErrorContext | None = None,
    **params: Any,
) -> NodeError:
    context = ctx or ErrorContext()
    values = {key: value for key, value in params.items() if value is not None}
    values.setdefault("node_label", context.node_label)
    values.setdefault("culprit_label", "")
    title, detail, fixes = render_entry(code, values, located=False)
    entry = CATALOGUE.get(code) or {}
    suggested = tuple(SuggestedFix(text=text) for text in fixes)
    return NodeError(
        code=code,
        title=title,
        detail=detail,
        hint=fixes[0] if fixes else entry.get("hint", ""),
        severity=entry.get("severity", "error"),
        suggested_fixes=suggested,
        **context.error_fields(),
        culprit_node_id=params.get("culprit_node_id"),
        culprit_node_title=params.get("culprit_node_title"),
        params={
            key: str(value)
            for key, value in values.items()
            if key not in {"culprit_node_id", "culprit_node_title"}
        },
    )
