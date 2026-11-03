"""Literals for generated code. Never interpolate user text into code with '{x}'.

Generated scripts are ``exec``'d at Run, and their inputs come from ``.tds``
files that may have been written by someone else. Every value that reaches a
code string goes through one of these helpers so it stays a value and can
never become a statement.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

_SCALARS = (str, int, float, bool, type(None))
_NOT_IDENT = re.compile(r"\W", re.ASCII)


def lit(value: Any) -> str:
    """Python source for a literal value. ``repr`` quotes/escapes str; containers recurse."""
    if isinstance(value, float) and not math.isfinite(value):
        return f"float({str(value)!r})"  # float('nan'), float('inf')
    if isinstance(value, _SCALARS):
        return repr(value)
    if isinstance(value, (list, tuple)):
        inner = ", ".join(lit(v) for v in value)
        if isinstance(value, list):
            return f"[{inner}]"
        return f"({inner}{',' if len(value) == 1 else ''})"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{lit(k)}: {lit(v)}" for k, v in value.items()) + "}"
    raise TypeError(f"cannot render {type(value).__name__} as a code literal")


def lit_dq(text: str) -> str:
    """Double-quoted str literal. JSON string syntax is valid Python."""
    if not isinstance(text, str):
        raise TypeError("lit_dq needs a str")
    return json.dumps(text, ensure_ascii=False)


def lit_list(values) -> str:
    return lit(list(values))


def safe_comment(text: Any) -> str:
    """Text safe inside a ``# ...`` comment: no line breaks (a newline would end it)."""
    return " ".join(
        str(text).replace("\r", " ").replace("\n", " ").replace("\x00", " ").split()
    )


def ident_part(value: Any) -> str:
    """``value`` reduced to ``[A-Za-z0-9_]`` so it is safe inside a variable name."""
    return _NOT_IDENT.sub("_", str(value))
