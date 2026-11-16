"""Dock layout presets and their validation. Pure data: no Qt application needed."""

from __future__ import annotations

from trigger_designer.qt.docking.layouts import (
    CLASSIC_LAYOUT,
    DEFAULT_LAYOUT,
    PRESETS,
    Area,
    LayoutSpec,
    Placement,
    validate_layout,
)
from trigger_designer.qt.docking.panel import (
    CENTRAL,
    PANEL_CONFIG,
    PANEL_HISTORY,
    PANEL_LOGS,
    PANEL_PREVIEW,
)

KNOWN = (PANEL_CONFIG, PANEL_LOGS, PANEL_PREVIEW, PANEL_HISTORY)


def _spec(*placements: Placement, sizes=None, active=()) -> LayoutSpec:
    return LayoutSpec(
        name="Test",
        placements=tuple(placements),
        sizes=dict(sizes or {}),
        active=tuple(active),
    )


def test_both_presets_validate_cleanly() -> None:
    assert validate_layout(DEFAULT_LAYOUT, KNOWN) == []
    assert validate_layout(CLASSIC_LAYOUT, KNOWN) == []


def test_default_layout_placements_are_exact() -> None:
    assert DEFAULT_LAYOUT.placements == (
        Placement(PANEL_CONFIG, Area.LEFT, None),
        Placement(PANEL_LOGS, Area.BOTTOM, CENTRAL),
        Placement(PANEL_PREVIEW, Area.TAB, PANEL_LOGS),
        Placement(PANEL_HISTORY, Area.TAB, PANEL_LOGS),
    )
    assert DEFAULT_LAYOUT.sizes == {PANEL_CONFIG: 340, PANEL_LOGS: 260}
    assert DEFAULT_LAYOUT.active == (PANEL_LOGS,)


def test_classic_layout_placements_are_exact_and_ordered() -> None:
    assert CLASSIC_LAYOUT.placements == (
        Placement(PANEL_CONFIG, Area.LEFT, CENTRAL),
        Placement(PANEL_LOGS, Area.BOTTOM, None),
        Placement(PANEL_PREVIEW, Area.TAB, PANEL_LOGS),
        Placement(PANEL_HISTORY, Area.TAB, PANEL_LOGS),
    )
    assert CLASSIC_LAYOUT.sizes == {PANEL_CONFIG: 340, PANEL_LOGS: 260}
    assert CLASSIC_LAYOUT.active == (PANEL_LOGS,)


def test_presets_are_keyed_by_name_default_first() -> None:
    assert list(PRESETS) == ["Default", "Classic"]
    assert PRESETS["Default"] is DEFAULT_LAYOUT
    assert PRESETS["Classic"] is CLASSIC_LAYOUT


def test_unplaced_known_panels_are_allowed() -> None:
    assert validate_layout(DEFAULT_LAYOUT, (*KNOWN, "extra")) == []


def test_unknown_panel_id_is_reported() -> None:
    spec = _spec(Placement("ghost", Area.LEFT, None))
    problems = validate_layout(spec, KNOWN)
    assert problems
    assert any("ghost" in p for p in problems)


def test_duplicate_placement_is_reported() -> None:
    spec = _spec(
        Placement(PANEL_LOGS, Area.BOTTOM, None),
        Placement(PANEL_LOGS, Area.BOTTOM, None),
    )
    problems = validate_layout(spec, KNOWN)
    assert problems
    assert any(PANEL_LOGS in p for p in problems)


def test_relative_to_unknown_panel_is_reported() -> None:
    spec = _spec(Placement(PANEL_LOGS, Area.BOTTOM, "missing"))
    problems = validate_layout(spec, KNOWN)
    assert problems
    assert any("missing" in p for p in problems)


def test_relative_to_panel_placed_later_is_reported() -> None:
    spec = _spec(
        Placement(PANEL_PREVIEW, Area.TAB, PANEL_LOGS),
        Placement(PANEL_LOGS, Area.BOTTOM, None),
    )
    problems = validate_layout(spec, KNOWN)
    assert problems
    assert any(PANEL_LOGS in p for p in problems)


def test_panel_relative_to_itself_is_reported() -> None:
    spec = _spec(Placement(PANEL_LOGS, Area.BOTTOM, PANEL_LOGS))
    problems = validate_layout(spec, KNOWN)
    assert problems
    assert any(PANEL_LOGS in p for p in problems)


def test_tab_without_target_is_reported() -> None:
    spec = _spec(
        Placement(PANEL_LOGS, Area.BOTTOM, None),
        Placement(PANEL_PREVIEW, Area.TAB, None),
    )
    problems = validate_layout(spec, KNOWN)
    assert problems
    assert any(PANEL_PREVIEW in p for p in problems)


def test_tab_joining_central_is_reported() -> None:
    spec = _spec(Placement(PANEL_LOGS, Area.TAB, CENTRAL))
    problems = validate_layout(spec, KNOWN)
    assert problems
    assert any(PANEL_LOGS in p for p in problems)


def test_size_hint_for_unplaced_panel_is_reported() -> None:
    spec = _spec(
        Placement(PANEL_LOGS, Area.BOTTOM, None),
        sizes={PANEL_HISTORY: 200},
    )
    problems = validate_layout(spec, KNOWN)
    assert problems
    assert any(PANEL_HISTORY in p for p in problems)


def test_active_entry_for_unplaced_panel_is_reported() -> None:
    spec = _spec(
        Placement(PANEL_LOGS, Area.BOTTOM, None),
        active=(PANEL_PREVIEW,),
    )
    problems = validate_layout(spec, KNOWN)
    assert problems
    assert any(PANEL_PREVIEW in p for p in problems)
