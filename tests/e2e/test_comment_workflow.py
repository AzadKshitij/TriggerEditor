"""Canvas comments end to end: saved with a workflow, kept through a run, migrated."""

from __future__ import annotations

import json

import orjson
import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.workflows import run_workflow_and_wait
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.core.shaping.comments import (
    LEGACY_COMMENT_OP,
    comments_from_scene_dict,
)
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e

CSV = "acct,amt\nA,10\nB,20\n"
NOTE = "Check cut-off\nSecond line"


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


def _build(root, *, with_note: bool = True):
    source = root / "in.csv"
    source.write_text(CSV, encoding="utf-8", newline="")
    out_dir = root / "out"
    out_dir.mkdir()
    target = out_dir / "out.csv"

    window = TriggerSubWindow()
    scene = window.scene
    file_input = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    record_id = get_class_from_opcode(
        PreparationNodes.RECORD_ID, NodeTypes.PREPARATION
    )(scene)
    output = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)

    file_input.content.filePath = str(source)
    file_input.content.file_type = "csv"
    output.content.settings["filePath"] = str(target)
    output.content.settings["file_format"] = "csv"
    if with_note:
        scene.addComment(NOTE, x=0, y=-200)

    Edge(scene, file_input.outputs[0], record_id.inputs[0])
    Edge(scene, record_id.outputs[0], output.inputs[0])
    tds = root / "comment.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, target


def test_canvas_comment_is_saved_kept_and_not_run(qtbot, tmp_path) -> None:
    tds, target = _build(tmp_path)

    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    assert not [node for node in window.getAllNodes() if node.title == "Comment"]
    (note,) = window.scene.comments
    assert note.text() == NOTE

    run_workflow_and_wait(qtbot, window)

    # Only the data nodes ran; the note is not a node and has no result.
    assert len(window.execution_results) == len(window.getAllNodes())
    out = pl.read_csv(target)
    assert out["amt"].to_list() == [10, 20]

    saved = orjson.loads(tds.read_bytes())
    assert all(node["op"] != LEGACY_COMMENT_OP for node in saved["nodes"])
    (record,) = comments_from_scene_dict(saved)
    assert record.text == NOTE
    assert record.y == -200.0


def test_legacy_comment_node_loads_as_a_canvas_comment(qtbot, tmp_path) -> None:
    tds, target = _build(tmp_path, with_note=False)
    saved = json.loads(tds.read_text(encoding="utf-8"))
    saved["nodes"].append(
        {
            "id": max(node["id"] for node in saved["nodes"]) + 1,
            "title": "Comment",
            "pos_x": 0.0,
            "pos_y": -200.0,
            "inputs": [],
            "outputs": [],
            "content": {"settings": {"text": NOTE}},
            "label_text": "Check cut-off",
            "label_visible": True,
            "label_offset": 10.0,
            "node_code": 3,
            "node_type": "report",
            "op": LEGACY_COMMENT_OP,
        }
    )
    legacy = tmp_path / "legacy.tds"
    legacy.write_text(json.dumps(saved), encoding="utf-8")

    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(legacy)) is True
    assert not [node for node in window.getAllNodes() if node.title == "Comment"]
    (note,) = window.scene.comments
    assert note.text() == NOTE
    assert note.pos().y() == -200.0

    run_workflow_and_wait(qtbot, window)
    assert len(window.execution_results) == len(window.getAllNodes())
    out = pl.read_csv(target)
    assert out.columns == ["RecordID", "acct", "amt"]
    assert out["amt"].to_list() == [10, 20]

    window.scene.saveToFile(str(legacy))
    resaved = orjson.loads(legacy.read_bytes())
    assert all(node["op"] != LEGACY_COMMENT_OP for node in resaved["nodes"])
    assert [c["text"] for c in resaved["comments"]] == [NOTE]
