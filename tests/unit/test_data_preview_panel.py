#!/usr/bin/env python3
"""DataPreviewPanel: states, info line, footer paging, Ctrl+R refresh."""

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.models.preview_sampling import collect_preview
from trigger_designer.qt.widgets.data_preview_panel import DataPreviewPanel
from trigger_designer.qt.widgets.data_preview_window import DataPreviewWindow

_APP = QApplication.instance() or QApplication([])


def _panel_with(rows: int = 600) -> DataPreviewPanel:
    """Panel fed a preview result directly (no worker threads)."""
    panel = DataPreviewPanel()
    window = collect_preview(pl.DataFrame({"n": range(rows)}), max_rows=1000)
    panel.controller.previewReady.emit(window)
    return panel


def _stub_requests(panel: DataPreviewPanel) -> list:
    """Keep set_source/refresh thread-free; records the requested payloads."""
    requested: list = []
    panel.controller.request = requested.append
    return requested


def _wait_until(predicate, timeout_ms: int = 10_000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    QApplication.processEvents()
    return predicate()


# -- states ------------------------------------------------------------------


def test_initial_state_is_select_a_node():
    panel = DataPreviewPanel()

    assert panel._state_label.text() == "Select a node to preview its output"
    assert not panel._state_label.isHidden()
    assert panel._content.isHidden()
    assert panel.info_label.isHidden()


def test_set_source_without_payload_accepts_custom_empty_text():
    panel = _panel_with(10)

    panel.set_source(None)
    assert panel._state_label.text() == "Select a node to preview its output"
    assert panel._content.isHidden()

    panel.set_source(None, empty_text="This node has no tabular output")
    assert panel._state_label.text() == "This node has no tabular output"


def test_no_rows_state():
    panel = DataPreviewPanel()
    window = collect_preview(pl.DataFrame(schema={"n": pl.Int64}), max_rows=1000)

    panel.controller.previewReady.emit(window)

    assert panel._state_label.text() == "No rows"
    assert panel._content.isHidden()


def test_failure_state_uses_the_same_label():
    panel = DataPreviewPanel()

    panel.controller.failed.emit("boom")

    assert panel._state_label.text() == "Preview failed: boom"
    assert not panel._state_label.isHidden()
    assert panel._content.isHidden()


# -- table, info line, footer ------------------------------------------------


def test_preview_fills_table_info_and_footer():
    panel = _panel_with(600)

    assert panel._state_label.isHidden()
    assert not panel._content.isHidden()
    assert not panel.info_label.isHidden()
    assert panel.info_label.text() == "600 rows - 1 columns"
    assert panel.viewer.model.total_rows == 600
    assert panel.viewer.model.rowCount() == 250
    assert panel.range_label.text() == "Rows 1-250 of 600"
    assert not panel._first_btn.isEnabled()
    assert not panel._prev_btn.isEnabled()
    assert panel._next_btn.isEnabled()
    assert panel._last_btn.isEnabled()


def test_footer_paging_buttons_walk_pages_and_sync_the_range():
    panel = _panel_with(600)

    panel._next_btn.click()
    assert panel.range_label.text() == "Rows 251-500 of 600"

    panel._next_btn.click()
    assert panel.range_label.text() == "Rows 501-600 of 600"
    assert not panel._next_btn.isEnabled()
    assert not panel._last_btn.isEnabled()
    assert panel._first_btn.isEnabled()

    panel._first_btn.click()
    assert panel.range_label.text() == "Rows 1-250 of 600"

    panel._last_btn.click()
    assert panel.range_label.text() == "Rows 501-600 of 600"


def test_page_size_combo_resizes_pages():
    panel = _panel_with(600)

    panel.page_size_combo.setCurrentText("100")

    assert panel.viewer.model.page_size == 100
    assert panel.range_label.text() == "Rows 1-100 of 600"


def test_info_line_counts_pending_then_resolved():
    panel = DataPreviewPanel()
    window = collect_preview(pl.DataFrame({"n": range(5000)}).lazy(), max_rows=1000)
    assert window.limited and window.is_lazy

    panel.controller.previewReady.emit(window)
    assert panel.info_label.text() == "1,000 rows collected - counting... - 1 columns"

    panel.controller.countReady.emit(5000)
    assert panel.info_label.text() == "1,000 rows collected - 5,000 total - 1 columns"


def test_count_equal_to_collected_drops_the_total_segment():
    panel = DataPreviewPanel()
    window = collect_preview(pl.DataFrame({"n": range(1000)}).lazy(), max_rows=1000)

    panel.controller.previewReady.emit(window)
    panel.controller.countReady.emit(1000)

    assert panel.info_label.text() == "1,000 rows - 1 columns"


def test_count_failure_omits_the_total_segment():
    panel = DataPreviewPanel()
    window = collect_preview(pl.DataFrame({"n": range(5000)}).lazy(), max_rows=1000)

    panel.controller.previewReady.emit(window)
    panel.controller.countReady.emit(-1)

    assert panel.info_label.text() == "1,000 rows collected - 1 columns"


# -- refresh -----------------------------------------------------------------


def test_refresh_shortcut_is_widget_scoped_ctrl_r():
    panel = DataPreviewPanel()

    assert panel._refresh_shortcut.key() == QKeySequence("Ctrl+R")
    assert panel._refresh_shortcut.context() == Qt.ShortcutContext.WidgetShortcut


def test_refresh_shortcut_re_requests_the_payload():
    panel = DataPreviewPanel()
    df = pl.DataFrame({"n": range(10)})
    panel._payload = df
    requested = _stub_requests(panel)

    panel._refresh_shortcut.activated.emit()

    assert requested == [df]


def test_refresh_without_payload_is_a_noop():
    panel = DataPreviewPanel()
    requested = _stub_requests(panel)

    panel.refresh()

    assert requested == []


def test_set_source_emits_title_changed_once_per_change():
    panel = DataPreviewPanel()
    titles = []
    panel.titleChanged.connect(titles.append)
    requested = _stub_requests(panel)
    df = pl.DataFrame({"n": [1]})

    panel.set_source(df, title="Data Preview - Select")
    panel.set_source(df, title="Data Preview - Select")
    panel.set_source(df, title="Data Preview - Filter")

    assert titles == ["Data Preview - Select", "Data Preview - Filter"]
    assert requested == [df, df, df]


def test_standalone_window_hosts_the_panel():
    window = DataPreviewWindow(pl.DataFrame({"n": range(10)}), "Data Preview - Test")
    try:
        assert window.windowTitle() == "Data Preview - Test"
        panel = window.panel
        assert isinstance(panel, DataPreviewPanel)
        assert _wait_until(
            lambda: panel.viewer.model.total_rows == 10 and not panel.controller.busy
        )
        assert panel.info_label.text() == "10 rows - 1 columns"
    finally:
        window.close()
