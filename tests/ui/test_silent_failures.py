"""Failures that used to be silent now reach the user.

* a failed ``.tds`` save shows a dialog with the reason (and is not "saved");
* a failed CSV export shows "Export failed" like the Excel export does;
* a Data Preview export says it wrote only the previewed rows;
* the unsaved-changes dialog has its typo fixed.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import polars as pl
import pytest
from qtpy.QtWidgets import QApplication, QFileDialog, QMessageBox

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.models.polars_table_viewer import PolarsTableViewer
from trigger_designer.qt.models.preview_sampling import collect_preview
from trigger_designer.qt.widgets.data_preview_panel import DataPreviewPanel

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def boxes(monkeypatch):
    """Capture every QMessageBox warning/information instead of blocking."""
    shown: list[tuple[str, str, str]] = []

    def capture(kind):
        def _show(_parent, title, text, *args, **kwargs):
            shown.append((kind, title, text))
            return QMessageBox.StandardButton.Discard

        return _show

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(capture("warning")))
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(capture("information"))
    )
    return shown


# -- (a) failed save --------------------------------------------------------


def test_failed_save_shows_the_reason_and_keeps_the_old_name(tmp_path, boxes):
    window = TriggerSubWindow()
    good = tmp_path / "ok.tds"
    assert window.fileSave(str(good)) is True
    assert window.last_save_error is None and window.filename == str(good)

    bad = tmp_path / "no_such_folder" / "x.tds"
    assert window.fileSave(str(bad)) is False
    assert window.filename == str(good)  # not switched to the failed target
    assert window.last_save_error
    kind, title, text = boxes[-1]
    assert (kind, title) == ("warning", "Save failed")
    assert str(bad) in text and "unsaved" in text
    assert window.last_save_error.split(": ", 1)[1] in text
    window.close()


def test_main_window_reports_a_failed_save_as_not_saved(tmp_path, boxes, monkeypatch):
    from trigger_designer.qt.main_window import TriggerWindow

    window = TriggerWindow()
    try:
        editor = TriggerSubWindow()
        sub = window.createMdiChild(editor)
        window.show()
        sub.show()
        window.mdiArea.setActiveSubWindow(sub)
        _APP.processEvents()
        editor.filename = str(tmp_path / "gone" / "x.tds")  # folder does not exist
        assert window.onFileSave() is False
        assert any(title == "Save failed" for _k, title, _t in boxes)
        assert "Save failed" in window.statusBar().currentMessage()
    finally:
        window.hide()
        window.deleteLater()
        _APP.processEvents()


def test_unsaved_changes_dialog_has_the_typo_fixed(boxes):
    from trigger_designer.qt.main_window import TriggerWindow

    window = TriggerWindow()
    try:
        editor = TriggerSubWindow()
        sub = window.createMdiChild(editor)
        window.show()
        sub.show()
        window.mdiArea.setActiveSubWindow(sub)
        _APP.processEvents()
        editor.scene.has_been_modified = True
        assert window.maybeSave() is True  # the stub answers "Discard"
        titles = [title for _k, title, _t in boxes]
        assert "About to lose your work?" in titles
        assert not any("loose" in title for title in titles)
    finally:
        editor.scene.has_been_modified = False
        window.hide()
        window.deleteLater()
        _APP.processEvents()


# -- (b) CSV export failure -------------------------------------------------


def _viewer() -> PolarsTableViewer:
    return PolarsTableViewer(
        dataframe=pl.DataFrame({"a": [1, 2, 3]}),
        show_controls=False,
        show_info=False,
        show_search=False,
        show_export=False,
    )


def test_csv_export_failure_shows_export_failed(tmp_path, boxes, monkeypatch):
    viewer = _viewer()
    target = tmp_path / "no_such_folder" / "out.csv"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    viewer.export_csv()
    assert boxes and boxes[-1][:2] == ("warning", "Export failed")
    assert "CSV file could not be written" in boxes[-1][2]
    assert not target.exists()


# -- (c) preview export scope -----------------------------------------------


def _panel(rows: int, **limits) -> DataPreviewPanel:
    panel = DataPreviewPanel()
    window = collect_preview(pl.DataFrame({"n": range(rows)}), **limits)
    panel.controller.previewReady.emit(window)
    return panel


def test_partial_preview_export_says_it_is_only_the_previewed_rows(
    tmp_path, boxes, monkeypatch
):
    panel = _panel(2500, max_rows=1000)  # eager 2,500 rows, 1,000 collected
    target = tmp_path / "preview.csv"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    panel.viewer.export_csv()
    assert target.exists() and pl.read_csv(target).height == 1000
    kind, title, text = boxes[-1]
    assert (kind, title) == ("information", "Export complete")
    assert "Exported 1,000 of 2,500 rows" in text
    assert "File Output" in text
    assert "only the rows collected" in panel.export_csv_action.toolTip()


def test_complete_preview_export_shows_no_dialog(tmp_path, boxes, monkeypatch):
    panel = _panel(50)
    target = tmp_path / "all.csv"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    panel.viewer.export_csv()
    assert pl.read_csv(target).height == 50
    assert boxes == []


def test_search_filtered_export_names_the_filter(tmp_path, boxes, monkeypatch):
    panel = DataPreviewPanel()
    frame = pl.DataFrame({"city": ["Berlin"] * 3 + ["Paris"] * 7})
    panel.controller.previewReady.emit(collect_preview(frame))
    panel.viewer.apply_search("Berlin", None)
    shown = panel.viewer.model.total_rows
    assert shown == 3
    target = tmp_path / "filtered.csv"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    panel.viewer.export_csv()
    text = boxes[-1][2]
    assert f"Exported {shown:,}" in text and "matching the search" in text
