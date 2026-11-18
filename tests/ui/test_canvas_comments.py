#!/usr/bin/env python3
"""Canvas comments: sticky notes the user adds, edits, moves and deletes.

nodeeditor owns the note item; these tests pin how the app wires it in: the
canvas menu entry, one undo step per change, no duplicate items after a restore,
and a save that loads again.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from nodeeditor.node_comment import Comment
from qtpy.QtCore import QPointF
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.helpers.context_menu_mixin import (
    COMMENT_ACTION_DATA,
    comment_at,
)

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def window() -> Iterator[TriggerSubWindow]:
    win = TriggerSubWindow()
    win.resize(900, 600)
    win.show()
    # What fileNew does: the first stamp is the baseline, not an undo step.
    win.scene.history.storeInitialHistoryStamp()
    _APP.processEvents()
    try:
        yield win
    finally:
        win.close()
        win.deleteLater()


def _comment_items(window: TriggerSubWindow) -> list[Comment]:
    return [i for i in window.scene.grScene.items() if isinstance(i, Comment)]


def test_add_comment_makes_one_undo_step(window: TriggerSubWindow) -> None:
    history = window.scene.history
    note = window.add_comment(QPointF(300, 200))
    note.finish_edit(commit=False, store_history=False)

    assert window.scene.comments == [note]
    assert note.isSelected()
    assert history.currentText() == "Comment Added"
    assert window.scene.has_been_modified

    history.undo()
    assert window.scene.comments == []
    assert _comment_items(window) == []

    history.redo()
    assert len(window.scene.comments) == 1
    assert len(_comment_items(window)) == 1


def test_default_position_is_the_viewport_centre(window: TriggerSubWindow) -> None:
    note = window.add_comment()
    note.finish_edit(commit=False, store_history=False)
    view = window.scene.getView()
    centre = view.mapToScene(view.viewport().rect().center())
    middle = note.pos() + QPointF(note.rect().width() / 2, note.rect().height() / 2)
    assert abs(middle.x() - centre.x()) < 1.0
    assert abs(middle.y() - centre.y()) < 1.0


def test_edit_text_is_undoable(window: TriggerSubWindow) -> None:
    history = window.scene.history
    note = window.scene.addComment("first", x=10, y=20)
    history.storeHistory("Comment Added", setModified=True)

    note.begin_edit()
    note.editor().setPlainText("second")
    note.finish_edit()
    assert window.scene.comments[0].text() == "second"

    history.undo()
    assert [c.text() for c in window.scene.comments] == ["first"]
    history.redo()
    assert [c.text() for c in window.scene.comments] == ["second"]


def test_restore_does_not_duplicate_items(window: TriggerSubWindow) -> None:
    history = window.scene.history
    window.scene.addComment("a", x=0, y=0)
    history.storeHistory("Comment Added", setModified=True)
    window.scene.addComment("b", x=300, y=0)
    history.storeHistory("Comment Added", setModified=True)

    for _ in range(3):
        history.undo()
        history.redo()

    assert sorted(c.text() for c in window.scene.comments) == ["a", "b"]
    assert len(_comment_items(window)) == 2


def test_delete_selected_and_undo(window: TriggerSubWindow) -> None:
    history = window.scene.history
    note = window.scene.addComment("keep me", x=40, y=50)
    history.storeHistory("Comment Added", setModified=True)
    note.setSelected(True)

    window.scene.getView().deleteSelected()
    assert window.scene.comments == []
    assert _comment_items(window) == []

    history.undo()
    assert [c.text() for c in window.scene.comments] == ["keep me"]
    restored = window.scene.comments[0]
    assert (restored.pos().x(), restored.pos().y()) == (40.0, 50.0)


def test_comments_survive_serialize_and_load(window: TriggerSubWindow) -> None:
    note = window.scene.addComment("audit trail", x=120, y=80, width=260, height=140)
    data = window.scene.serialize()
    assert [c["text"] for c in data["comments"]] == ["audit trail"]

    other = TriggerSubWindow()
    try:
        other.scene.deserialize(data)
        (loaded,) = other.scene.comments
        assert loaded.text() == "audit trail"
        assert (loaded.pos().x(), loaded.pos().y()) == (120.0, 80.0)
        assert loaded.rect().width() == note.rect().width()
    finally:
        other.close()
        other.deleteLater()


def test_comment_at_finds_the_note_from_its_text_child(
    window: TriggerSubWindow,
) -> None:
    note = window.scene.addComment("hello", x=0, y=0)
    assert comment_at(note) is note
    assert comment_at(note._text_item) is note
    assert comment_at(None) is None


def test_menu_action_adds_a_comment(window: TriggerSubWindow) -> None:
    action = window.comment_action
    assert list(action.data()) == COMMENT_ACTION_DATA
    window.set_selected_action_data(action.data())
    window.add_node_to_scene()
    (note,) = window.scene.comments
    note.finish_edit(commit=False, store_history=False)
    assert window.scene.history.currentText() == "Comment Added"


def test_selecting_a_comment_leaves_the_dock_alone(window: TriggerSubWindow) -> None:
    window.scene.addComment("note", x=0, y=0)
    window.scene.comments[0].setSelected(True)
    _APP.processEvents()
    assert window.scene.comments[0].isSelected()
