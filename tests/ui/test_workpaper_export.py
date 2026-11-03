"""File > Export Workpaper...: action, dialog and the whole flow (offscreen)."""

from __future__ import annotations

from pathlib import Path

import pytest
from qtpy.QtWidgets import QDialog, QFileDialog

from tests.support.workpaper import load
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    ReportNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.helpers import workpaper_export
from trigger_designer.qt.helpers.workpaper_export import (
    WorkpaperExportDialog,
    default_output_path,
    export_workpaper,
)

RECORD = {
    "run_id": "r1",
    "status": "ok",
    "started_at": "2026-03-31T09:00:00.000000Z",
    "finished_at": "2026-03-31T09:00:01.000000Z",
    "app_version": "0.1.0",
    "inputs": [],
    "outputs": [],
    "nodes": [
        {
            "node_id": 0,
            "op": "audit.duplicates",
            "title": "Duplicates",
            "status": "ok",
            "rows_out": {"v": 3},
            "test_summary": {
                "test_name": "Duplicates",
                "criteria": "Same invoice",
                "status": "fail",
                "population_rows": 10,
                "exception_rows": 3,
                "exception_rate": 0.3,
                "message": "3 repeat",
            },
        }
    ],
}


class Box:
    """Stands in for QMessageBox."""

    def __init__(self):
        self.calls = []

    def information(self, _parent, title, text, *_a, **_k):
        self.calls.append(("information", title, text))

    def warning(self, _parent, title, text, *_a, **_k):
        self.calls.append(("warning", title, text))


class FakeStore:
    def __init__(self, record):
        self.record = record
        self.asked = []

    def latest_record_dict(self, directory=None, workflow_path=None):
        self.asked.append(workflow_path)
        return self.record


class FakeMain:
    def __init__(self, widget):
        self._widget = widget

    def getCurrentNodeEditorWidget(self):
        return self._widget


class FakeDialog:
    out = ""
    accept = True

    def __init__(self, _parent, suggested):
        self.suggested = suggested

    def exec(self):
        return (
            QDialog.DialogCode.Accepted if self.accept else QDialog.DialogCode.Rejected
        )

    def settings(self):
        return {
            "output_path": self.out,
            "client": "Acme",
            "preparer": "A. Auditor",
            "objective": "Check repeats",
            "if_exists": "version",
        }


@pytest.fixture
def env(qtbot, monkeypatch, clean_preferences, tmp_path):
    box = Box()
    monkeypatch.setattr(workpaper_export, "QMessageBox", box)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.filename = str(tmp_path / "wf.tds")
    store = FakeStore(RECORD)
    monkeypatch.setattr(workpaper_export, "store_from_preferences", lambda: store)
    FakeDialog.out = str(tmp_path / "run.xlsx")
    FakeDialog.accept = True
    return window, box, store, tmp_path


def test_no_recorded_run_says_so(env):
    window, box, store, _ = env
    store.record = None
    assert export_workpaper(FakeMain(window), dialog_class=FakeDialog) is None
    assert box.calls[0][0] == "information"
    assert "Run the workflow first" in box.calls[0][2]
    assert store.asked == [window.filename]


def test_no_active_window_does_nothing(env):
    _w, box, _s, _t = env
    assert export_workpaper(FakeMain(None), dialog_class=FakeDialog) is None
    assert box.calls == []


def test_cancelled_dialog_writes_nothing(env):
    window, box, _s, tmp = env
    FakeDialog.accept = False
    assert export_workpaper(FakeMain(window), dialog_class=FakeDialog) is None
    assert not (tmp / "run.xlsx").exists() and box.calls == []


def test_export_writes_the_run_workpaper(env, clean_preferences):
    window, box, _s, tmp = env
    scene = window.scene
    fin = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    fin.id = 0
    note = get_class_from_opcode(ReportNodes.COMMENT, NodeTypes.REPORT)(scene)
    note.content.settings["text"] = "Reviewed with the client"
    path = export_workpaper(FakeMain(window), dialog_class=FakeDialog)
    assert Path(path) == tmp / "run.xlsx"
    assert box.calls[-1][0] == "information"
    assert "run.xlsx" in box.calls[-1][2]
    wb = load(path)
    assert wb.sheetnames == ["Summary", "Run log", "Workflow"]
    summary = wb["Summary"]
    assert summary["B6"].value == "Acme" and summary["B10"].value == "A. Auditor"
    assert [c.value for c in wb["Workflow"]["A"]][3:5] == ["Step", 1]
    notes = [
        row[1].value
        for row in wb["Workflow"].iter_rows(min_col=1, max_col=2)
        if row[0].value == "Note"
    ]
    assert notes == ["Reviewed with the client"]
    assert Path(clean_preferences.get("export/workpaper_dir")) == tmp


def test_second_export_creates_a_numbered_copy(env):
    window, _box, _s, _tmp = env
    first = export_workpaper(FakeMain(window), dialog_class=FakeDialog)
    second = export_workpaper(FakeMain(window), dialog_class=FakeDialog)
    assert Path(second).name == "run (2).xlsx" and Path(first).exists()


def test_write_failure_is_reported_in_plain_language(env):
    window, box, _s, tmp = env
    FakeDialog.out = str(tmp / "missing_folder" / "run.xlsx")
    assert export_workpaper(FakeMain(window), dialog_class=FakeDialog) is None
    kind, title, text = box.calls[-1]
    assert kind == "warning" and title == "Workpaper not written"
    assert "does not exist" in text


def test_default_output_path_uses_workflow_name_and_last_folder(
    clean_preferences, tmp_path
):
    assert default_output_path(str(tmp_path / "Ledger test.tds")) == str(
        tmp_path / "Ledger test workpaper.xlsx"
    )
    clean_preferences.set("export/workpaper_dir", "D:/wp")
    got = default_output_path(None).replace("\\", "/")
    assert got == "D:/wp/Workflow workpaper.xlsx"


def test_dialog_collects_values_and_browses(
    qtbot, monkeypatch, clean_preferences, tmp_path
):
    clean_preferences.set("engagement/client_name", "Pref Client")
    dialog = WorkpaperExportDialog(None, str(tmp_path / "a.xlsx"))
    qtbot.addWidget(dialog)
    assert dialog.edits["client"].placeholderText() == "Pref Client"
    dialog.edits["client"].setText(" Acme ")
    dialog.objective.setPlainText("Obj")
    dialog.if_exists.setCurrentIndex(dialog.if_exists.findData("replace"))
    values = dialog.settings()
    assert values["client"] == "Acme" and values["objective"] == "Obj"
    assert values["if_exists"] == "replace"
    assert values["output_path"] == str(tmp_path / "a.xlsx")
    target = str(tmp_path / "picked")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (target, ""))
    dialog.browse()
    assert dialog.path_edit.text() == target + ".xlsx"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    dialog.browse()
    assert dialog.path_edit.text() == target + ".xlsx"


def test_menu_action_is_enabled_with_a_window_and_calls_the_export(
    qtbot, monkeypatch, clean_preferences
):
    from trigger_designer.qt.main_window import TriggerWindow

    window = TriggerWindow()
    qtbot.addWidget(window)
    assert window.actExportWorkpaper in window.fileMenu.actions()
    assert "Workpaper" in window.actExportWorkpaper.text()
    window.updateMenus()
    assert not window.actExportWorkpaper.isEnabled()
    window.show()
    window.onFileNew()
    qtbot.wait(50)
    window.updateMenus()
    assert window.actExportWorkpaper.isEnabled() == window.actSave.isEnabled() is True
    seen = []
    monkeypatch.setattr(
        workpaper_export, "export_workpaper", lambda main: seen.append(main)
    )
    window.actExportWorkpaper.trigger()
    assert seen == [window]
