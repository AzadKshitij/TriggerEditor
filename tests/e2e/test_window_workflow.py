"""Window end to end: File Input (CSV) -> node -> File Output.

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
    TransformNodes,
    get_class_from_opcode,
)
from trigger_designer.core.shaping.common import LIVE_SAMPLE_ROWS
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e

CSV = "acct,d,v\nA,3,10\nA,1,\nB,1,5\nA,2,7\nB,2,8\nB,3,9\n"
OPS = [
    {"op": "lag", "source": "v"},
    {"op": "cum_sum", "source": "v"},
    {"op": "rank", "source": "v", "descending": True},
]


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


def _build(root, csv_text: str, **settings):
    src = root / "ledger.csv"
    src.write_text(csv_text, encoding="utf-8")
    out_dir = root / "out"
    out_dir.mkdir()
    out_path = out_dir / "window.csv"

    window = TriggerSubWindow()
    scene = window.scene
    file_input = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    node = get_class_from_opcode(TransformNodes.WINDOW, NodeTypes.TRANSFORM)(scene)
    file_output = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)
    file_input.content.filePath = str(src)
    file_input.content.file_type = "csv"
    file_output.content.settings["filePath"] = str(out_path)
    file_output.content.settings["file_format"] = "csv"
    node.content.settings.update(settings)
    Edge(scene, file_input.outputs[0], node.inputs[0])
    Edge(scene, node.outputs[0], file_output.inputs[0])
    tds = root / "window.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, out_path


def _run(qtbot, tmp_path, csv_text: str = CSV, **settings):
    tds, out_path = _build(tmp_path, csv_text, **settings)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    assert len(window.execution_results) == len(window.getAllNodes())
    assert not any(node.isInvalid() for node in window.getAllNodes())
    return window, read_frame(out_path)


def test_window_workflow_keeps_input_order_and_computes_per_account(
    qtbot, tmp_path, no_modal_dialogs
) -> None:
    window, out = _run(
        qtbot,
        tmp_path,
        partition_by=["acct"],
        order_by=[{"column": "d", "descending": False}],
        ops=OPS,
    )
    assert out.columns == ["acct", "d", "v", "v_lag1", "v_cum_sum", "v_rank"]
    assert out.rows() == [
        ("A", 3, 10, 7, 17.0, 1),
        ("A", 1, None, None, None, None),
        ("B", 1, 5, None, 5.0, 3),
        ("A", 2, 7, None, 7.0, 2),
        ("B", 2, 8, 5, 13.0, 2),
        ("B", 3, 9, 8, 22.0, 1),
    ]
    (node,) = nodes_titled(window, "Window")
    assert executed_frame(window, node).columns == out.columns
    assert no_modal_dialogs["warnings"] == []


def test_row_number_and_rolling_sum_without_partition(qtbot, tmp_path) -> None:
    _window, out = _run(
        qtbot,
        tmp_path,
        order_by=[{"column": "d", "descending": True}],
        ops=[
            {"op": "row_number", "name": "n"},
            {"op": "rolling_sum", "source": "d", "name": "r", "window": 2},
        ],
    )
    # d = [3,1,1,2,2,3]; high to low, ties by position: rows 0,5,3,4,1,2
    assert out["n"].to_list() == [1, 5, 6, 3, 4, 2]
    # window order d: 3,3,2,2,1,1 -> strict rolling(2) sums: null,6,5,4,3,2
    assert out["r"].to_list() == [None, 3.0, 2.0, 5.0, 4.0, 6.0]


def test_run_reads_every_row_while_live_reads_the_sample(qtbot, tmp_path) -> None:
    total = LIVE_SAMPLE_ROWS * 2 + 50
    text = "g,x\n" + "".join(f"a,{1}\n" for _ in range(total))
    window, out = _run(
        qtbot,
        tmp_path,
        text,
        ops=[{"op": "cum_sum", "source": "x", "name": "cs"}],
    )
    assert out.height == total
    assert out["cs"].to_list()[-1] == float(total)
    (node,) = nodes_titled(window, "Window")
    live = node.value[0]["data"].collect()
    assert isinstance(live, pl.DataFrame)
    assert live.height == LIVE_SAMPLE_ROWS
    assert live["cs"].to_list() == out["cs"].to_list()[:LIVE_SAMPLE_ROWS]
