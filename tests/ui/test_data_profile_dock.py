"""Data Profile Config Dock (plan 05 section 6.3), offscreen."""

from __future__ import annotations

import os
import sys

import polars as pl
import pytest
from nodeeditor.node_edge import Edge
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from trigger_designer.core.node_configuration import (
    NodeTypes,
    ReportNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets import profile_view
from trigger_designer.qt.widgets.common import EmptyStateLabel

WAIT_MS = 15_000


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, frame) -> None:
        self._frame = frame
        super().__init__(scene, inputs=[], outputs=[3])
        self.value = [{"data": frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)

    def evalImplementation(self):
        self.value = [{"data": self._frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


def sample_frame(rows: int = 60) -> pl.LazyFrame:
    return pl.DataFrame(
        {
            "qty": [i % 7 for i in range(rows)],
            "flag": ["Y" if i % 3 else "N" for i in range(rows)],
            "maybe": [None if i % 2 else "x" for i in range(rows)],
        }
    ).lazy()


def build(qtbot, data=None, wired: bool = True):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    cls = get_class_from_opcode(ReportNodes.DATA_PROFILE, NodeTypes.REPORT)
    node = cls(window.scene)
    if wired:
        source = Source(window.scene, sample_frame() if data is None else data)
        Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, dock


def ready_view(qtbot, node):
    view = node.content._view
    assert view is not None
    qtbot.waitUntil(lambda: view.state == "ready", timeout=WAIT_MS)
    return view


def select_column(view, name: str) -> None:
    for row in range(view.proxy.rowCount()):
        if view.proxy.index(row, 0).data() == name:
            view.table.selectRow(row)
            return
    raise AssertionError(name)


def test_rows_start_in_input_column_order(qtbot):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    names = [view.proxy.index(r, 0).data() for r in range(view.proxy.rowCount())]
    assert names == ["qty", "flag", "maybe"]
    view.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
    assert view.proxy.index(0, 0).data() == "qty"  # q > m > f when descending
    view.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    assert view.proxy.index(0, 0).data() == "flag"


def test_dock_fills_and_sorts(qtbot):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    assert view.model.rowCount() == 3
    assert [view.model.headerData(i, Qt.Orientation.Horizontal) for i in range(6)] == [
        "Column",
        "Type",
        "Null %",
        "Distinct",
        "Suggested",
        "Flags",
    ]
    view.table.sortByColumn(2, Qt.SortOrder.DescendingOrder)
    assert view.proxy.index(0, 0).data() == "maybe"  # 50% null, the others 0%


def test_detail_pane_histogram_for_numbers_and_bars_for_text(qtbot):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    select_column(view, "qty")
    assert view.chart.kind == "hist"
    select_column(view, "flag")
    assert view.chart.kind == "freq"
    assert "Distinct" in view.detail_stats.text()


def test_data_notice_then_sample_notice(qtbot):
    _window, node, _dock = build(qtbot, sample_frame(5000))
    view = ready_view(qtbot, node)
    assert view.notice.text().startswith("Data: 5,000 rows")
    node.content.set_setting("sample_mode", "head", "Profile Sample Changed")
    node.content.set_setting("sample_rows", 1000, "Profile Rows Changed")
    qtbot.waitUntil(
        lambda: view.notice.text().startswith("Sample: first"), timeout=WAIT_MS
    )
    assert view.notice.property("tone") == "accent"
    assert "1,000" in view.notice.text()


def test_setting_change_is_one_undo_step_and_restores_widgets(qtbot):
    window, node, _dock = build(qtbot)
    ready_view(qtbot, node)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    content.set_setting("top_n", 9, "Profile Top values Changed")
    assert content.settings["top_n"] == 9
    history.undo()
    assert content.settings["top_n"] == 5
    assert content._widgets["top_n"].value() == 5
    history.redo()
    assert content.settings["top_n"] == 9
    assert content._widgets["top_n"].value() == 9


def test_search_typing_is_not_recorded(qtbot):
    window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    history = window.scene.history
    history.storeHistory("Baseline")
    before = history.canUndo()
    view.search.setText("fla")
    qtbot.wait(400)
    assert view.proxy.rowCount() == 1
    assert history.canUndo() == before


def test_copy_puts_tsv_on_the_clipboard(qtbot):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    view.copy_profile()
    text = QApplication.clipboard().text()
    lines = text.splitlines()
    assert lines[0].split("\t")[0] == "column"
    assert len(lines) == 4  # header + three columns
    assert view.notice.text().startswith("Copied")


def test_export_csv(qtbot, tmp_path, monkeypatch):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    target = tmp_path / "p.csv"
    monkeypatch.setattr(
        profile_view.QFileDialog,
        "getSaveFileName",
        lambda *_a, **_k: (str(target), ""),
    )
    view.export_csv()
    assert pl.read_csv(target).height == 3
    assert view.notice.text().startswith("Exported")


def test_excel_export_degrades_without_the_helper(qtbot, tmp_path, monkeypatch):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    monkeypatch.setitem(sys.modules, "trigger_designer.core.excel", None)
    monkeypatch.setattr(
        profile_view.QFileDialog,
        "getSaveFileName",
        lambda *_a, **_k: (str(tmp_path / "p.xlsx"), ""),
    )
    view.export_excel()
    assert view.notice.text().startswith("Export failed")
    assert view.notice.property("tone") == "warning"


def test_excel_export_writes_a_workbook_when_the_helper_exists(
    qtbot, tmp_path, monkeypatch
):
    pytest.importorskip("trigger_designer.core.excel")
    openpyxl = pytest.importorskip("openpyxl")
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    target = tmp_path / "p.xlsx"
    monkeypatch.setattr(
        profile_view.QFileDialog,
        "getSaveFileName",
        lambda *_a, **_k: (str(target), ""),
    )
    view.export_excel()
    assert openpyxl.load_workbook(target)["Profile"].max_row == 4


def test_empty_state_without_input(qtbot):
    _window, node, dock = build(qtbot, wired=False)
    assert node.content._view is None
    assert dock.findChildren(EmptyStateLabel)


def test_recompute_button_rebuilds_the_profile(qtbot):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    first = node.content.current_profile()
    view.refresh_button.click()
    qtbot.waitUntil(lambda: view.state == "ready", timeout=WAIT_MS)
    qtbot.waitUntil(
        lambda: node.content.current_profile() is not first, timeout=WAIT_MS
    )


def test_create_layout_direct_has_no_exception(qtbot):
    _window, node, _dock = build(qtbot)
    holder = QWidget()
    qtbot.addWidget(holder)
    node.content.create_layout(QVBoxLayout(holder))


def test_toolbar_buttons_have_tooltips_and_accessible_names(qtbot):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    for button in (view.report_button, view.export_button, view.refresh_button):
        assert button.toolTip()
        assert button.accessibleName() == button.toolTip()
        assert not button.text()


def test_view_is_an_undo_composite(qtbot):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    assert view._undo_composite is True


def test_pure_helpers_describe_a_column(qtbot):
    from trigger_designer.core import profile as pf

    p = pf.profile_frame(
        pl.DataFrame({"a": ["1", "-2", "x" * 3], "b": ["2024-01-01"] * 3})
    )
    by = {c.name: c for c in p.columns}
    assert profile_view.status_text(p) == "Data: 3 rows"
    labels = dict(profile_view.detail_rows(by["a"]))
    assert labels["Type in file"] == "String"
    assert "Null" in labels
    assert profile_view.suggested_text(by["b"]) == "Date"
    assert profile_view.distinct_text(by["a"]) == "3"
    assert profile_view.chart_for(by["b"])[2] == "freq"


def test_one_export_button_with_a_menu(qtbot):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    assert [a.text() for a in view.export_menu.actions()] == [
        "Copy to clipboard",
        "CSV file...",
        "HTML report...",
        "Excel workbook...",
    ]
    assert view.export_button.menu() is view.export_menu
    # the three old per-format buttons are gone
    for name in ("copy_button", "csv_button", "excel_button"):
        assert not hasattr(view, name)


def test_menu_actions_run_the_exports(qtbot, tmp_path, monkeypatch):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    target = tmp_path / "from_menu.csv"
    monkeypatch.setattr(
        profile_view.QFileDialog,
        "getSaveFileName",
        lambda *_a, **_k: (str(target), ""),
    )
    view.csv_action.trigger()
    assert pl.read_csv(target).height == 3
    view.copy_action.trigger()
    assert view.notice.text().startswith("Copied")


def test_export_html_writes_a_report_with_every_column(qtbot, tmp_path, monkeypatch):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    target = tmp_path / "report.html"
    monkeypatch.setattr(
        profile_view.QFileDialog,
        "getSaveFileName",
        lambda *_a, **_k: (str(target), ""),
    )
    view.export_html()
    html = target.read_text(encoding="utf-8")
    assert "<title>Data Profile</title>" in html  # the node's own title
    for name in ("qty", "flag", "maybe"):
        assert f'id="col-{["qty", "flag", "maybe"].index(name) + 1}"' in html
        assert name in html
    assert view.notice.text() == "Exported HTML report"


def test_full_report_button_opens_the_html_in_the_browser(qtbot, monkeypatch):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    opened = []
    monkeypatch.setattr(
        profile_view.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )
    view.report_button.click()
    assert len(opened) == 1
    path = opened[0]
    assert path.endswith(".html")
    html = open(path, encoding="utf-8").read()  # noqa: SIM115
    assert html.count('class="card"') == 3  # a card for every column
    # Qt reports forward slashes; the list keeps the OS form. Removed at exit.
    assert os.path.normpath(path) in map(os.path.normpath, profile_view._TEMP_REPORTS)


def test_full_report_reports_a_browser_that_will_not_open(qtbot, monkeypatch):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    monkeypatch.setattr(profile_view.QDesktopServices, "openUrl", lambda _url: False)
    view.open_full_report()
    assert view.notice.text().startswith("Could not open the report")


def test_live_profile_is_labelled_as_a_preview(qtbot):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    assert view.source == "live"
    assert "Run the workflow" in view.notice.toolTip()


def run_frame(rows: int) -> pl.DataFrame:
    from trigger_designer.core.shaping import data_profile

    return data_profile.run_node([sample_frame(rows)], {})[1].collect()


def test_dock_shows_the_full_profile_after_a_run(qtbot):
    # The canvas holds 60 rows; the Run profiled all 5,000.
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    assert view.notice.text() == "Data: 60 rows"
    content = node.content
    content.on_run_result({content.output_variables[1]: run_frame(5000).lazy()})
    qtbot.waitUntil(lambda: view.source == "run", timeout=WAIT_MS)
    assert view.notice.text() == "Data: 5,000 rows"
    assert "workflow run" in view.notice.toolTip()
    assert view.model.rowCount() == 3
    select_column(view, "qty")
    assert view.chart.kind == "hist"  # chart data survived the table round trip


def test_changing_a_setting_returns_to_the_live_preview(qtbot):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    content = node.content
    content.on_run_result({content.output_variables[1]: run_frame(5000).lazy()})
    qtbot.waitUntil(lambda: view.source == "run", timeout=WAIT_MS)
    content.set_setting("top_n", 7, "Profile Top values Changed")
    qtbot.waitUntil(lambda: view.source == "live", timeout=WAIT_MS)
    qtbot.waitUntil(lambda: view.state == "ready", timeout=WAIT_MS)
    assert view.notice.text() == "Data: 60 rows"


def test_html_after_a_run_describes_the_whole_run(qtbot, monkeypatch):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    content = node.content
    content.on_run_result({content.output_variables[1]: run_frame(5000).lazy()})
    qtbot.waitUntil(lambda: view.source == "run", timeout=WAIT_MS)
    html = view._report_html()
    assert "Data: 5,000 rows" in html
    assert "Distribution" in html


def test_summary_line_is_not_shown(qtbot):
    _window, node, dock = build(qtbot)
    ready_view(qtbot, node)
    assert node.content.dock_summary() == ""
    from qtpy.QtWidgets import QLabel

    shown = [
        label.text()
        for label in dock.findChildren(QLabel, "ConfigSummary")
        if label.isVisibleTo(dock)
    ]
    assert shown == []


def test_options_are_explained(qtbot):
    from trigger_designer.qt.widgets.nodes.Report.data_profile import (
        DataProfileContent,
    )

    fields = {f.key: f for f in DataProfileContent.FORM[0].fields}
    assert fields["histogram_bins"].label == "Chart bars"
    assert "bars" in fields["histogram_bins"].hint
    assert fields["approx_distinct_threshold"].label == "Estimate over"
    assert all(f.hint for f in fields.values())
    assert next(label for _v, label in fields["sample_mode"].options) == "All rows"


def test_an_old_views_destroyed_signal_does_not_drop_the_new_view(qtbot):
    _window, node, dock = build(qtbot)
    content = node.content
    ready_view(qtbot, node)
    first_generation = content._view_generation
    dock.updateConfig([node.grNode], force=True)  # rebuild: a new view
    assert content._view_generation == first_generation + 1
    content._drop_view(first_generation)  # the old view's late destroyed signal
    assert content._view is not None
    content._drop_view(content._view_generation)
    assert content._view is None


def test_a_failing_profile_is_shown_in_the_chip_not_raised(qtbot, monkeypatch):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    content = node.content

    def boom(*_args, **_kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(content, "get_or_compute", boom)
    content.request_profile()
    assert view.state == "failed"
    assert view.notice.text() == "Profile failed: boom"


def test_the_run_result_stays_on_show_when_the_dock_refreshes(qtbot):
    _window, node, _dock = build(qtbot)
    view = ready_view(qtbot, node)
    content = node.content
    content.on_run_result({content.output_variables[1]: run_frame(5000).lazy()})
    qtbot.waitUntil(lambda: view.source == "run", timeout=WAIT_MS)
    content.request_profile()
    content.on_inputs_processed()
    qtbot.wait(50)
    assert view.source == "run"
    assert view.notice.text() == "Data: 5,000 rows"


def test_profile_is_computed_on_the_gui_thread(qtbot):
    import threading

    seen = []
    _window, node, _dock = build(qtbot)
    content = node.content
    real = content.get_or_compute

    def spy(*args, **kwargs):
        seen.append(threading.current_thread() is threading.main_thread())
        return real(*args, **kwargs)

    content.get_or_compute = spy
    content._cache = None
    content.request_profile()
    assert seen == [True]


def wide_frame(columns: int) -> pl.LazyFrame:
    return pl.DataFrame({f"c{i}": [1, 2, 3] for i in range(columns)}).lazy()


def test_a_very_wide_input_skips_the_live_preview(qtbot):
    from trigger_designer.core.shaping import data_profile

    columns = data_profile.LIVE_MAX_COLUMNS + 1
    _window, node, _dock = build(qtbot, wide_frame(columns))
    view = node.content._view
    assert view.state == "skipped"
    assert view.model.rowCount() == 0
    assert not view.table.isVisibleTo(view)
    assert f"{columns} columns" in view.empty_note.text()
    assert "Run the workflow" in view.empty_note.text()
    assert view.notice.text() == "Live preview skipped"


def test_the_limit_itself_is_still_profiled(qtbot):
    from trigger_designer.core.shaping import data_profile

    _window, node, _dock = build(qtbot, wide_frame(data_profile.LIVE_MAX_COLUMNS))
    view = ready_view(qtbot, node)
    assert view.model.rowCount() == data_profile.LIVE_MAX_COLUMNS


def test_a_run_profiles_a_wide_input_that_the_preview_skipped(qtbot):
    from trigger_designer.core.shaping import data_profile

    columns = data_profile.LIVE_MAX_COLUMNS + 50
    _window, node, _dock = build(qtbot, wide_frame(columns))
    view = node.content._view
    assert view.state == "skipped"
    content = node.content
    run = data_profile.run_node([wide_frame(columns)], {})[1]
    content.on_run_result({content.output_variables[1]: run})
    assert view.state == "ready"
    assert view.source == "run"
    assert view.model.rowCount() == columns
    assert view.table.isVisibleTo(view)
    assert view.empty_note.text() == "No columns" and not view.empty_note.isVisibleTo(
        view
    )
