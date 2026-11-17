"""An external rewrite of an open ``.tds`` is one "External Edit" undo step (AI plan, phase 4)."""

from __future__ import annotations

import json

import pytest

from trigger_designer.core.authoring import Editor, new_workflow
from trigger_designer.core.headless.params import dump_workflow
from trigger_designer.qt.headless import make_window

pytestmark = pytest.mark.e2e


@pytest.fixture
def window():
    win = make_window()
    yield win
    win.deleteLater()


def _saved_node(window, node_id: int) -> dict:
    data = json.loads(json.dumps(window.scene.serialize(), default=str))
    return next(node for node in data["nodes"] if node["id"] == node_id)


def _open(window, tmp_path, nodes: int):
    """Load a workflow of ``nodes`` nodes and make that load the undo baseline."""
    editor = Editor(new_workflow(), base_dir=str(tmp_path))
    for _ in range(nodes):
        editor.add_node("preparation.sort")
    path = tmp_path / "flow.tds"
    path.write_bytes(dump_workflow(editor.data))
    window.scene.loadFromFile(str(path))
    history = window.scene.history
    history.clear()
    history.storeInitialHistoryStamp()
    return path


def _external_version(tmp_path, path) -> dict:
    """The file as an outside tool would rewrite it: what is on disk, plus a node."""
    editor = Editor(json.loads(path.read_bytes()), base_dir=str(tmp_path))
    editor.add_node("preparation.sort")
    return editor.data


def test_disk_bytes_follow_the_load_and_the_save(window, tmp_path):
    path = _open(window, tmp_path, nodes=2)
    assert window.scene.disk_bytes == path.read_bytes()

    window.scene.saveToFile(str(path))

    assert window.scene.disk_bytes == path.read_bytes()


def test_an_external_rewrite_is_one_undo_step_named_external_edit(window, tmp_path):
    path = _open(window, tmp_path, nodes=2)
    history = window.scene.history
    steps = history.controller.count

    assert history.replace_scene(_external_version(tmp_path, path)) is True

    assert len(window.scene.nodes) == 3
    assert history.controller.count == steps + 1
    assert history.currentText() == "External Edit"

    history.undo()
    assert len(window.scene.nodes) == 2
    assert history.nextText() == "External Edit"

    history.redo()
    assert len(window.scene.nodes) == 3
    assert history.currentText() == "External Edit"


def test_undo_brings_back_an_unsaved_edit_made_before_the_rewrite(window, tmp_path):
    path = _open(window, tmp_path, nodes=2)
    history = window.scene.history
    node = window.scene.nodes[0]
    node_id = node.id
    node.grNode.setPos(555.0, 333.0)  # moved on screen, neither saved nor recorded
    moved = _saved_node(window, node_id)

    history.replace_scene(_external_version(tmp_path, path))
    replaced = _saved_node(window, node_id)
    assert (replaced["pos_x"], replaced["pos_y"]) != (moved["pos_x"], moved["pos_y"])

    history.undo()

    restored = _saved_node(window, node_id)
    assert (restored["pos_x"], restored["pos_y"]) == (moved["pos_x"], moved["pos_y"])


def test_an_edit_made_after_the_rewrite_is_its_own_step(window, tmp_path):
    path = _open(window, tmp_path, nodes=2)
    history = window.scene.history
    history.replace_scene(_external_version(tmp_path, path))

    window.scene.nodes[0].grNode.setPos(10.0, 20.0)
    history.storeHistory("Node Moved")
    assert history.currentText() == "Node Moved"

    history.undo()
    assert history.currentText() == "External Edit"
    assert len(window.scene.nodes) == 3


def test_a_rewrite_is_refused_while_a_restore_is_running(window, tmp_path):
    path = _open(window, tmp_path, nodes=2)
    history = window.scene.history
    steps = history.controller.count

    with history.restoring(is_undo=True):
        assert history.replace_scene(_external_version(tmp_path, path)) is False

    assert len(window.scene.nodes) == 2
    assert history.controller.count == steps
