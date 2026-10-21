"""Canvas rendering settings, read from the user's preferences.

Zoomed out far enough, the canvas stops drawing the parts of a node it can
spare. Which parts those are is the user's call: the preferences say, and this
module hands the answer to the graphics scene, which owns the level-of-detail
policy.

The scene knows three elements of its own (``content``, ``label`` and
``sockets``). The status indicator is painted by this application rather than
by the library, so it is registered here under the key ``badge``.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

#: The elements the user can choose between, in the order the dialog shows
#: them.
ELEMENTS: tuple[tuple[str, str], ...] = (
    ("card", "Node card"),
    ("sockets", "Sockets"),
    ("label", "Label"),
    ("indicator", "Status indicator"),
)

#: The key the graphics scene knows each element by.
ELEMENT_KEYS = {
    "card": "content",
    "sockets": "sockets",
    "label": "label",
    "indicator": "badge",
}

#: The modes an element can be in.
MODES: tuple[str, ...] = ("always", "auto", "never")

#: The threshold is stored as a percentage of full size.
DEFAULT_THRESHOLD_PERCENT = 50


def _mode(value: Any) -> str:
    """One valid mode, whatever the preferences file happens to hold."""
    text = str(value or "").strip().lower()
    return text if text in MODES else "auto"


def threshold_percent(prefs: Any) -> int:
    """The zoom level, as a percentage, at which the canvas simplifies."""
    raw = prefs.get("editor/render_detail_threshold", DEFAULT_THRESHOLD_PERCENT)
    try:
        percent = int(raw)
    except (TypeError, ValueError):
        percent = DEFAULT_THRESHOLD_PERCENT
    return max(0, min(100, percent))


def threshold_scale(prefs: Any) -> float:
    """The zoom scale at which the canvas starts simplifying.

    A threshold of 0 means the canvas never simplifies, and 1 means it
    simplifies at every zoom below full size.
    """
    return threshold_percent(prefs) / 100.0


def policy_from_preferences(prefs: Any) -> dict[str, str]:
    """The per-element modes, keyed the way the graphics scene wants them."""
    policy: dict[str, str] = {}
    for name, _title in ELEMENTS:
        # No fallback here: the defaults live in the preference store, and the
        # label's default is not "auto" like the others.
        policy[ELEMENT_KEYS[name]] = _mode(prefs.get(f"editor/render_detail_{name}"))
    return policy


def apply_render_settings_to_scene(scene: Any, prefs: Any = None) -> None:
    """Push the user's rendering choices into one scene's graphics scene."""
    gr_scene = getattr(scene, "grScene", None)
    if gr_scene is None:
        return
    if prefs is None:
        from trigger_designer.qt.preferences import get_preferences

        prefs = get_preferences()
    setter = getattr(gr_scene, "set_detail_policy", None)
    if setter is None:
        logger.warning(
            "The installed nodeeditor has no detail policy; the canvas keeps "
            "its own rules"
        )
        return
    percent = threshold_percent(prefs)
    policy = policy_from_preferences(prefs)
    gr_scene.detail_lod_threshold = percent / 100.0
    setter(policy)
    logger.info(
        "Canvas rendering: simplify below {}%, card {}, sockets {}, label {}, "
        "indicator {}",
        percent,
        policy["content"],
        policy["sockets"],
        policy["label"],
        policy["badge"],
    )
    # The threshold is read on the next paint, so ask for one.
    gr_scene.update()
