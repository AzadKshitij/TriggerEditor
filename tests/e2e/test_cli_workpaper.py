"""The CLI with a Workpaper Output: ``--output-dir``, ``--param`` and ``paths``.

The workflow is built and saved by a real window in this process, then every
case runs the installed CLI in a subprocess against it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from nodeeditor.node_edge import Edge

from tests.support.audit_ledger import make_ledger
from tests.support.cli import events, run_cli
from tests.support.workpaper import find_label, load
from trigger_designer.core.node_configuration import (
    AuditNodes,
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


def _build(root: Path, **wp_settings):
    """ledger.csv -> Duplicates -> Workpaper Output (E), ledger.csv -> (P)."""
    source = root / "in" / "ledger.csv"
    source.parent.mkdir()
    make_ledger().frame.write_csv(source)
    original = root / "original"
    original.mkdir()
    window = TriggerSubWindow()
    scene = window.scene
    file_input = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    file_input.content.filePath = str(source)
    file_input.content.file_type = "csv"
    dups = get_class_from_opcode(AuditNodes.DUPLICATES, NodeTypes.AUDIT)(scene)
    dups.content.key_columns = ["vendor", "invoice_no", "amount"]
    wp = get_class_from_opcode(IONodes.WORKPAPER_OUTPUT, NodeTypes.IO)(scene)
    wp.content.settings.update(
        output_path=str(original / "wp.xlsx"),
        client="Acme Ltd",
        preparer="A. Auditor",
        prepared_date="2026-03-31",
        source_files=str(source),
        **wp_settings,
    )
    Edge(scene, file_input.outputs[0], dups.inputs[0])
    Edge(scene, dups.outputs[0], wp.inputs[0])
    Edge(scene, file_input.outputs[0], wp.inputs[1])
    Edge(scene, dups.outputs[2], wp.inputs[2])
    tds = root / "wp_flow.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, source, original


def _run(tds, tmp_path, *extra):
    return run_cli(
        "run",
        tds,
        "--allow-unapproved",
        "--log-format",
        "json",
        "--record-dir",
        tmp_path / "rec",
        *extra,
        cwd=tmp_path,
    )


def _finished(proc):
    return [e for e in events(proc) if e["event"] == "run.finished"][-1]


def _workflow_sheet_text(path) -> str:
    sheet = load(path)["Workflow"]
    return "\n".join(
        str(c.value) for row in sheet.iter_rows() for c in row if c.value is not None
    )


def test_output_dir_redirects_the_workpaper_and_the_record_fingerprints_it(
    qtbot, tmp_path
):
    tds, source, original = _build(tmp_path)
    target = tmp_path / "elsewhere"
    target.mkdir()
    proc = _run(tds, tmp_path, "--output-dir", target)
    assert proc.returncode == 0, proc.stderr[-2000:] + proc.stdout[-2000:]
    workbook = target / "wp.xlsx"
    assert workbook.exists()
    assert not (original / "wp.xlsx").exists()
    assert [p.name for p in target.iterdir()] == ["wp.xlsx"]  # no staging leftovers

    record = json.loads(Path(_finished(proc)["record_path"]).read_text("utf-8"))
    outputs = record["outputs"]
    assert any(
        Path(o["path"]).resolve() == workbook.resolve()
        and o.get("sha256")
        and o["role"] == "output"
        for o in outputs
    ), outputs

    sheet_text = _workflow_sheet_text(workbook)
    assert "staging" not in sheet_text.lower()
    assert "tdtmp" not in sheet_text
    assert find_label(load(workbook)["Summary"], "Client")


def test_a_second_run_does_not_overwrite_a_versioned_workpaper(qtbot, tmp_path):
    """if_exists=version means a rerun adds ``wp (2).xlsx`` (the CLI stages the write)."""
    tds, _source, _original = _build(tmp_path)
    target = tmp_path / "elsewhere"
    target.mkdir()
    for _ in range(2):
        proc = _run(tds, tmp_path, "--output-dir", target)
        assert proc.returncode == 0, proc.stderr[-2000:] + proc.stdout[-2000:]
    assert sorted(p.name for p in target.iterdir()) == ["wp (2).xlsx", "wp.xlsx"]


def test_the_full_exceptions_csv_lands_beside_the_final_workbook(qtbot, tmp_path):
    """A row-limited workpaper also writes ``<name>_exceptions_full.csv``: never a staging name."""
    tds, _source, _original = _build(tmp_path, row_limit=5)
    target = tmp_path / "elsewhere"
    target.mkdir()
    proc = _run(tds, tmp_path, "--output-dir", target)
    assert proc.returncode == 0, proc.stderr[-2000:] + proc.stdout[-2000:]
    assert sorted(p.name for p in target.iterdir()) == [
        "wp.xlsx",
        "wp_exceptions_full.csv",
    ]
    sheet = load(target / "wp.xlsx")["Exceptions"]
    text = " ".join(str(c.value) for row in sheet.iter_rows() for c in row if c.value)
    assert "wp_exceptions_full.csv" in text and "tdtmp" not in text


def test_param_and_relativize_work_for_the_workpaper_path(qtbot, tmp_path):
    tds, source, original = _build(tmp_path)
    added = run_cli(
        "params",
        "add",
        tds,
        "--name",
        "workpaper_file",
        "--node",
        "Workpaper Output",
        "--setting",
        "output_path",
        cwd=tmp_path,
    )
    assert added.returncode == 0, added.stderr
    chosen = tmp_path / "chosen" / "named_by_param.xlsx"
    chosen.parent.mkdir()
    proc = _run(tds, tmp_path, "--param", f"workpaper_file={chosen}")
    assert proc.returncode == 0, proc.stderr[-2000:] + proc.stdout[-2000:]
    assert chosen.exists() and not (original / "wp.xlsx").exists()

    # paths --relativize --write: the saved absolute paths become relative, and a
    # run from another folder still writes next to the workflow file.
    rel = run_cli("paths", tds, "--relativize", "--write", cwd=tmp_path)
    assert rel.returncode == 0, rel.stderr
    saved = tds.read_text(encoding="utf-8")
    assert str(original).replace("\\", "/") not in saved.replace("\\\\", "/")
    other = tmp_path / "other"
    again = run_cli(
        "run",
        tds,
        "--allow-unapproved",
        "--log-format",
        "json",
        "--record-dir",
        tmp_path / "rec",
        "--param",
        f"workpaper_file={chosen.with_name('second.xlsx')}",
        cwd=other,
    )
    assert again.returncode == 0, again.stderr[-1500:]
    assert chosen.with_name("second.xlsx").exists()


def test_workflow_sheet_never_shows_staging_names_and_follows_input_dir(
    qtbot, tmp_path
):
    """The sheet lists the ancestors of the workpaper (never an output node), so a
    staged output name cannot appear; an input moved with --input-dir shows the path
    that was actually read."""
    tds, source, _original = _build(tmp_path)
    moved = tmp_path / "moved"
    moved.mkdir()
    (moved / "ledger.csv").write_bytes(source.read_bytes())
    target = tmp_path / "elsewhere"
    target.mkdir()
    proc = _run(tds, tmp_path, "--output-dir", target, "--input-dir", moved)
    assert proc.returncode == 0, proc.stderr[-2000:] + proc.stdout[-2000:]
    text = _workflow_sheet_text(target / "wp.xlsx")
    assert "tdtmp" not in text and "staging" not in text.lower()
    assert (moved / "ledger.csv").as_posix() in text
    sources = load(target / "wp.xlsx")["Summary"]
    listed = " ".join(
        str(c.value) for row in sources.iter_rows() for c in row if c.value
    )
    assert "moved" in listed  # source_files followed --input-dir too


def _sheet_cells(path, name) -> list[str]:
    sheet = load(path)[name]
    return [
        str(c.value) for row in sheet.iter_rows() for c in row if c.value is not None
    ]


def test_cli_workpaper_has_a_run_log_sheet_with_the_steps_and_durations(
    qtbot, tmp_path
):
    tds, _source, original = _build(tmp_path)
    proc = _run(tds, tmp_path)
    assert proc.returncode == 0, proc.stderr[-2000:] + proc.stdout[-2000:]
    workbook = original / "wp.xlsx"
    book = load(workbook)
    assert "Run log" in book.sheetnames
    cells = _sheet_cells(workbook, "Run log")
    text = " ".join(cells)
    assert "Snapshot taken while the workflow was running" in text
    assert "File Input" in cells and "Duplicates" in cells
    sheet = book["Run log"]
    header = next(
        row for row in sheet.iter_rows() if any(c.value == "Duration (s)" for c in row)
    )
    col = next(c.column for c in header if c.value == "Duration (s)")
    durations = [
        sheet.cell(r, col).value
        for r in range(header[0].row + 1, sheet.max_row + 1)
        if sheet.cell(r, 2).value in ("File Input", "Duplicates")
    ]
    assert len(durations) == 2
    assert all(isinstance(d, (int, float)) and d >= 0 for d in durations), durations
    summary = " ".join(_sheet_cells(workbook, "Summary"))
    assert "no run record is available" not in summary


def test_cli_no_record_leaves_the_run_log_out_with_the_reason(qtbot, tmp_path):
    tds, _source, original = _build(tmp_path)
    proc = _run(tds, tmp_path, "--no-record")
    assert proc.returncode == 0, proc.stderr[-2000:] + proc.stdout[-2000:]
    workbook = original / "wp.xlsx"
    assert "Run log" not in load(workbook).sheetnames
    summary = " ".join(_sheet_cells(workbook, "Summary"))
    assert "run recording is off" in summary
