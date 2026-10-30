"""Wording of shaping messages that used to point the user at the wrong control."""

from __future__ import annotations

from trigger_designer.core.errors.catalogue import CATALOGUE


def test_too_many_possible_matches_hint_names_what_changes_the_count() -> None:
    hint = CATALOGUE["TD-SHAPE-072"]["hint"]
    # The tolerance does not change how many pairs are compared; keys and the
    # date window do.
    assert "tolerance" not in hint.lower()
    assert "key" in hint.lower() and "date window" in hint.lower()
