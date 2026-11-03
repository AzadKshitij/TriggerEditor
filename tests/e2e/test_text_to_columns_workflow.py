"""Text to Columns end to end: File Input (CSV) -> node -> File Output.

The expected rows are worked out by hand from the input below, so a change in
the node's behaviour fails here rather than being re-frozen.
"""

from __future__ import annotations

import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.frames import read_frame
from tests.support.workflows import (
    executed_frame,
    nodes_titled,
    run_workflow_and_wait,
)
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e

CSV = 'id,acct\n1,1000-200-30-4\n2,7\n3," a - b "\n'


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


def _build(root, **settings):
    src = root / "accounts.csv"
    src.write_text(CSV, encoding="utf-8")
    out_dir = root / "out"
    out_dir.mkdir()
    out_path = out_dir / "split.csv"

    window = TriggerSubWindow()
    scene = window.scene
    file_input = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    node = get_class_from_opcode(
        PreparationNodes.TEXT_TO_COLUMNS, NodeTypes.PREPARATION
    )(scene)
    file_output = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)
    file_input.content.filePath = str(src)
    file_input.content.file_type = "csv"
    file_output.content.settings["filePath"] = str(out_path)
    file_output.content.settings["file_format"] = "csv"
    node.content.settings.update(settings)
    Edge(scene, file_input.outputs[0], node.inputs[0])
    Edge(scene, node.outputs[0], file_output.inputs[0])
    tds = root / "split.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, out_path


def _run(qtbot, tmp_path, **settings):
    tds, out_path = _build(tmp_path, **settings)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    assert len(window.execution_results) == len(window.getAllNodes())
    assert not any(node.isInvalid() for node in window.getAllNodes())
    return window, read_frame(out_path)


def test_columns_mode_workflow(qtbot, tmp_path, no_modal_dialogs) -> None:
    window, out = _run(qtbot, tmp_path, column="acct", pattern="-", max_splits=2)
    assert out.columns == ["id", "acct", "acct_1", "acct_2", "acct_3"]
    assert out.rows() == [
        (1, "1000-200-30-4", "1000", "200", "30-4"),
        (2, "7", "7", None, None),
        (3, " a - b ", "a", "b", None),
    ]
    (node,) = nodes_titled(window, "Text to Columns")
    assert executed_frame(window, node).columns == out.columns
    assert no_modal_dialogs["warnings"] == []


def test_rows_mode_workflow(qtbot, tmp_path) -> None:
    _window, out = _run(
        qtbot,
        tmp_path,
        column="acct",
        pattern="-",
        output="rows",
        max_splits=0,
        row_index_column="n",
        keep_original=False,
    )
    assert out.columns == ["id", "acct", "n"]
    assert out.rows() == [
        (1, "1000", 1),
        (1, "200", 2),
        (1, "30", 3),
        (1, "4", 4),
        (2, "7", 1),
        (3, "a", 1),
        (3, "b", 2),
    ]


def test_run_matches_live_sample(qtbot, tmp_path) -> None:
    window, out = _run(
        qtbot,
        tmp_path,
        column="acct",
        split_mode="regex",
        pattern=r"\s*-\s*",
        max_splits=1,
        names="head, tail",
        keep_original=False,
    )
    assert out.columns == ["id", "head", "tail"]
    (node,) = nodes_titled(window, "Text to Columns")
    live = node.value[0]["data"].collect()
    assert isinstance(live, pl.DataFrame)
    # The live preview reads ids as text; the CSV round trip re-infers integers.
    assert [tuple(map(str, row)) for row in live.rows()] == [
        tuple(map(str, row)) for row in out.rows()
    ]
    assert live.select("head", "tail").rows() == [
        ("1000", "200-30-4"),
        ("7", None),
        ("a", "b"),
    ]
