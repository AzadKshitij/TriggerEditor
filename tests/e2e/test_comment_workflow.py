"""Comment end to end: File Input -> Record ID -> File Output, plus a Comment."""

from __future__ import annotations

import orjson
import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.workflows import nodes_titled, run_workflow_and_wait
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    PreparationNodes,
    ReportNodes,
    get_class_from_opcode,
)
from trigger_designer.core.shaping.comments import comments_from_scene_dict
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e

CSV = "acct,amt\nA,10\nB,20\n"


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


def _build(root):
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
    comment = get_class_from_opcode(ReportNodes.COMMENT, NodeTypes.REPORT)(scene)

    file_input.content.filePath = str(source)
    file_input.content.file_type = "csv"
    output.content.settings["filePath"] = str(target)
    output.content.settings["file_format"] = "csv"
    comment.content.set_setting("text", "Check cut-off\nSecond line", "Comment Text")
    comment.setPos(0, -200)

    Edge(scene, file_input.outputs[0], record_id.inputs[0])
    Edge(scene, record_id.outputs[0], output.inputs[0])
    tds = root / "comment.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, target


def test_comment_is_skipped_by_run_and_persisted(qtbot, tmp_path) -> None:
    tds, target = _build(tmp_path)

    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    (comment,) = nodes_titled(window, "Comment")
    assert comment.getNodeLabel() == "Check cut-off"

    run_workflow_and_wait(qtbot, window)

    # The no-op ran successfully and defined nothing.
    assert window.execution_results[comment] == {}
    assert len(window.execution_results) == len(window.getAllNodes())

    # The data path is untouched by the note.
    out = pl.read_csv(target)
    assert out.columns == ["RecordID", "acct", "amt"]
    assert out["RecordID"].to_list() == [1, 2]
    assert out["amt"].to_list() == [10, 20]

    saved = orjson.loads(tds.read_bytes())
    (record,) = comments_from_scene_dict(saved)
    assert record.text == "Check cut-off\nSecond line"
    assert record.y == -200.0
