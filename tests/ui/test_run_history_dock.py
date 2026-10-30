"""The Run History dock (docs/plan/02-audit-trail.md 6.4), offscreen."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import orjson
import pytest
from qtpy.QtCore import QCoreApplication
from qtpy.QtWidgets import QApplication, QDockWidget

from tests.support.audit_helpers import (
    build_window,
    make_fingerprint,
    make_node,
    make_record,
)
from trigger_designer.core.audit.store import RunStore
from trigger_designer.qt.docks import run_history_dock
from trigger_designer.qt.docks.run_history_dock import RunHistoryDock
from trigger_designer.qt.main_window import TriggerWindow
from trigger_designer.qt.widgets.common import EmptyStateLabel, IconButton


class _Recorder:
    """Stands in for QMessageBox / QFileDialog / QDesktopServices."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.save_path = ""

    def warning(self, *args, **_kw):
        self.calls.append(("warning", *args[1:]))

    information = warning

    def getSaveFileName(self, *_a, **_k):
        return self.save_path, ""

    def openUrl(self, url):
        self.calls.append(("open", url.toLocalFile()))
        return True


@pytest.fixture()
def patched(monkeypatch):
    stub = _Recorder()
    monkeypatch.setattr(run_history_dock, "QMessageBox", stub)
    monkeypatch.setattr(run_history_dock, "QFileDialog", stub)
    monkeypatch.setattr(run_history_dock, "QDesktopServices", stub)
    shown: list = []
    monkeypatch.setattr(
        run_history_dock, "show_input_check", lambda _p, checks: shown.append(checks)
    )
    stub.input_checks = shown
    return stub


class _Window:
    """The two things the dock reads from a design window."""

    def __init__(self, filename):
        from qtpy.QtCore import QObject, Signal

        class Holder(QObject):
            runRecorded = Signal(str)

        self._holder = Holder()
        self.runRecorded = self._holder.runRecorded
        self.filename = filename


def _store(tmp_path):
    return RunStore(app_data_dir=tmp_path / "ad")


def _seed(tmp_path, count=3, **over):
    """``count`` sealed records next to ``tmp_path/wf.tds``."""
    tds = tmp_path / "wf.tds"
    tds.write_text("{}")
    directory = tmp_path / "wf.runs"
    store = _store(tmp_path)
    sealed = []
    for i in range(count):
        record = make_record(
            started_at=f"2026-10-21T09:14:0{i}.000000Z",
            finished_at=f"2026-10-21T09:14:0{i}.500000Z",
            **over,
        )
        sealed.append(store.seal_and_save(record, directory)[0])
    return tds, directory, sealed


def _dock(qtbot, tds, theme_manager):
    dock = RunHistoryDock()
    qtbot.addWidget(dock)
    dock.show()
    window = _Window(str(tds))
    dock.switch_to_design_window(window)
    dock._test_window = window  # keep the stand-in alive
    assert dock.wait_for_tasks()
    return dock


def _cell(dock, row, column):
    return dock.run_model.index(row, column).data()


def test_dock_registered_tabified_and_in_the_window_menu(
    qtbot, theme_manager, clean_preferences
):
    window = TriggerWindow()
    qtbot.addWidget(window)
    window.show()
    window.updateWindowMenu()
    dock = window.runHistoryDock
    assert dock.objectName() == "RunHistoryDock"
    assert dock.windowTitle() == "Run History"
    assert dock in window.tabifiedDockWidgets(window.loggingDock)
    assert window.dockWidgetArea(dock) == window.dockWidgetArea(window.loggingDock)
    texts = [a.text() for a in window.windowMenu.actions()]
    assert "Run History" in texts
    assert isinstance(dock, QDockWidget)


def test_default_layout_tabs_the_history_with_the_bottom_docks(
    qtbot, theme_manager, clean_preferences
):
    from trigger_designer.qt.layout_state import apply_default_layout

    window = TriggerWindow()
    qtbot.addWidget(window)
    window.show()
    apply_default_layout(window)
    tabbed = window.tabifiedDockWidgets(window.loggingDock)
    assert window.runHistoryDock in tabbed
    assert window.dataPreviewDock in tabbed and window.problemsDock in tabbed


def test_following_the_active_window(qtbot, theme_manager, clean_preferences, tmp_path):
    window = TriggerWindow()
    qtbot.addWidget(window)
    window.show()
    window.onFileNew()
    QApplication.processEvents()
    sub = window.mdiArea.subWindowList()[0]
    window.mdiArea.setActiveSubWindow(sub)
    QApplication.processEvents()
    assert window.runHistoryDock._window is sub.widget()
    window.onDesignWindowClose(sub.widget(), None)
    assert window.runHistoryDock._window is None


def test_lists_runs_newest_first(qtbot, theme_manager, clean_preferences, tmp_path):
    tds, _dir, sealed = _seed(tmp_path, 3)
    dock = _dock(qtbot, tds, theme_manager)
    assert dock.run_model.rowCount() == 3
    assert [_cell(dock, r, 0) for r in range(3)] == ["3", "2", "1"]
    assert {_cell(dock, r, 2) for r in range(3)} == {"ok"}
    assert _cell(dock, 0, 6) == "-"  # chain not verified yet
    # the background pass fills duration / nodes / rows
    assert _cell(dock, 0, 4) == "2" and _cell(dock, 0, 5) == "3"
    assert dock.empty_label.isHidden() and not dock.main_split.isHidden()
    assert "3 runs" in dock.status_label.text()
    assert "not verified" in dock.status_label.text()
    assert dock.current_run_id() == sealed[-1].run_id


def test_empty_state_when_no_runs(qtbot, theme_manager, clean_preferences, tmp_path):
    tds = tmp_path / "wf.tds"
    tds.write_text("{}")
    dock = _dock(qtbot, tds, theme_manager)
    assert isinstance(dock.empty_label, EmptyStateLabel)
    assert dock.empty_label.isVisible() and dock.main_split.isHidden()
    assert dock.empty_label.text() == "No runs recorded yet"
    assert not dock.btn_verify.isEnabled() and not dock.btn_export_json.isEnabled()
    # no window at all: nothing to show, nothing raises
    dock.switch_to_design_window(None)
    assert dock.run_model.rowCount() == 0 and dock.status_label.text() == ""


def test_selecting_a_run_fills_summary_and_node_table(
    qtbot, theme_manager, clean_preferences, tmp_path
):
    tds, directory, sealed = _seed(
        tmp_path,
        2,
        nodes=[
            make_node(1, title="Load"),
            make_node(
                2,
                title="Filter",
                status="failed",
                error={"code": "TD-SCH-001", "title": "Column 'amnt' was not found"},
            ),
        ],
        status="failed",
    )
    dock = _dock(qtbot, tds, theme_manager)
    dock.select_run(sealed[0].run_id)
    labels = dict(dock.summary_model.rows())
    assert labels["Run id"] == sealed[0].run_id
    assert dock.node_model.rowCount() == 2
    titles = [dock.node_model.index(r, 0).data() for r in range(2)]
    assert titles == ["Load", "Filter"]
    assert dock.node_model.index(1, 2).data() == "failed"
    assert dock.node_model.index(1, 7).data() == "Column 'amnt' was not found"
    assert not dock.btn_compare.isEnabled()
    assert dock.btn_check_inputs.isEnabled() and dock.btn_export_html.isEnabled()
    assert Path(directory).is_dir()


def test_every_toolbar_button_is_icon_only_with_tooltip_and_name(
    qtbot, theme_manager, clean_preferences, tmp_path
):
    tds, *_ = _seed(tmp_path, 1)
    dock = _dock(qtbot, tds, theme_manager)
    buttons = dock.findChildren(IconButton)
    assert len(buttons) == 7
    for button in buttons:
        assert button.toolTip() and button.accessibleName()
        assert button.text() == ""
        assert (button.width(), button.height()) == (30, 30)
        assert not button.icon().isNull()
    assert dock.btn_compare.isCheckable()


def test_no_inline_stylesheet_and_theme_change_is_safe(
    qtbot, theme_manager, clean_preferences, tmp_path
):
    tds, *_ = _seed(tmp_path, 2)
    dock = _dock(qtbot, tds, theme_manager)
    from qtpy.QtWidgets import QWidget

    offenders = [w for w in dock.findChildren(QWidget) if w.styleSheet()]
    assert offenders == [] and dock.styleSheet() == ""
    dock.apply_theme()
    dock.apply_theme()


def test_verify_reports_ok_then_tamper(
    qtbot, theme_manager, clean_preferences, tmp_path, patched
):
    tds, directory, sealed = _seed(tmp_path, 3)
    dock = _dock(qtbot, tds, theme_manager)
    with qtbot.waitSignal(dock.verify_finished, timeout=20_000) as blocker:
        dock.btn_verify.click()
    assert blocker.args[0].ok
    assert "chain verified" in dock.status_label.text()
    assert dock.status_label.text().count("head ") == 1
    assert {_cell(dock, r, 6) for r in range(3)} == {"ok"}
    assert not [c for c in patched.calls if c[0] == "warning"]

    path = directory / f"{sealed[1].run_id}.json"
    os.chmod(path, stat.S_IWRITE)
    data = orjson.loads(path.read_bytes())
    data["status"] = "failed"
    path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

    with qtbot.waitSignal(dock.verify_finished, timeout=20_000) as blocker:
        dock.btn_verify.click()
    assert not blocker.args[0].ok
    warnings = [c for c in patched.calls if c[0] == "warning"]
    assert len(warnings) == 1
    text = warnings[0][-1]
    assert "record_hash_mismatch" in text and "run #2" in text
    # rows newest first: seq 2 is the middle row
    assert _cell(dock, 1, 6) == "record_hash_mismatch"
    assert _cell(dock, 0, 6) == "ok" and _cell(dock, 2, 6) == "ok"
    assert "FAILED" in dock.status_label.text()


def _select_rows(dock, rows):
    from qtpy.QtCore import QItemSelectionModel

    model = dock.run_table.selectionModel()
    model.clearSelection()
    for row in rows:
        model.select(
            dock.run_model.index(row, 0),
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        )
    model.setCurrentIndex(
        dock.run_model.index(rows[-1], 0), QItemSelectionModel.SelectionFlag.NoUpdate
    )


def test_compare_is_enabled_only_for_two_selected_runs(
    qtbot, theme_manager, clean_preferences, tmp_path
):
    tds = tmp_path / "wf.tds"
    tds.write_text("{}")
    store = _store(tmp_path)
    directory = tmp_path / "wf.runs"
    for sha in ("a" * 64, "b" * 64, "c" * 64):
        store.seal_and_save(
            make_record(inputs=[make_fingerprint("input", sha256=sha)]), directory
        )
    dock = _dock(qtbot, tds, theme_manager)
    _select_rows(dock, [0])
    assert not dock.btn_compare.isEnabled()
    _select_rows(dock, [0, 1, 2])
    assert not dock.btn_compare.isEnabled()
    _select_rows(dock, [0, 2])
    assert dock.btn_compare.isEnabled()
    dock.btn_compare.click()
    assert dock.btn_compare.isChecked()
    assert dock.lower_stack.currentWidget() is dock.diff_table
    assert dock.diff_model.rowCount() == 1
    row = [dock.diff_model.index(0, c).data() for c in range(5)]
    assert row[0] == "input" and row[2] == "sha256"
    assert row[3].startswith("a" * 10) and row[4].startswith(
        "c" * 10
    )  # oldest -> newest
    # changing the selection leaves compare mode
    _select_rows(dock, [1])
    assert not dock.btn_compare.isChecked()
    assert dock.lower_stack.currentWidget() is dock.node_table


def test_export_json_writes_a_byte_identical_copy(
    qtbot, theme_manager, clean_preferences, tmp_path, patched
):
    tds, directory, sealed = _seed(tmp_path, 2)
    dock = _dock(qtbot, tds, theme_manager)
    dock.select_run(sealed[0].run_id)
    patched.save_path = str(tmp_path / "exports" / "copy.json")
    with qtbot.waitSignal(dock.export_finished, timeout=20_000):
        dock.btn_export_json.click()
    source = directory / f"{sealed[0].run_id}.json"
    assert Path(patched.save_path).read_bytes() == source.read_bytes()
    from trigger_designer.core.audit.store import verify_record_file

    assert verify_record_file(patched.save_path).ok


def test_export_cancelled_dialog_writes_nothing(
    qtbot, theme_manager, clean_preferences, tmp_path, patched
):
    tds, *_ = _seed(tmp_path, 1)
    dock = _dock(qtbot, tds, theme_manager)
    patched.save_path = ""
    dock.btn_export_json.click()
    dock.btn_export_html.click()
    assert dock.wait_for_tasks()
    assert not (tmp_path / "exports").exists()


def test_export_html_writes_the_file_and_opens_it(
    qtbot, theme_manager, clean_preferences, tmp_path, patched
):
    tds, _dir, sealed = _seed(tmp_path, 1)
    dock = _dock(qtbot, tds, theme_manager)
    patched.save_path = str(tmp_path / "report.html")
    with qtbot.waitSignal(dock.export_finished, timeout=20_000):
        dock.btn_export_html.click()
    page = Path(patched.save_path).read_text(encoding="utf-8")
    assert sealed[0].record_hash in page and "<!doctype html>" in page
    opened = [Path(c[1]) for c in patched.calls if c[0] == "open"]
    assert Path(patched.save_path) in opened


def test_check_inputs_flags_a_modified_input(
    qtbot, theme_manager, clean_preferences, tmp_path, patched
):
    import hashlib

    csv = tmp_path / "in.csv"
    csv.write_bytes(b"a,b\n1,2\n")
    sha = hashlib.sha256(csv.read_bytes()).hexdigest()
    tds, *_ = _seed(
        tmp_path, 1, inputs=[make_fingerprint("input", csv.as_posix(), sha256=sha)]
    )
    dock = _dock(qtbot, tds, theme_manager)
    with qtbot.waitSignal(dock.check_finished, timeout=20_000) as blocker:
        dock.btn_check_inputs.click()
    assert [c.state for c in blocker.args[0]] == ["unchanged"]
    csv.write_bytes(b"a,b\n1,3\n")
    with qtbot.waitSignal(dock.check_finished, timeout=20_000) as blocker:
        dock.btn_check_inputs.click()
    (check,) = blocker.args[0]
    assert check.state == "modified" and check.path == csv.as_posix()
    assert patched.input_checks[-1][0].state == "modified"


def test_input_check_dialog_lists_paths_and_states(qtbot, theme_manager):
    from trigger_designer.core.audit.compare import InputCheck

    checks = [
        InputCheck("C:/a.csv", None, "modified", "a" * 64, "b" * 64),
        InputCheck("C:/b.csv", "S1", "missing", "a" * 64, None),
        InputCheck("C:/c.csv", None, "unchanged", "a" * 64, "a" * 64),
    ]
    dialog = run_history_dock.InputCheckDialog(checks)
    qtbot.addWidget(dialog)
    model = dialog.table.model()
    assert [model.index(r, 0).data() for r in range(3)] == [
        "MODIFIED",
        "MISSING",
        "unchanged",
    ]
    assert model.index(0, 1).data() == "C:/a.csv" and model.index(1, 2).data() == "S1"
    assert "2 of 3" in dialog.summary_label.text()


def test_new_run_signal_refreshes_and_selects(
    qtbot, theme_manager, clean_preferences, tmp_path
):
    tds, directory, _sealed = _seed(tmp_path, 1)
    dock = _dock(qtbot, tds, theme_manager)
    assert dock.run_model.rowCount() == 1
    newer, path = _store(tmp_path).seal_and_save(make_record(), directory)
    dock._test_window.runRecorded.emit(path)
    assert dock.wait_for_tasks()
    assert dock.run_model.rowCount() == 2
    assert dock.current_run_id() == newer.run_id
    assert _cell(dock, 0, 0) == "2"


def test_corrupt_record_is_still_listed(
    qtbot, theme_manager, clean_preferences, tmp_path
):
    tds, directory, sealed = _seed(tmp_path, 2)
    path = directory / f"{sealed[0].run_id}.json"
    os.chmod(path, stat.S_IWRITE)
    path.write_bytes(b"{ not json")
    dock = _dock(qtbot, tds, theme_manager)
    assert dock.run_model.rowCount() == 2
    dock.select_run(sealed[0].run_id)
    assert dock.summary_model.rowCount() == 0 and dock.node_model.rowCount() == 0


def test_open_folder_uses_the_store_directory(
    qtbot, theme_manager, clean_preferences, tmp_path, patched
):
    tds, directory, _ = _seed(tmp_path, 1)
    dock = _dock(qtbot, tds, theme_manager)
    dock.btn_folder.click()
    assert directory in [Path(c[1]) for c in patched.calls if c[0] == "open"]


def test_refresh_button_rereads_the_index(
    qtbot, theme_manager, clean_preferences, tmp_path
):
    tds, directory, _ = _seed(tmp_path, 1)
    dock = _dock(qtbot, tds, theme_manager)
    _store(tmp_path).seal_and_save(make_record(), directory)
    assert dock.run_model.rowCount() == 1
    dock.btn_refresh.click()
    assert dock.run_model.rowCount() == 2


def test_dock_follows_a_real_design_window_run(
    qtbot, theme_manager, clean_preferences, tmp_path, no_modal_dialogs
):
    """A real Run through a real window lands in the dock without any glue."""
    from tests.support.workflows import run_workflow_and_wait
    from trigger_designer.qt.design_window import TriggerSubWindow

    window, _src, _out = build_window(tmp_path)
    tds = tmp_path / "wf.tds"
    window.scene.saveToFile(str(tds))
    window.close()
    sub = TriggerSubWindow()
    qtbot.addWidget(sub)
    assert sub.fileLoad(str(tds)) is True
    dock = RunHistoryDock()
    qtbot.addWidget(dock)
    dock.show()
    dock.switch_to_design_window(sub)
    assert dock.run_model.rowCount() == 0
    run_workflow_and_wait(qtbot, sub)
    QCoreApplication.processEvents()
    assert dock.wait_for_tasks()
    assert dock.run_model.rowCount() == 1
    assert dock.current_run_id()
    assert dict(dock.summary_model.rows())["Status"] == "ok"
    assert dock.node_model.rowCount() == 3
    with qtbot.waitSignal(dock.verify_finished, timeout=20_000) as blocker:
        dock.btn_verify.click()
    assert blocker.args[0].ok
