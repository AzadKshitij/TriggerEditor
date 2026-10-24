"""RuleStack emits ordered-card intents."""

from __future__ import annotations

from qtpy.QtWidgets import QWidget

from trigger_designer.qt.widgets.common import RuleStack


def test_add_and_move_remove_signals(qtbot) -> None:
    stack = RuleStack("Add rule")
    qtbot.addWidget(stack)
    added = []
    removed = []
    moved = []
    stack.add_requested.connect(lambda: added.append(1))
    stack.remove_requested.connect(removed.append)
    stack.move_requested.connect(lambda i, d: moved.append((i, d)))

    stack.add_button.click()
    assert added == [1]

    stack.add_card(0, 3, QWidget())
    stack.add_card(1, 3, QWidget())
    stack.add_card(2, 3, QWidget())
    cards = [
        stack._cards_layout.itemAt(i).widget()
        for i in range(stack._cards_layout.count())
    ]
    assert len(cards) == 3

    # The first card's up is disabled and the last card's down is disabled.
    first_buttons = cards[0].findChildren(type(stack.add_button))
    assert len(first_buttons) == 4
    assert first_buttons[0].isEnabled() is False
    assert first_buttons[1].isEnabled() is True

    last_buttons = cards[2].findChildren(type(stack.add_button))
    assert last_buttons[1].isEnabled() is False

    first_buttons[1].click()
    assert moved == [(0, 1)]
    first_buttons[3].click()
    assert removed == [0]


def test_summary_collapse_and_duplicate(qtbot) -> None:
    stack = RuleStack("Add rule")
    qtbot.addWidget(stack)
    duplicated = []
    stack.duplicate_requested.connect(duplicated.append)
    stack.add_card(
        0,
        2,
        QWidget(),
        summary="Remove currency · US$ → blank",
        collapsible=True,
    )
    stack.add_card(1, 2, QWidget(), summary="Strip commas", collapsible=True)
    assert stack.is_collapsed(0) is False
    stack._cards[0].findChildren(type(stack.add_button))[2].click()
    assert duplicated == [0]
    stack._headers[0].mousePressEvent(None)
    assert stack.is_collapsed(0) is True
    stack.set_card_summary(0, "Changed")
    assert stack._summaries[0].text() == "Changed"


def test_add_button_has_tooltip_and_accessible_name(qtbot) -> None:
    stack = RuleStack("Add another rule")
    qtbot.addWidget(stack)
    assert stack.add_button.toolTip() == "Add another rule"
    assert stack.add_button.accessibleName() == "Add another rule"
