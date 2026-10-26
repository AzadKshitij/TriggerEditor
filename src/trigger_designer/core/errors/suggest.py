"""Small "did you mean" helper for columns, sheets and functions."""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable

_NORMALISE = re.compile(r"[\s_\-]+")


def normalise_name(value: str) -> str:
    return _NORMALISE.sub("", str(value or "")).casefold()


def suggest_names(
    name: str,
    candidates: Iterable[str],
    *,
    limit: int = 3,
    cutoff: float = 0.6,
) -> tuple[str, ...]:
    target = normalise_name(name)
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        text = str(candidate)
        if text not in seen:
            seen.add(text)
            unique.append(text)

    exact = [item for item in unique if normalise_name(item) == target and target]
    if exact:
        return tuple(exact[:limit])

    by_normalised = {normalise_name(item): item for item in unique}
    matches = difflib.get_close_matches(
        target, list(by_normalised), n=limit, cutoff=cutoff
    )
    return tuple(by_normalised[match] for match in matches)
