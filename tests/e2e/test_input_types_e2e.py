"""End-to-end runs for the new File Input source types."""

from __future__ import annotations

import shutil

import orjson
import pytest
from nodeeditor.node_edge import Edge

from tests.support.frames import assert_frame_golden, read_frame
from tests.support.input_fixtures import (
    duckdb_db,
    json_files,
    monthly_csvs,
    multi_sheet_xlsx,
    parquet_files,
    sqlite_db,
    write_text,
)
from tests.support.workflows import run_workflow_and_wait
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


def _build_workflow(
    root,
    name: str,
    source,
    file_type: str,
    *,
    extra: dict | None = None,
    out_name: str = "out.csv",
):
    out_dir = root / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / out_name
    window = TriggerSubWindow()
    scene = window.scene
    file_input = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    file_output = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)

    content = file_input.content
    content.filePath = str(source)
    content.file_type = file_type
    for key, value in (extra or {}).items():
        setattr(content, key, value)
    file_output.content.filePath = str(out_path)
    file_output.content.file_format = "csv"

    Edge(scene, file_input.outputs[0], file_output.inputs[0])
    tds = root / f"{name}.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, out_path


def _open_and_run(qtbot, tds):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    return window


def _input_node(window):
    return next(node for node in window.getAllNodes() if node.title == "File Input")


def test_folder_union_matches_golden(qtbot, tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    tds, out = _build_workflow(
        tmp_path,
        "folder",
        monthly,
        "csv",
        extra={"output_filename_as_field": True},
    )
    window = _open_and_run(qtbot, tds)
    frame = read_frame(out)
    assert_frame_golden(frame, "input_folder_union")
    assert _input_node(window) in window.execution_results
    report = _input_node(window).content.last_report
    assert report is not None
    assert "sales_2024-03.csv" in {
        item.relative_path for item in report.differing_files()
    }


def test_glob_union_matches_golden(qtbot, tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    pattern = str(monthly / "sales_2024-0[12].csv")
    tds, out = _build_workflow(
        tmp_path,
        "glob",
        pattern,
        "csv",
        extra={
            "output_filename_as_field": True,
            "file_name_column_name": "Source",
        },
        out_name="glob.csv",
    )
    window = _open_and_run(qtbot, tds)
    assert_frame_golden(read_frame(out), "input_glob_union")
    assert _input_node(window) in window.execution_results


def test_parquet_folder_matches_golden(qtbot, tmp_path) -> None:
    directory = parquet_files(tmp_path)
    tds, out = _build_workflow(
        tmp_path,
        "parquet",
        directory,
        "parquet",
        extra={"output_filename_as_field": True},
        out_name="parquet.csv",
    )
    window = _open_and_run(qtbot, tds)
    assert_frame_golden(read_frame(out), "input_parquet_folder")
    assert _input_node(window) in window.execution_results


def test_ndjson_matches_golden(qtbot, tmp_path) -> None:
    _array, ndjson = json_files(tmp_path)
    tds, out = _build_workflow(
        tmp_path, "ndjson", ndjson, "ndjson", out_name="ndjson.csv"
    )
    window = _open_and_run(qtbot, tds)
    assert_frame_golden(read_frame(out), "input_json_ndjson")
    assert _input_node(window) in window.execution_results


def test_json_array_nested_text_matches_golden(qtbot, tmp_path) -> None:
    array, _ndjson = json_files(tmp_path)
    tds, out = _build_workflow(
        tmp_path,
        "json",
        array,
        "json",
        extra={"json_nested": "text"},
        out_name="json.csv",
    )
    window = _open_and_run(qtbot, tds)
    assert_frame_golden(read_frame(out), "input_json_array_text")
    assert _input_node(window) in window.execution_results


def test_sqlite_query_matches_golden(qtbot, tmp_path) -> None:
    database = sqlite_db(tmp_path)
    tds, out = _build_workflow(
        tmp_path,
        "sqlite",
        database,
        "sqlite",
        extra={
            "db_mode": "query",
            "db_query": (
                "SELECT region, SUM(amount) AS total FROM sales "
                "GROUP BY region ORDER BY region"
            ),
        },
        out_name="sqlite.csv",
    )
    window = _open_and_run(qtbot, tds)
    assert_frame_golden(read_frame(out), "input_sqlite_query")
    assert _input_node(window) in window.execution_results


def test_duckdb_table_matches_golden(qtbot, tmp_path) -> None:
    database = duckdb_db(tmp_path)
    tds, out = _build_workflow(
        tmp_path,
        "duckdb",
        database,
        "duckdb",
        extra={"db_mode": "table", "db_table": "sales"},
        out_name="duckdb.csv",
    )
    window = _open_and_run(qtbot, tds)
    assert_frame_golden(read_frame(out), "input_duckdb_table")
    assert _input_node(window) in window.execution_results


def test_duckdb_table_mode_defaults_table_at_run(qtbot, tmp_path) -> None:
    """The reported failure: table mode without a chosen table must still run."""
    database = duckdb_db(tmp_path)
    tds, out = _build_workflow(
        tmp_path,
        "duckdb-default",
        database,
        "duckdb",
        extra={"db_mode": "table"},
        out_name="duckdb-default.csv",
    )
    window = _open_and_run(qtbot, tds)
    assert_frame_golden(read_frame(out), "input_duckdb_table")
    assert _input_node(window).content.db_table == "sales"


def test_excel_all_sheets_matches_golden(qtbot, tmp_path) -> None:
    book = multi_sheet_xlsx(tmp_path)
    tds, out = _build_workflow(
        tmp_path,
        "excel",
        book,
        "excel",
        extra={"sheet_mode": "all", "add_sheet_name_column": True},
        out_name="excel.csv",
    )
    window = _open_and_run(qtbot, tds)
    assert_frame_golden(read_frame(out), "input_excel_all_sheets")
    assert _input_node(window) in window.execution_results


def test_workflow_moved_with_data_still_runs(qtbot, tmp_path) -> None:
    project = tmp_path / "project"
    monthly = monthly_csvs(project / "data")
    _tds, _out = _build_workflow(
        project,
        "wf",
        monthly,
        "csv",
        extra={"output_filename_as_field": True},
    )
    moved = tmp_path / "moved"
    shutil.copytree(project, moved)
    shutil.rmtree(project)

    # File Output paths are still absolute (plan 01 only makes inputs
    # relative). Repoint the output so this test isolates input resolution.
    moved_tds = moved / "wf.tds"
    data = orjson.loads(moved_tds.read_bytes())
    for node in data["nodes"]:
        if node.get("op") == "input.file_output":
            node["content"]["filePath"] = str(moved / "out" / "out.csv")
    moved_tds.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
    window = _open_and_run(qtbot, moved_tds)
    frame = read_frame(moved / "out" / "out.csv")
    assert_frame_golden(frame, "input_folder_union")
    assert _input_node(window) in window.execution_results


def test_absolute_fallback_when_relative_missing(qtbot, tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    tds, out = _build_workflow(
        tmp_path,
        "fallback",
        monthly,
        "csv",
        extra={"output_filename_as_field": True},
        out_name="fallback.csv",
    )
    data = orjson.loads(tds.read_bytes())
    for node in data["nodes"]:
        if node.get("op") == "input.file_input":
            node["content"]["filePathRel"] = "gone/missing.csv"
    tds.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

    window = _open_and_run(qtbot, tds)
    assert_frame_golden(read_frame(out), "input_folder_union")
    assert _input_node(window) in window.execution_results


def test_folder_run_failure_names_file(qtbot, tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    write_text(monthly / "sales_2024-05.csv", "")
    tds, _out = _build_workflow(tmp_path, "bad", monthly, "csv")
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    input_node = _input_node(window)
    assert "sales_2024-05.csv" in str(input_node.content.last_error)

    run_workflow_and_wait(qtbot, window)
    assert input_node not in window.execution_results


def test_folder_skip_matches_golden(qtbot, tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    write_text(monthly / "sales_2024-05.csv", "")
    tds, out = _build_workflow(
        tmp_path,
        "skip",
        monthly,
        "csv",
        extra={
            "output_filename_as_field": True,
            "on_file_error": "skip",
        },
        out_name="skip.csv",
    )
    window = _open_and_run(qtbot, tds)
    assert_frame_golden(read_frame(out), "input_folder_union")
    assert _input_node(window).content.last_report.skipped_count == 1


def test_missing_folder_negative(qtbot, tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    tds, _out = _build_workflow(
        tmp_path,
        "missing",
        monthly,
        "csv",
        extra={"file_name_column_name": "Source"},
    )
    shutil.rmtree(monthly)

    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    messages = window.validateLoadedWorkflow()
    assert any(str(monthly) in message for message in messages)
    input_node = _input_node(window)
    assert input_node.content.last_error is not None
    assert "NameError" not in str(input_node.content.last_error)

    run_workflow_and_wait(qtbot, window)
    assert input_node not in window.execution_results


def test_strict_mode_run_fails_with_column(qtbot, tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    tds, _out = _build_workflow(
        tmp_path,
        "strict",
        monthly,
        "csv",
        extra={"schema_mismatch": "error"},
    )
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    input_node = _input_node(window)
    assert input_node.content.last_error is not None
    assert "channel" in str(input_node.content.last_error)

    run_workflow_and_wait(qtbot, window)
    assert input_node not in window.execution_results
