"""The external-edit banner and its review dialog (qt/widgets/external_edit_banner.py).

Every mode shows exactly the actions it needs, the messages are exact, and
every action is a named, tooltipped, text-free IconButton (docs/DESIGN_SYSTEM.md
§4, §15). The dialog lists lines and problems read-only.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import QDialog, QFrame, QLabel, QPlainTextEdit

from trigger_designer.qt.widgets.common.config_widgets import (
    STRIP_H,
    IconButton,
    TextButton,
)
from trigger_designer.qt.widgets.external_edit_banner import (
    ExternalChangeDialog,
    ExternalEditBanner,
)

try:
    from trigger_designer.core.authoring.external_edit import ExternalChange
except ImportError:  # the analysis module is written separately
    ExternalChange = None

pytestmark = pytest.mark.ui

SUMMARY = "Changed outside Trigger Designer: 2 nodes added, 1 node changed"
LINES = ("+ node 4 Filter", "~ node 2 Select")
REVIEW = "Review changes"
RELOAD = "Reload from disk"
KEEP = "Keep my version, ignore this change"
REVIEWED = "Mark all as reviewed"


def _change(**fields: Any) -> Any:
    """A hand-built change: the real dataclass when it is importable."""
    values: dict[str, Any] = {
        "status": "changed",
        "sha256": "0" * 64,
        "data": None,
        "diff": None,
        "summary": SUMMARY,
        "lines": LINES,
        "problems": (),
        "touched": {4: "added", 2: "changed"},
        "removed": (),
    }
    values.update(fields)
    if ExternalChange is not None:
        return ExternalChange(**values)
    return SimpleNamespace(**values)


@pytest.fixture
def banner(qtbot) -> ExternalEditBanner:
    widget = ExternalEditBanner()
    qtbot.addWidget(widget)
    return widget


def _button(banner: ExternalEditBanner, name: str) -> IconButton:
    for button in banner.findChildren(IconButton):
        if button.accessibleName() == name:
            return button
    raise AssertionError(f"no action named {name!r}")


def _shown_actions(banner: ExternalEditBanner) -> set[str]:
    return {
        button.accessibleName()
        for button in banner.findChildren(IconButton)
        if not button.isHidden()
    }


def _message(banner: ExternalEditBanner) -> str:
    return banner.findChild(QLabel, "ExternalEditMessage").text()


def _tone(banner: ExternalEditBanner) -> str:
    return banner.property("tone")


# -- the frame -----------------------------------------------------------------


def test_the_banner_is_a_styled_strip_one_row_high(banner) -> None:
    assert isinstance(banner, QFrame)
    assert banner.objectName() == "ExternalEditBanner"
    assert banner.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert banner.minimumHeight() == STRIP_H
    assert banner.maximumHeight() == STRIP_H


def test_the_banner_starts_hidden(banner) -> None:
    assert banner.mode == "hidden"
    assert banner.isHidden()


# -- modes ---------------------------------------------------------------------


def test_pending_change_offers_review_reload_and_keep(banner) -> None:
    banner.show_change(_change(), unsaved=False)
    assert banner.mode == "pending"
    assert not banner.isHidden()
    assert _message(banner) == SUMMARY
    assert _tone(banner) == "info"
    assert _shown_actions(banner) == {REVIEW, RELOAD, KEEP}


def test_pending_change_without_lines_has_no_review_action(banner) -> None:
    banner.show_change(_change(lines=()), unsaved=False)
    assert _shown_actions(banner) == {RELOAD, KEEP}


def test_unsaved_changes_are_named_and_use_the_warning_tone(banner) -> None:
    banner.show_change(_change(), unsaved=True)
    assert _message(banner) == (
        f"{SUMMARY}. You also have unsaved changes; you can undo the reload."
    )
    assert _tone(banner) == "warning"
    assert _shown_actions(banner) == {REVIEW, RELOAD, KEEP}


@pytest.mark.parametrize(
    ("count", "removed", "message"),
    [
        (1, 0, "1 node changed by an external tool"),
        (3, 0, "3 nodes changed by an external tool"),
        (2, 1, "2 nodes changed by an external tool, 1 removed"),
    ],
)
def test_applied_message_uses_the_right_plural(banner, count, removed, message) -> None:
    banner.show_applied(count, removed=removed)
    assert banner.mode == "applied"
    assert _message(banner) == message
    assert _tone(banner) == "info"


def test_applied_mode_offers_review_and_mark_reviewed(banner) -> None:
    banner.show_applied(3)
    assert _shown_actions(banner) == {REVIEW, REVIEWED}


def test_invalid_mode_offers_only_keep(banner) -> None:
    banner.show_invalid("The external file is not valid JSON.")
    assert banner.mode == "invalid"
    assert not banner.isHidden()
    assert _message(banner) == "The external file is not valid JSON."
    assert _tone(banner) == "warning"
    assert _shown_actions(banner) == {KEEP}


def test_clear_hides_the_banner_and_every_action(banner) -> None:
    banner.show_applied(1)
    banner.clear()
    assert banner.mode == "hidden"
    assert banner.isHidden()
    assert _shown_actions(banner) == set()


# -- the labels ----------------------------------------------------------------


def test_the_message_tooltip_carries_the_full_text(banner) -> None:
    banner.show_change(_change(), unsaved=False)
    label = banner.findChild(QLabel, "ExternalEditMessage")
    assert label.toolTip() == SUMMARY


def test_the_status_icon_has_a_glyph(banner) -> None:
    icon = banner.findChild(QLabel, "ExternalEditIcon")
    assert icon.pixmap() is not None
    assert not icon.pixmap().isNull()


# -- actions -------------------------------------------------------------------


def test_every_action_is_a_named_text_free_icon_button(banner) -> None:
    buttons = banner.findChildren(IconButton)
    assert len(buttons) == 4
    for button in buttons:
        assert button.objectName() == "IconButton"
        assert button.text() == ""
        assert button.size() == QSize(30, 30)
        assert button.toolTip()
        assert button.accessibleName() == button.toolTip()
        assert not button.toolTip().endswith(".")
        assert not button.icon().isNull()


def test_each_action_emits_its_own_signal(banner, qtbot) -> None:
    banner.show_change(_change(), unsaved=True)
    with qtbot.waitSignal(banner.reviewRequested):
        _button(banner, REVIEW).click()
    with qtbot.waitSignal(banner.reloadRequested):
        _button(banner, RELOAD).click()
    with qtbot.waitSignal(banner.keepRequested):
        _button(banner, KEEP).click()
    banner.show_applied(2)
    with qtbot.waitSignal(banner.reviewedRequested):
        _button(banner, REVIEWED).click()


def test_apply_theme_keeps_every_glyph(banner) -> None:
    banner.show_change(_change(), unsaved=False)
    banner.apply_theme()
    assert not banner.findChild(QLabel, "ExternalEditIcon").pixmap().isNull()
    for button in banner.findChildren(IconButton):
        assert not button.icon().isNull()


# -- the review dialog ---------------------------------------------------------


def test_dialog_lists_the_lines_read_only(qtbot) -> None:
    dialog = ExternalChangeDialog(LINES)
    qtbot.addWidget(dialog)
    text = dialog.findChild(QPlainTextEdit, "ExternalChangeText")
    assert text.isReadOnly()
    assert text.toPlainText() == "\n".join(LINES)
    assert dialog.objectName() == "ExternalChangeDialog"
    assert dialog.windowTitle() == "Changes made outside Trigger Designer"
    assert dialog.minimumWidth() >= 560
    assert dialog.minimumHeight() >= 360


def test_dialog_without_lines_says_there_are_no_node_changes(qtbot) -> None:
    dialog = ExternalChangeDialog([])
    qtbot.addWidget(dialog)
    text = dialog.findChild(QPlainTextEdit, "ExternalChangeText")
    assert text.toPlainText() == "(no node changes)"


def test_for_change_shows_problems_when_there_are_no_lines(qtbot) -> None:
    change = _change(lines=(), problems=("Line 3: unknown op",), status="invalid")
    dialog = ExternalChangeDialog.for_change(change)
    qtbot.addWidget(dialog)
    text = dialog.findChild(QPlainTextEdit, "ExternalChangeText")
    assert text.toPlainText() == "Line 3: unknown op"


def test_for_change_puts_problems_after_the_lines(qtbot) -> None:
    dialog = ExternalChangeDialog.for_change(_change(problems=("Node 9 has no op",)))
    qtbot.addWidget(dialog)
    text = dialog.findChild(QPlainTextEdit, "ExternalChangeText")
    assert text.toPlainText() == "\n".join(
        [*LINES, "", "Problems:", "Node 9 has no op"]
    )


def test_for_change_with_nothing_to_show_says_so(qtbot) -> None:
    dialog = ExternalChangeDialog.for_change(
        _change(lines=(), problems=(), status="metadata_only")
    )
    qtbot.addWidget(dialog)
    text = dialog.findChild(QPlainTextEdit, "ExternalChangeText")
    assert text.toPlainText() == "(no node changes)"


def test_close_is_the_only_text_button_and_accepts_the_dialog(qtbot) -> None:
    dialog = ExternalChangeDialog(LINES)
    qtbot.addWidget(dialog)
    buttons = dialog.findChildren(TextButton)
    assert [button.text() for button in buttons] == ["Close"]
    buttons[0].click()
    assert dialog.result() == int(QDialog.DialogCode.Accepted)
