"""Remove sample values from anything that can be logged or copied."""

from __future__ import annotations

import re

from trigger_designer.core.errors.catalogue import CATALOGUE, render_entry
from trigger_designer.core.errors.model import NodeError, SuggestedFix

_SCRUBS = (
    (re.compile(r"values:\s*\[.*?\]", re.DOTALL), "values: [<redacted>]"),
    (re.compile(r"""string (['"]).*?\1 to""", re.DOTALL), "string <redacted> to"),
    (
        re.compile(r'invalid date field format:\s*".*?"', re.DOTALL),
        "invalid date field format: <redacted>",
    ),
    (
        re.compile(r'Could not parse string ".*?" according', re.DOTALL),
        "Could not parse string <redacted> according",
    ),
    (
        re.compile(r"first shown value:\s*'.*?'", re.DOTALL),
        "...: <redacted>",
    ),
)


def redact_text(text: str, values=()) -> str:
    result = str(text or "")
    for value in values or ():
        if value:
            result = result.replace(str(value), "<redacted>")
    for pattern, replacement in _SCRUBS:
        result = pattern.sub(replacement, result)
    return result


def redact_error(error: NodeError) -> NodeError:
    values = error.sample_values
    entry = CATALOGUE.get(error.code) or {}
    if entry.get("passthrough"):
        title = redact_text(error.title, values)
        detail = redact_text(error.detail, values)
    else:
        title, detail, fixes = render_entry(error.code, error.params, located=False)
        if not title:
            title = redact_text(error.title, values)
        if not detail:
            detail = redact_text(error.detail, values)
        if not fixes:
            fixes = tuple(fix.text for fix in error.suggested_fixes)
        replacements: list[SuggestedFix] = []
        for index, text in enumerate(fixes):
            old = (
                error.suggested_fixes[index]
                if index < len(error.suggested_fixes)
                else None
            )
            replacements.append(
                SuggestedFix(
                    text=text,
                    kind=old.kind if old is not None else "manual",
                    params=old.params if old is not None else {},
                )
            )
        error = error.with_updates(suggested_fixes=tuple(replacements))
    return error.with_updates(
        title=title,
        detail=detail,
        sample_values=(),
        technical=redact_text(error.technical, values),
        traceback=redact_text(error.traceback, values),
        redacted=True,
        row_index=error.row_index,
    )
