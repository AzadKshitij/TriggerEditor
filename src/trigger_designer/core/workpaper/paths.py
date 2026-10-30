"""Output-path rules shared by the writer and by the run record (Qt-free)."""

from __future__ import annotations

import os


def unique_path(path: str) -> str:
    """``path``, or the first free ``name (2).ext``, ``name (3).ext`` ..."""
    stem, ext = os.path.splitext(path)
    candidate, n = path, 2
    while os.path.exists(candidate):
        candidate = f"{stem} ({n}){ext}"
        n += 1
    return candidate


def predict_output_path(path: str, mode: str) -> str:
    """The file a run would write for ``if_exists`` mode ``mode`` (no side effects).

    The run record fingerprints the workpaper after it is written, so it needs the
    versioned name, not the name the user typed.
    """
    if not path:
        return path
    return unique_path(path) if mode == "version" else path
