"""Layouts as data: an ordered list of placements applied one after another.

A placement says *where one panel goes*. Applying them in order against an
empty host reproduces the layout, so the same description serves the default
arrangement, built-in presets and tests.

``relative_to`` is what the panel docks against:

* ``None``   - the whole window edge (a full-height column or a full-width row);
* ``CENTRAL`` - the workflow canvas' own area (the panel only spans the canvas);
* a panel id - the area that panel currently lives in (placed earlier in the list).

``Area.TAB`` ignores the edge: the panel joins the tab group of ``relative_to``
(which must then be a panel id).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from trigger_designer.qt.docking.panel import (
    CENTRAL,
    PANEL_CONFIG,
    PANEL_HISTORY,
    PANEL_LOGS,
    PANEL_PREVIEW,
)


class Area(Enum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    TAB = "tab"


@dataclass(frozen=True)
class Placement:
    panel_id: str
    area: Area
    relative_to: str | None = None


@dataclass(frozen=True)
class LayoutSpec:
    """An ordered list of placements plus optional size hints in pixels."""

    name: str
    placements: tuple[Placement, ...]
    #: panel_id -> preferred width (LEFT/RIGHT panels) or height (TOP/BOTTOM).
    sizes: dict[str, int] = field(default_factory=dict)
    #: Panel that is the visible tab in its group once applied.
    active: tuple[str, ...] = ()


DEFAULT_LAYOUT = LayoutSpec(
    name="Default",
    placements=(
        Placement(PANEL_CONFIG, Area.LEFT, None),
        Placement(PANEL_LOGS, Area.BOTTOM, CENTRAL),
        Placement(PANEL_PREVIEW, Area.TAB, PANEL_LOGS),
        Placement(PANEL_HISTORY, Area.TAB, PANEL_LOGS),
    ),
    sizes={PANEL_CONFIG: 340, PANEL_LOGS: 260},
    active=(PANEL_LOGS,),
)

CLASSIC_LAYOUT = LayoutSpec(
    name="Classic",
    placements=(
        Placement(PANEL_CONFIG, Area.LEFT, CENTRAL),
        Placement(PANEL_LOGS, Area.BOTTOM, None),
        Placement(PANEL_PREVIEW, Area.TAB, PANEL_LOGS),
        Placement(PANEL_HISTORY, Area.TAB, PANEL_LOGS),
    ),
    sizes={PANEL_CONFIG: 340, PANEL_LOGS: 260},
    active=(PANEL_LOGS,),
)

PRESETS: dict[str, LayoutSpec] = {
    DEFAULT_LAYOUT.name: DEFAULT_LAYOUT,
    CLASSIC_LAYOUT.name: CLASSIC_LAYOUT,
}


def validate_layout(spec: LayoutSpec, known_ids: Iterable[str]) -> list[str]:
    """Return human-readable problems with ``spec``; an empty list means valid.

    Never raises: every problem is reported as text so callers can show it.
    """
    known = set(known_ids)
    placed: set[str] = set()
    problems: list[str] = []

    for index, placement in enumerate(spec.placements):
        panel = placement.panel_id
        target = placement.relative_to
        where = f"placement {index} ({panel!r})"

        if panel not in known:
            problems.append(f"{where}: unknown panel id {panel!r}")
        if panel in placed:
            problems.append(f"{where}: panel {panel!r} is placed more than once")

        if placement.area is Area.TAB and target is None:
            problems.append(f"{where}: tab area needs a panel to join, got none")
        elif placement.area is Area.TAB and target == CENTRAL:
            problems.append(f"{where}: tab area cannot join {CENTRAL!r}")

        if target is None or target == CENTRAL:
            pass
        elif target == panel:
            problems.append(f"{where}: panel is placed relative to itself")
        elif target not in known:
            problems.append(f"{where}: relative_to names unknown panel id {target!r}")
        elif target not in placed:
            problems.append(
                f"{where}: relative_to {target!r} is not placed earlier in the list"
            )

        placed.add(panel)

    for panel in spec.sizes:
        if panel not in placed:
            problems.append(
                f"size hint names panel {panel!r} which the layout does not place"
            )
    for panel in spec.active:
        if panel not in placed:
            problems.append(f"active entry {panel!r} is not a panel the layout places")

    return problems
