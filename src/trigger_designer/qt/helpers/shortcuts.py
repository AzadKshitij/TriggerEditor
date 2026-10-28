"""User-assignable keyboard shortcuts for the Arrange menu.

The commands themselves live in :mod:`trigger_designer.qt.helpers.node_arrange`;
this module owns the part the Preferences page needs: what a command's key
sequence is, where it is stored, whether it clashes with something else, and
how it is put onto the main window's actions.

Storage is one JSON object under ``editor/shortcuts``:

.. code-block:: json

    {"align_centers_h": "Ctrl+Shift+H", "arrange_row": ""}

Only commands the user has changed are written. A missing key means "use the
default", and an empty string means "no shortcut" - the two must stay
distinguishable, which is why an empty value is stored rather than removed.

The window's own sequences are collected at runtime rather than hardcoded, so
a shortcut added elsewhere in the app is picked up as reserved without anyone
maintaining a second list.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from loguru import logger
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import QAction, QShortcut

from trigger_designer.qt.helpers.node_arrange import (
    SHORTCUT_COMMANDS,
    ArrangeCommand,
    COMMAND_BY_ID,
)

#: Preference key holding the JSON map.
PREF_KEY = "editor/shortcuts"

_PORTABLE = QKeySequence.SequenceFormat.PortableText

_MODIFIERS = ("Ctrl", "Alt", "Shift", "Meta")


def command_by_id(command_id: str) -> Optional[ArrangeCommand]:
    return COMMAND_BY_ID.get(command_id)


def label_for(command_id: str) -> str:
    command = COMMAND_BY_ID.get(command_id)
    return command.label if command is not None else command_id


def normalize(sequence: str) -> str:
    """Canonical portable text for a key sequence, or ``""`` if it is not one."""
    text = (sequence or "").strip()
    if not text:
        return ""
    try:
        parsed = QKeySequence.fromString(text, _PORTABLE)
    except Exception:  # pragma: no cover - defensive
        return ""
    if parsed.isEmpty():
        return ""
    return parsed.toString(_PORTABLE)


def defaults() -> dict[str, str]:
    return {command.id: command.default_shortcut for command in SHORTCUT_COMMANDS}


def sequence(text: str) -> QKeySequence:
    """Parse stored portable text into a ``QKeySequence``.

    Empty text means "no shortcut" and yields an empty sequence, which is
    what ``QAction.setShortcut`` expects when a command was cleared.
    """
    canonical = normalize(text)
    if not canonical:
        return QKeySequence()
    return QKeySequence.fromString(canonical, _PORTABLE)


def _decode(raw: Any) -> dict[str, str]:
    if isinstance(raw, dict):
        data = raw
    else:
        try:
            data = json.loads(str(raw or "{}"))
        except TypeError, ValueError:
            return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items() if isinstance(value, str)}


def load_shortcuts(prefs: Any) -> dict[str, str]:
    """Every command's sequence, with the defaults filled in."""
    resolved = defaults()
    stored = _decode(prefs.get(PREF_KEY, "{}"))
    for command_id, text in stored.items():
        if command_id not in resolved:
            continue
        resolved[command_id] = normalize(text)
    return resolved


def save_shortcut(prefs: Any, command_id: str, sequence: str) -> None:
    """Store one command's sequence. An empty string clears it."""
    if command_id not in defaults():
        logger.warning(f"Unknown shortcut command: {command_id!r}")
        return
    stored = _decode(prefs.get(PREF_KEY, "{}"))
    stored[command_id] = normalize(sequence)
    prefs.set(PREF_KEY, json.dumps(stored, sort_keys=True))


def reset_shortcuts(prefs: Any) -> None:
    """Forget every override, so the registry defaults apply again."""
    prefs.set(PREF_KEY, "{}")


def _has_safe_prefix(sequence: str) -> bool:
    """A shortcut must not shadow plain typing in the node editors."""
    parts = sequence.split("+")
    if any(part in _MODIFIERS for part in parts[:-1]):
        return True
    last = parts[-1] if parts else ""
    return len(last) > 1 and last[0] == "F" and last[1:].isdigit()


def _our_actions(window: Any) -> set:
    return {
        action
        for action in (
            getattr(window, command.action, None) for command in SHORTCUT_COMMANDS
        )
        if action is not None
    }


def _clean_label(text: str) -> str:
    return (text or "").replace("&", "").strip()


def reserved_sequences(window: Any) -> dict[str, str]:
    """Sequences the window already uses, mapped to a readable owner name."""
    if window is None:
        return {}
    ours = _our_actions(window)
    reserved: dict[str, str] = {}

    for action in window.findChildren(QAction):
        if action in ours:
            continue
        try:
            shortcuts = action.shortcuts()
        except RuntimeError:  # pragma: no cover - Qt object already gone
            continue
        for sequence in shortcuts:
            text = normalize(sequence.toString(_PORTABLE))
            if text and text not in reserved:
                reserved[text] = _clean_label(action.text()) or "another action"

    for shortcut in window.findChildren(QShortcut):
        try:
            text = normalize(shortcut.key().toString(_PORTABLE))
        except RuntimeError:  # pragma: no cover - Qt object already gone
            continue
        if text and text not in reserved:
            reserved[text] = "another action"

    return reserved


def conflict_message(
    sequence: str,
    command_id: str,
    assigned: dict[str, str],
    reserved: Optional[dict[str, str]] = None,
) -> Optional[str]:
    """Why ``sequence`` cannot be used for ``command_id``, or ``None``.

    ``assigned`` is the full command -> sequence map as it will be once the
    edit is applied, so a command keeps its own current sequence without
    reporting itself.
    """
    text = normalize(sequence)
    if not text:
        return None

    if not _has_safe_prefix(text):
        return (
            "A shortcut needs Ctrl, Alt or Shift, or a function key. "
            "A plain key would hide typing in the node editors."
        )

    for other_id, other_text in assigned.items():
        if other_id == command_id:
            continue
        if normalize(other_text) == text:
            return f"{text} is already used by {label_for(other_id)}."

    owner = (reserved or {}).get(text)
    if owner:
        return f"{text} is already used by {owner}."

    return None


def apply_to_window(window: Any, mapping: Optional[dict[str, str]] = None) -> None:
    """Put every command's sequence onto the window's actions."""
    if window is None:
        return
    if mapping is None:
        from trigger_designer.qt.preferences import get_preferences

        mapping = load_shortcuts(get_preferences())

    for command in SHORTCUT_COMMANDS:
        action = getattr(window, command.action, None)
        if action is None:
            continue
        text = mapping.get(command.id, command.default_shortcut)
        if text:
            action.setShortcut(sequence(text))
        else:
            action.setShortcut(QKeySequence())


def sequence_text(action: Any) -> str:
    """The first sequence of ``action`` as portable text."""
    if action is None:
        return ""
    try:
        shortcuts = action.shortcuts()
    except RuntimeError:  # pragma: no cover - Qt object already gone
        return ""
    if not shortcuts:
        return ""
    return normalize(shortcuts[0].toString(_PORTABLE))
