"""Data Profile: pass the input through and profile it (Qt-free adapter).

The engine is ``core/profile.py`` (shared with the run record and the workpaper);
this module only fits it to the shaping-node runner contract.
"""

from __future__ import annotations

import dataclasses

import polars as pl

from trigger_designer.core.profile import ProfileSettings, profile_table
from trigger_designer.core.shaping.common import LIVE_SAMPLE_ROWS, as_lazy

DEFAULTS: dict = dataclasses.asdict(ProfileSettings())

SAMPLE_MODES = ("full", "head", "random")

#: The live preview profiles on the GUI thread, and Polars 2.0 plans a profile in
#: time that grows roughly with the square of the column count (about 1 s at 150
#: columns, 4 s at 400). Beyond this the preview is skipped; a workflow Run still
#: profiles every column.
LIVE_MAX_COLUMNS = 150

#: Inclusive (low, high) per numeric setting; loaded files are clamped into range.
LIMITS: dict[str, tuple[int, int]] = {
    "sample_rows": (1_000, 100_000_000),
    "seed": (0, 2_147_483_647),
    "top_n": (1, 50),
    "approx_distinct_threshold": (10_000, 2_000_000_000),
    "histogram_bins": (5, 100),
}


def normalize(settings: dict | None) -> dict:
    """Return a complete settings dict with every value inside its range.

    Old files carry no keys (defaults apply); a hand-edited file may carry an
    out-of-range number or an unknown sample mode, which is clamped silently.
    """
    out = dict(DEFAULTS)
    for key in DEFAULTS:
        if settings and key in settings:
            out[key] = settings[key]
    for key, (low, high) in LIMITS.items():
        try:
            value = int(out[key])
        except TypeError, ValueError:
            value = DEFAULTS[key]
        out[key] = min(max(value, low), high)
    if out["sample_mode"] not in SAMPLE_MODES:
        out["sample_mode"] = "full"
    return out


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    """Return ``[input unchanged, profile table]``.

    The profile is computed here, not deferred, so a failure surfaces during
    Run (nothing else in a Run collects unless a sink does).
    """
    frame = as_lazy(frames[0])
    profile = profile_table(frame, **normalize(settings))
    return [frame, profile.lazy()]


def mode_text(settings: dict) -> str:
    """Short description of which rows are profiled."""
    s = normalize(settings)
    rows = f"{s['sample_rows']:,}"
    if s["sample_mode"] == "head":
        return f"First {rows} rows"
    if s["sample_mode"] == "random":
        return f"Random {rows} rows (seed {s['seed']})"
    return "All rows"


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    """Dock chips: which rows are profiled, and what live evaluation shows."""
    del frames
    full = normalize(settings)["sample_mode"] == "full"
    return [
        (mode_text(settings), "" if full else "accent"),
        (
            f"Live preview: first {LIVE_SAMPLE_ROWS} rows. Run the workflow to profile all rows.",
            "muted",
        ),
    ]
