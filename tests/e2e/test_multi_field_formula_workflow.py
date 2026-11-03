"""Multi-Field Formula end to end: File Input (CSV) -> node -> File Output (CSV)."""

from __future__ import annotations

import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.frames import read_frame
from tests.support.workflows import run_workflow_and_wait
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


CSV = "vendor,city,amount\n  acme ,paris,10\nBOLT, rome ,2.5\n,oslo,x\n"


def _build(root, **settings):
    source = root / "in.csv"
    source.write_text(CSV, encoding="utf-8")
    out_path = root / "out.csv"
    window = TriggerSubWindow()
    scene = window.scene
    file_input = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    node = get_class_from_opcode(
        PreparationNodes.MULTI_FIELD_FORMULA, NodeTypes.PREPARATION
    )(scene)
    file_output = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)
    file_input.content.filePath = str(source)
    file_input.content.file_type = "csv"
    file_output.content.settings["filePath"] = str(out_path)
    file_output.content.settings["file_format"] = "csv"
    node.content.settings.update(settings)
    Edge(scene, file_input.outputs[0], node.inputs[0])
    Edge(scene, node.outputs[0], file_output.inputs[0])
    tds = root / "mff.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, out_path


def _run(qtbot, root, **settings):
    tds, out_path = _build(root, **settings)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    assert not any(node.isInvalid() for node in window.getAllNodes())
    return window, read_frame(out_path)


def test_in_place_trim_and_upper(qtbot, tmp_path) -> None:
    _window, out = _run(
        qtbot,
        tmp_path,
        columns=["vendor", "city"],
        template="UPPER(TRIM({col}))",
    )
    assert out.columns == ["vendor", "city", "amount"]
    assert out["vendor"].to_list() == ["ACME", "BOLT", None]
    assert out["city"].to_list() == ["PARIS", "ROME", "OSLO"]
    assert out["amount"].cast(pl.String).to_list() == ["10", "2.5", "x"]


def test_suffix_mode_adds_columns(qtbot, tmp_path) -> None:
    _window, out = _run(
        qtbot,
        tmp_path,
        columns=["amount"],
        template="TRY_CAST({col} AS DOUBLE) * 2",
        mode="suffix",
        suffix="_x2",
    )
    assert out.columns == ["vendor", "city", "amount", "amount_x2"]
    assert out["amount_x2"].to_list() == [20.0, 5.0, None]


def test_hostile_template_fails_the_run_and_writes_nothing(qtbot, tmp_path) -> None:

    tds, out_path = _build(
        tmp_path,
        columns=["vendor"],
        template="{col}) FROM read_csv('in.csv') --",
    )
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    node = next(n for n in window.getAllNodes() if n.title == "Multi-Field Formula")
    node.markDirty(True)
    node.eval()
    assert node.isInvalid()
    assert not out_path.exists()
