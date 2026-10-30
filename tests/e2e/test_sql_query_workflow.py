"""SQL Query end to end: File Input (CSV) x2 -> SQL Query -> File Output (CSV).

The workflow is saved, reopened and run through the real Run path. The second
test aims a file-reading query at a planted CSV: the run must write nothing and
the planted file must stay untouched.
"""

from __future__ import annotations

import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.frames import read_frame
from tests.support.workflows import nodes_titled, run_workflow_and_wait
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    TransformNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e

JOIN = "SELECT t1.a, t1.b, t2.c FROM t1 JOIN t2 USING (a) ORDER BY t1.a"


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


def _build(root, sql: str, *, second_input: bool):
    (root / "out").mkdir()
    t1 = root / "t1.csv"
    t1.write_text("a,b\n1,x\n2,y\n3,z\n")
    t2 = root / "t2.csv"
    t2.write_text("a,c\n2,20.0\n3,30.0\n4,40.0\n")
    result = root / "out" / "result.csv"

    window = TriggerSubWindow()
    scene = window.scene
    sources = []
    for path in (t1, t2)[: 2 if second_input else 1]:
        node = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
        node.content.filePath = str(path)
        node.content.file_type = "csv"
        sources.append(node)
    query = get_class_from_opcode(TransformNodes.SQL_QUERY, NodeTypes.TRANSFORM)(scene)
    query.content.settings["sql"] = sql
    output = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)
    output.content.settings["filePath"] = str(result)
    output.content.settings["file_format"] = "csv"

    for index, source in enumerate(sources):
        Edge(scene, source.outputs[0], query.inputs[index])
    Edge(scene, query.outputs[0], output.inputs[0])
    tds = root / "sql_query.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, result


def test_two_inputs_joined_by_sql_end_to_end(qtbot, tmp_path) -> None:
    tds, result = _build(tmp_path, JOIN, second_input=True)

    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    (query,) = nodes_titled(window, "SQL Query")
    assert query.content.settings["sql"] == JOIN
    assert not query.isInvalid()

    run_workflow_and_wait(qtbot, window)
    assert not any(node.isInvalid() for node in window.getAllNodes())

    frame = read_frame(result)
    assert frame.columns == ["a", "b", "c"]
    assert frame.rows() == [(2, "y", 20.0), (3, "z", 30.0)]


def test_single_input_text_columns_need_a_cast(qtbot, tmp_path) -> None:
    tds, result = _build(
        tmp_path,
        "SELECT a, upper(b) AS b FROM t1 WHERE try_cast(a AS INTEGER) >= 2",
        second_input=False,
    )
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    frame = read_frame(result)
    assert frame.rows() == [(2, "Y"), (3, "Z")]


def test_run_matches_live_preview(qtbot, tmp_path) -> None:
    tds, result = _build(tmp_path, JOIN, second_input=True)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    (query,) = nodes_titled(window, "SQL Query")
    live = query.value[0]["data"].collect()
    run_workflow_and_wait(qtbot, window)
    ran = pl.read_csv(result, infer_schema=False)
    assert ran.equals(live.cast(pl.String))


@pytest.mark.parametrize(
    "template",
    [
        "SELECT * FROM read_csv('{secret}')",
        "SELECT * FROM '{secret}'",
        "COPY (SELECT * FROM t1) TO '{dir}/stolen.csv'",
        "SELECT 1; COPY t1 TO '{dir}/stolen.csv'",
        "ATTACH '{dir}/new.db'",
    ],
)
def test_file_access_in_a_workflow_writes_and_reads_nothing(
    qtbot, tmp_path, no_modal_dialogs, template
) -> None:
    secret = tmp_path / "secret.csv"
    secret.write_text("password\nhunter2\n")
    sql = template.format(secret=secret.as_posix(), dir=tmp_path.as_posix())
    tds, result = _build(tmp_path, sql, second_input=False)

    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    (query,) = nodes_titled(window, "SQL Query")
    assert query.isInvalid()
    assert query.current_error.code.startswith("TD-SHAPE-11")

    window.executeWorkflow()
    if window._workflow_worker is not None:
        window._workflow_worker.wait(30_000)
    qtbot.wait(300)

    assert not result.exists()
    assert not (tmp_path / "stolen.csv").exists()
    assert not (tmp_path / "new.db").exists()
    assert secret.read_text() == "password\nhunter2\n"
    assert isinstance(pl.read_csv(secret), pl.DataFrame)
