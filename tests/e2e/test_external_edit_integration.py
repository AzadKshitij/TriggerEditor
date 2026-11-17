"""An open workflow notices an outside rewrite and lets the user take it (AI plan, phase 4).

The window is driven through its own handlers (``_on_external_change`` and the
banner's actions) so no test waits on the operating system's file events; the
watcher's own timing is covered in ``tests/ui/test_external_edit_watcher.py``.
"""

from __future__ import annotations

import json

import pytest

from trigger_designer.core.authoring import Editor, new_workflow
from trigger_designer.core.headless.atomic import write_bytes_atomic
from trigger_designer.core.headless.params import dump_workflow
from trigger_designer.qt.headless import make_window

pytestmark = pytest.mark.e2e


@pytest.fixture
def window():
    win = make_window()
    yield win
    win.shutdown_external_edit()  # Windows cannot delete a watched folder
    win.deleteLater()


def _open(window, tmp_path, nodes: int = 2):
    """Load a workflow the way the app does after ``fileLoad`` succeeds."""
    editor = Editor(new_workflow(), base_dir=str(tmp_path))
    for _ in range(nodes):
        editor.add_node("preparation.sort")
    path = tmp_path / "flow.tds"
    path.write_bytes(dump_workflow(editor.data))
    window.scene.loadFromFile(str(path))
    window.filename = str(path)
    history = window.scene.history
    history.clear()
    history.storeInitialHistoryStamp()
    window.external_edit_retarget()
    return path


def _agent_adds_a_node(tmp_path, path) -> int:
    """What an outside tool does: rewrite the file atomically with one more node."""
    editor = Editor(json.loads(path.read_bytes()), base_dir=str(tmp_path))
    added = editor.add_node("preparation.sort", title="Added by the agent")
    write_bytes_atomic(str(path), dump_workflow(editor.data))
    return added["id"]


def _notice(window):
    """The watcher's report for the file as it is now, handed to the window."""
    change = window._external_watcher.check_now()
    assert change is not None
    window._on_external_change(change)
    return change


def test_the_watcher_follows_the_loaded_file(window, tmp_path):
    path = _open(window, tmp_path)
    watcher = window._external_watcher
    assert watcher.path is not None and watcher.path.endswith("flow.tds")
    assert watcher.baseline == path.read_bytes() == window.scene.disk_bytes
    assert window._external_banner.isHidden()


def test_an_outside_rewrite_shows_the_banner_with_what_changed(window, tmp_path):
    path = _open(window, tmp_path)
    _agent_adds_a_node(tmp_path, path)

    change = _notice(window)

    assert change.status == "changed"
    assert window._external_pending is change
    assert not window._external_banner.isHidden()
    assert window._external_banner.mode == "pending"
    assert len(window.scene.nodes) == 2  # nothing is applied until the user says so


def test_reload_takes_the_change_as_one_undo_step_and_marks_the_new_node(
    window, tmp_path
):
    path = _open(window, tmp_path)
    history = window.scene.history
    steps = history.controller.count
    new_id = _agent_adds_a_node(tmp_path, path)
    _notice(window)

    assert window.apply_external_edit() is True

    assert len(window.scene.nodes) == 3
    assert history.controller.count == steps + 1
    assert history.currentText() == "External Edit"
    node = window.scene.getNodeByID(new_id)
    assert node.grNode.external_cue == "added"
    assert window._external_banner.mode == "applied"
    assert window._external_pending is None
    assert window.scene.disk_bytes == path.read_bytes()
    assert window._external_watcher.baseline == path.read_bytes()

    history.undo()
    assert len(window.scene.nodes) == 2
    history.redo()
    assert len(window.scene.nodes) == 3
    assert window.scene.getNodeByID(new_id).grNode.external_cue == "added"


def test_reload_leaves_the_document_clean_when_nothing_was_unsaved(window, tmp_path):
    path = _open(window, tmp_path)
    window.scene.has_been_modified = False
    _agent_adds_a_node(tmp_path, path)
    _notice(window)

    window.apply_external_edit()

    assert window.scene.has_been_modified is False


def test_reload_keeps_the_document_dirty_when_there_were_unsaved_edits(
    window, tmp_path
):
    path = _open(window, tmp_path)
    window.scene.nodes[0].grNode.setPos(321.0, 123.0)
    window.scene.has_been_modified = True
    _agent_adds_a_node(tmp_path, path)
    _notice(window)
    assert window._external_banner.mode == "pending"

    window.apply_external_edit()

    assert window.scene.has_been_modified is True


def test_mark_reviewed_removes_every_cue_and_the_banner(window, tmp_path):
    path = _open(window, tmp_path)
    new_id = _agent_adds_a_node(tmp_path, path)
    _notice(window)
    window.apply_external_edit()

    window.mark_external_reviewed()

    assert window.scene.getNodeByID(new_id).grNode.external_cue == ""
    assert window._external_banner.isHidden()
    assert window._external_cues == {}


def test_keep_my_version_ignores_this_change_and_reports_it_only_once(window, tmp_path):
    path = _open(window, tmp_path)
    _agent_adds_a_node(tmp_path, path)
    _notice(window)

    window.keep_my_version()

    assert window._external_pending is None
    assert window._external_banner.isHidden()
    assert len(window.scene.nodes) == 2
    assert (
        window._external_watcher.check_now() is None
    )  # same bytes: not reported again


def test_saving_in_the_app_clears_a_pending_banner_and_moves_the_baseline(
    window, tmp_path
):
    path = _open(window, tmp_path)
    _agent_adds_a_node(tmp_path, path)
    _notice(window)

    window.scene.saveToFile(str(path))
    window.external_edit_after_save()

    assert window._external_pending is None
    assert window._external_banner.isHidden()
    assert window._external_watcher.baseline == window.scene.disk_bytes
    assert window._external_watcher.check_now() is None  # the app's own save


def test_reload_waits_while_a_run_is_in_flight(window, tmp_path):
    path = _open(window, tmp_path)
    _agent_adds_a_node(tmp_path, path)
    _notice(window)
    window._workflow_worker = object()  # a run is in flight
    try:
        assert window.apply_external_edit() is False
    finally:
        window._workflow_worker = None

    assert len(window.scene.nodes) == 2
    assert window._external_pending is not None
    assert window._external_banner.mode == "pending"


def test_an_unreadable_rewrite_shows_a_warning_and_applies_nothing(window, tmp_path):
    path = _open(window, tmp_path)
    path.write_bytes(b'{"nodes": [')  # half written
    change = window._external_watcher.check_now()
    assert change is not None and change.status == "invalid"

    window._on_external_change(change)

    assert window._external_banner.mode == "invalid"
    assert window._external_pending is None
    assert window.apply_external_edit() is False
    assert len(window.scene.nodes) == 2


def test_loading_another_file_forgets_the_old_change(window, tmp_path):
    path = _open(window, tmp_path)
    new_id = _agent_adds_a_node(tmp_path, path)
    _notice(window)
    window.apply_external_edit()
    assert window.scene.getNodeByID(new_id).grNode.external_cue == "added"

    other = tmp_path / "other.tds"
    editor = Editor(new_workflow(), base_dir=str(tmp_path))
    editor.add_node("preparation.sort")
    other.write_bytes(dump_workflow(editor.data))
    window.scene.loadFromFile(str(other))
    window.filename = str(other)
    window.external_edit_retarget()

    assert window._external_cues == {}
    assert window._external_banner.isHidden()
    assert window._external_watcher.path.endswith("other.tds")


def test_the_overlay_buttons_sit_below_the_banner_while_it_shows(window, tmp_path):
    path = _open(window, tmp_path)
    top = window.run_button.y()
    _agent_adds_a_node(tmp_path, path)
    _notice(window)

    assert window.run_button.y() == top + window._external_banner.height()

    window.keep_my_version()

    assert window.run_button.y() == top


def test_a_node_the_outside_tool_removed_leaves_no_stale_dock(window, tmp_path):
    path = _open(window, tmp_path, nodes=3)
    editor = Editor(json.loads(path.read_bytes()), base_dir=str(tmp_path))
    victim = editor.data["nodes"][-1]["id"]
    editor.remove_node(victim)
    write_bytes_atomic(str(path), dump_workflow(editor.data))
    change = _notice(window)
    assert [node["id"] for node in change.removed] == [victim]

    assert window.apply_external_edit() is True

    assert len(window.scene.nodes) == 2
    assert window.scene.getNodeByID(victim) is None
    assert victim not in window._external_cues


def test_the_headless_session_never_watches_its_throwaway_copy(tmp_path):
    """The command line loads a temporary copy of the workflow through the same
    window class. A watcher on that folder only warns on stderr when the copy
    is deleted, so a headless window must not start one."""
    from trigger_designer.qt.headless import HeadlessSession

    editor = Editor(new_workflow(), base_dir=str(tmp_path))
    editor.add_node("preparation.sort")
    path = tmp_path / "flow.tds"
    path.write_bytes(dump_workflow(editor.data))

    session = HeadlessSession()
    try:
        session.load(str(path), expect_nodes=1, expect_edges=0)
        assert session.window.external_edit_enabled is False
        assert session.window._external_watcher.path is None
    finally:
        session.close()
