"""Excel export needs xlsxwriter: declared, importable, and used by File Output."""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[2]


def test_xlsxwriter_importable() -> None:
    import xlsxwriter

    assert xlsxwriter.__version__.split(".")[0] == "3"


def test_pyproject_declares_xlsxwriter_and_cli_script() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'"xlsxwriter[=<>~]', text)
    assert 'trigger-designer-cli = "trigger_designer.cli:main"' in text


def test_cli_stub_importable() -> None:
    from trigger_designer.cli import main

    assert callable(main)


def test_file_output_excel_writes_readable_workbook(tmp_path) -> None:
    import fastexcel

    from trigger_designer.core.shaping.file_output import write_node

    out = tmp_path / "out.xlsx"
    frame = pl.LazyFrame({"a": [1, 2], "b": ["x", "y"]})
    write_node([frame], {"filePath": str(out), "file_format": "excel"})
    rows = fastexcel.read_excel(str(out)).load_sheet(0).to_polars()
    assert rows.to_dicts() == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]


def test_viewer_export_failure_shows_warning(qtbot, monkeypatch, tmp_path) -> None:
    from qtpy.QtWidgets import QFileDialog, QMessageBox

    from trigger_designer.qt.models.polars_table_viewer import PolarsTableViewer

    viewer = PolarsTableViewer()
    qtbot.addWidget(viewer)
    df = pl.DataFrame({"a": [1]})
    viewer.dataframe = df
    viewer.filtered_dataframe = None
    target = tmp_path / "x.xlsx"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), "")
    )
    seen: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: seen.append(a[2]))
    import trigger_designer.core.excel as excel_pkg

    monkeypatch.setattr(
        excel_pkg,
        "write_frame_xlsx",
        lambda *a, **k: (_ for _ in ()).throw(OSError("boom")),
    )
    viewer.export_excel()
    assert seen and "boom" in seen[0]

    seen.clear()
    monkeypatch.undo()
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), "")
    )
    viewer.export_excel()
    assert target.exists()
