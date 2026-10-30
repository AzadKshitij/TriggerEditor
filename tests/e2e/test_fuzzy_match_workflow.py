"""Fuzzy Match end to end: two File Inputs -> Fuzzy Match -> three File Outputs.

The vendor and supplier lists are the plan's worked example (docs/plan/07,
section 7.6); the expected rows are hand-computed Jaro-Winkler scores.
"""

from __future__ import annotations

import pytest
from nodeeditor.node_edge import Edge

from tests.support.frames import read_frame
from tests.support.workflows import nodes_titled, run_workflow_and_wait
from trigger_designer.core.node_configuration import (
    IONodes,
    JoinNodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


VENDORS = 'Vendor,id\nACME Corp.,1\n"Globex, Inc",2\nInitech LLC,3\nHooli,5\n'
SUPPLIERS = "Supplier,ref\nAcme Corporation,a\nGLOBEX INC.,b\nInitec,c\nPied Piper,e\n"


def _build(root, **settings):
    out_dir = root / "out"
    out_dir.mkdir()
    (root / "vendors.csv").write_text(VENDORS, encoding="utf-8")
    (root / "suppliers.csv").write_text(SUPPLIERS, encoding="utf-8")
    paths = {name: out_dir / f"{name}.csv" for name in ("matched", "left", "right")}

    window = TriggerSubWindow()
    scene = window.scene
    io = NodeTypes.IO
    left_in = get_class_from_opcode(IONodes.FILE_INPUT, io)(scene)
    right_in = get_class_from_opcode(IONodes.FILE_INPUT, io)(scene)
    fuzzy = get_class_from_opcode(JoinNodes.FUZZY_MATCH, NodeTypes.JOIN)(scene)
    outputs = [get_class_from_opcode(IONodes.FILE_OUTPUT, io)(scene) for _ in paths]

    for node, name in ((left_in, "vendors.csv"), (right_in, "suppliers.csv")):
        node.content.filePath = str(root / name)
        node.content.file_type = "csv"
    for output, path in zip(outputs, paths.values()):
        output.content.settings["filePath"] = str(path)
        output.content.settings["file_format"] = "csv"
    fuzzy.content.settings.update(
        {"left_column": "Vendor", "right_column": "Supplier", **settings}
    )

    Edge(scene, left_in.outputs[0], fuzzy.inputs[0])
    Edge(scene, right_in.outputs[0], fuzzy.inputs[1])
    for index, output in enumerate(outputs):
        Edge(scene, fuzzy.outputs[index], output.inputs[0])
    tds = root / "fuzzy.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, paths


def _run(qtbot, tmp_path, **settings):
    tds, paths = _build(tmp_path, **settings)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    assert len(window.execution_results) == len(window.getAllNodes())
    assert not any(node.isInvalid() for node in window.getAllNodes())
    return window, {name: read_frame(path) for name, path in paths.items()}


def test_fuzzy_match_workflow_writes_matched_and_unmatched(qtbot, tmp_path) -> None:
    window, frames = _run(qtbot, tmp_path)
    matched = frames["matched"]
    assert matched.columns == [
        "Match_ID",
        "Match_Score",
        "Vendor",
        "id",
        "Supplier",
        "ref",
    ]
    assert matched.rows() == [
        (1, 1.0, "ACME Corp.", 1, "Acme Corporation", "a"),
        (2, 1.0, "Globex, Inc", 2, "GLOBEX INC.", "b"),
        (3, 0.9714, "Initech LLC", 3, "Initec", "c"),
    ]
    assert frames["left"].rows() == [("Hooli", 5)]
    assert frames["right"].rows() == [("Pied Piper", "e")]
    assert len(nodes_titled(window, "Fuzzy Match")) == 1


def test_fuzzy_match_workflow_all_pairs_with_lower_threshold(qtbot, tmp_path) -> None:
    _window, frames = _run(
        qtbot, tmp_path, assignment="all_pairs", threshold=0.01, blocking="none"
    )
    pairs = frames["matched"].select("id", "ref").rows()
    # the three true pairs are there, each also paired with weaker candidates
    assert {(1, "a"), (2, "b"), (3, "c")} <= set(pairs)
    assert len(pairs) > 3
    assert frames["matched"]["Match_ID"].to_list() == list(range(1, len(pairs) + 1))
