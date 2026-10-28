"""Shortcut registry: defaults, storage, and the refusals.

The preferences page is only a view over this module, so the interesting
behaviour is here: what a stored map resolves to, which sequences are refused,
and that applying a map moves the window's real ``QAction`` shortcuts.
"""

from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
)

from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import QAction, QApplication, QWidget

from trigger_designer.qt.helpers import shortcuts
from trigger_designer.qt.helpers.node_arrange import SHORTCUT_COMMANDS

APP = QApplication.instance() or QApplication([])

PORTABLE = QKeySequence.SequenceFormat.PortableText


class FakePreferences:
    def __init__(self, values: dict | None = None) -> None:
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value) -> None:
        self.values[key] = value


class FakeWindow(QWidget):
    """A window with the actions the real one owns, plus one unrelated action."""

    def __init__(self) -> None:
        super().__init__()
        for command in SHORTCUT_COMMANDS:
            setattr(self, command.action, QAction(command.label, self))
        self.other_action = QAction("&Save As", self)
        self.other_action.setShortcut(QKeySequence("Ctrl+Shift+S"))


def text_of(action: QAction) -> str:
    return action.shortcut().toString(PORTABLE)


# -- defaults ------------------------------------------------------------


def test_every_command_has_a_known_default():
    defaults = shortcuts.defaults()
    assert set(defaults) == {command.id for command in SHORTCUT_COMMANDS}
    assert defaults["align_centers_h"] == "Ctrl+Shift+H"
    assert defaults["align_centers_v"] == "Ctrl+Shift+V"


def test_defaults_are_unique_and_parse():
    used = [value for value in shortcuts.defaults().values() if value]
    assert len(set(used)) == len(used)
    for value in used:
        assert shortcuts.sequence(value).toString(PORTABLE) == value


# -- normalisation and storage -------------------------------------------


def test_normalize_canonicalises_case_and_order():
    assert shortcuts.normalize("ctrl+shift+h") == "Ctrl+Shift+H"
    assert shortcuts.normalize("  ") == ""
    assert shortcuts.normalize("not a key") == ""
    assert shortcuts.sequence("") == QKeySequence()


def test_load_without_overrides_returns_the_defaults():
    assert shortcuts.load_shortcuts(FakePreferences()) == shortcuts.defaults()


def test_save_and_load_round_trip():
    prefs = FakePreferences()
    shortcuts.save_shortcut(prefs, "arrange_row", "ctrl+alt+r")

    assert shortcuts.load_shortcuts(prefs)["arrange_row"] == "Ctrl+Alt+R"
    assert shortcuts.defaults()["arrange_row"] == ""


def test_an_empty_string_clears_a_shortcut_and_stays_cleared():
    prefs = FakePreferences()
    shortcuts.save_shortcut(prefs, "align_centers_h", "")
    assert shortcuts.load_shortcuts(prefs)["align_centers_h"] == ""


def test_unknown_ids_and_broken_json_are_ignored():
    prefs = FakePreferences(
        {"editor/shortcuts": json.dumps({"not_a_command": "Ctrl+Q"})}
    )
    assert shortcuts.load_shortcuts(prefs) == shortcuts.defaults()

    broken = FakePreferences({"editor/shortcuts": "{not json"})
    assert shortcuts.load_shortcuts(broken) == shortcuts.defaults()

    prefs.set("editor/shortcuts", "[1, 2]")
    assert shortcuts.load_shortcuts(prefs) == shortcuts.defaults()


def test_saving_an_unknown_command_does_nothing():
    prefs = FakePreferences()
    shortcuts.save_shortcut(prefs, "not_a_command", "Ctrl+Q")
    assert "editor/shortcuts" not in prefs.values


def test_reset_forgets_overrides():
    prefs = FakePreferences()
    shortcuts.save_shortcut(prefs, "arrange_grid", "Ctrl+Alt+G")
    shortcuts.reset_shortcuts(prefs)
    assert shortcuts.load_shortcuts(prefs) == shortcuts.defaults()


# -- conflicts -----------------------------------------------------------


def test_a_command_may_keep_its_own_sequence():
    assert (
        shortcuts.conflict_message(
            "Ctrl+Shift+H", "align_centers_h", shortcuts.defaults()
        )
        is None
    )


def test_a_sequence_used_by_another_command_is_refused():
    message = shortcuts.conflict_message(
        "Ctrl+Shift+H", "align_centers_v", shortcuts.defaults()
    )
    assert message is not None
    assert "Ctrl+Shift+H" in message
    assert "Align Horizontal Centers" in message


def test_a_sequence_owned_by_another_action_is_refused():
    window = FakeWindow()
    reserved = shortcuts.reserved_sequences(window)

    assert reserved["Ctrl+Shift+S"] == "Save As"
    message = shortcuts.conflict_message(
        "Ctrl+Shift+S", "arrange_row", shortcuts.defaults(), reserved
    )
    assert message is not None
    assert "Save As" in message


def test_the_windows_own_arrange_actions_are_not_reserved():
    window = FakeWindow()
    # The defaults sit on the Arrange actions themselves; they must stay legal.
    reserved = shortcuts.reserved_sequences(window)
    assert "Ctrl+Shift+H" not in reserved


def test_a_plain_key_is_refused():
    message = shortcuts.conflict_message("H", "arrange_row", shortcuts.defaults())
    assert message is not None
    assert "Ctrl" in message


def test_a_function_key_on_its_own_is_allowed():
    assert shortcuts.conflict_message("F5", "arrange_row", shortcuts.defaults()) is None


def test_an_empty_sequence_is_never_a_conflict():
    assert shortcuts.conflict_message("", "arrange_row", shortcuts.defaults()) is None


# -- applying ------------------------------------------------------------


def test_apply_to_window_sets_clears_and_keeps_defaults():
    window = FakeWindow()
    mapping = shortcuts.defaults()
    mapping["align_centers_h"] = "Ctrl+Alt+H"
    mapping["arrange_row"] = "Ctrl+Alt+R"

    shortcuts.apply_to_window(window, mapping)

    assert text_of(window.actArrangeAlignH) == "Ctrl+Alt+H"
    assert text_of(window.actArrangeRow) == "Ctrl+Alt+R"
    # Untouched commands keep their default.
    assert text_of(window.actArrangeAlignV) == "Ctrl+Shift+V"
    # A command without a default stays unbound.
    assert text_of(window.actArrangeDistributeH) == ""


def test_apply_a_cleared_shortcut_leaves_the_action_unbound():
    window = FakeWindow()
    mapping = shortcuts.defaults()
    mapping["align_centers_h"] = ""

    shortcuts.apply_to_window(window, mapping)

    assert window.actArrangeAlignH.shortcuts() == []
    assert text_of(window.actToggleSnap) == ""
