#!/usr/bin/env python3
"""DataPreviewPanel: the strip (node, socket, search, counts), states, refresh."""

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

from trigger_designer.qt.models.polars_table_viewer import ALL_COLUMNS_LABEL
from trigger_designer.qt.models.preview_sampling import collect_preview
from trigger_designer.qt.widgets.data_preview_panel import DataPreviewPanel
from trigger_designer.qt.widgets.data_preview_window import DataPreviewWindow

_APP = QApplication.instance() or QApplication([])


def _cities() -> pl.DataFrame:
    """Ten rows, two string columns: 'Berlin' matches three of them."""
    return pl.DataFrame(
        {
            "city": ["Berlin"] * 3 + ["Paris"] * 7,
            "code": [f"C{i}" for i in range(10)],
        }
    )


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
    assert panel.counts_chip.isHidden()
    assert panel.node_chip.isHidden()
    assert not panel.pin_btn.isEnabled()
    assert not panel.search_edit.isEnabled()
    assert not panel.scope_combo.isEnabled()


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
    assert panel.status_label.text() == "0 rows · 1 cols"


def test_failure_state_uses_the_same_label():
    panel = DataPreviewPanel()

    panel.controller.failed.emit("boom")

    assert panel._state_label.text() == "Preview failed: boom"
    assert not panel._state_label.isHidden()
    assert panel._content.isHidden()


def test_empty_state_drops_the_stale_filter_and_counts():
    panel = DataPreviewPanel()
    panel.controller.previewReady.emit(collect_preview(_cities(), max_rows=1000))
    panel.search_edit.setText("Berlin")
    assert _wait_until(lambda: panel.viewer.model.total_rows == 3)

    panel.set_source(None)

    assert panel.search_edit.text() == ""
    assert panel.status_label.text() == ""
    assert not panel.search_edit.isEnabled()

    # The next frame starts unfiltered: nothing of the old query leaks in.
    panel.controller.previewReady.emit(
        collect_preview(pl.DataFrame({"n": range(5)}), max_rows=1000)
    )
    assert panel.viewer.model.total_rows == 5


# -- table, counts chip ------------------------------------------------------


def test_preview_fills_the_table_as_one_page():
    panel = _panel_with(600)

    assert panel._state_label.isHidden()
    assert not panel._content.isHidden()
    assert panel.viewer.model.total_rows == 600
    # No paging: the collected frame is a single page, whole.
    assert panel.viewer.model.page_size == 1000
    assert panel.viewer.model.page_count == 1
    assert panel.viewer.model.rowCount() == 600
    assert panel.status_label.text() == "600 rows · 1 cols"
    assert panel.counts_chip.isVisibleTo(panel)


def test_viewer_is_compact_and_searchless():
    panel = _panel_with(10)

    assert panel.viewer.row_height == 24
    assert panel.viewer.table_view.verticalHeader().defaultSectionSize() == 24
    # The strip drives the filter; the viewer shows no controls of its own.
    assert panel.viewer.combined_panel is None
    assert panel.viewer.search_input is None


def test_counts_pending_then_resolved():
    panel = DataPreviewPanel()
    window = collect_preview(pl.DataFrame({"n": range(5000)}).lazy(), max_rows=1000)
    assert window.limited and window.is_lazy

    panel.controller.previewReady.emit(window)
    assert panel.status_label.text() == "1,000 rows · counting..."
    assert not panel.limited_badge.isHidden()

    panel.controller.countReady.emit(5000)
    assert panel.status_label.text() == "1,000 / 5,000 rows · 1 cols"
    assert not panel.limited_badge.isHidden()


def test_count_equal_to_collected_drops_the_total_segment():
    panel = DataPreviewPanel()
    window = collect_preview(pl.DataFrame({"n": range(1000)}).lazy(), max_rows=1000)

    panel.controller.previewReady.emit(window)
    panel.controller.countReady.emit(1000)

    assert panel.status_label.text() == "1,000 rows · 1 cols"


def test_count_failure_keeps_the_collected_count():
    panel = DataPreviewPanel()
    window = collect_preview(pl.DataFrame({"n": range(5000)}).lazy(), max_rows=1000)

    panel.controller.previewReady.emit(window)
    panel.controller.countReady.emit(-1)

    assert panel.status_label.text() == "1,000 rows · 1 cols"


# -- search ------------------------------------------------------------------


def test_search_filters_after_the_debounce():
    panel = DataPreviewPanel()
    panel.controller.previewReady.emit(collect_preview(_cities(), max_rows=1000))
    assert panel.search_edit.isEnabled()
    assert panel.status_label.text() == "10 rows · 2 cols"

    panel.search_edit.setText("Berlin")

    assert _wait_until(lambda: panel.viewer.model.total_rows == 3)
    assert panel.status_label.text() == "3 / 10 rows · 2 cols"


def test_search_scope_narrows_to_one_column():
    panel = DataPreviewPanel()
    panel.controller.previewReady.emit(collect_preview(_cities(), max_rows=1000))

    assert panel.scope_combo.itemText(0) == ALL_COLUMNS_LABEL
    assert panel.scope_combo.itemText(1) == "city"
    assert panel.scope_combo.itemText(2) == "code"

    panel.search_edit.setText("Berlin")
    assert _wait_until(lambda: panel.viewer.model.total_rows == 3)

    # Same query, one column: the code column holds no 'Berlin'.
    panel.scope_combo.setCurrentText("code")
    assert panel.viewer.model.total_rows == 0

    panel.scope_combo.setCurrentText("city")
    assert panel.viewer.model.total_rows == 3


def test_clearing_the_search_restores_every_row():
    panel = DataPreviewPanel()
    panel.controller.previewReady.emit(collect_preview(_cities(), max_rows=1000))
    panel.search_edit.setText("Berlin")
    assert _wait_until(lambda: panel.viewer.model.total_rows == 3)

    panel.search_edit.setText("")

    assert _wait_until(lambda: panel.viewer.model.total_rows == 10)
    assert panel.status_label.text() == "10 rows · 2 cols"


def test_new_frame_keeps_the_query_and_rebuilds_the_scope():
    panel = DataPreviewPanel()
    panel.controller.previewReady.emit(collect_preview(_cities(), max_rows=1000))
    panel.search_edit.setText("Berlin")
    assert _wait_until(lambda: panel.viewer.model.total_rows == 3)

    # A new node with other columns: the query stays, the scope resets.
    frame = pl.DataFrame({"name": ["Berlin", "Lisbon"]})
    panel.controller.previewReady.emit(collect_preview(frame, max_rows=1000))

    assert panel.search_edit.text() == "Berlin"
    assert panel.viewer.model.total_rows == 1
    assert panel.scope_combo.currentText() == ALL_COLUMNS_LABEL
    assert panel.scope_combo.count() == 2


# -- strip: node, socket, pin ------------------------------------------------


def test_set_node_shows_the_chip_and_pin_state():
    panel = DataPreviewPanel()

    panel.set_node("Cleansing", pinned=False, enabled=True)
    assert not panel.node_chip.isHidden()
    assert panel.node_label.text() == "Cleansing"
    assert panel.pin_btn.isEnabled()
    assert not panel.pin_btn.isChecked()
    assert panel._pin_dot.isHidden()

    panel.set_node("Select", pinned=True, enabled=True)
    assert panel.pin_btn.isChecked()
    assert not panel._pin_dot.isHidden()
    assert panel.pin_btn.toolTip() == "Unpin this node"

    panel.set_node(None)
    assert panel.node_chip.isHidden()
    assert not panel.pin_btn.isEnabled()
    assert not panel.pin_btn.isChecked()


def test_long_node_titles_elide_with_a_tooltip():
    panel = DataPreviewPanel()
    title = "Dynamic Row Builder With A Very Long Descriptive Name"

    panel.set_node(title, enabled=True)

    assert panel.node_label.text() != title
    assert "…" in panel.node_label.text()
    assert panel.node_label.toolTip() == title


def test_pin_toggle_reports_out():
    panel = DataPreviewPanel()
    panel.set_node("Cleansing", enabled=True)
    seen: list = []
    panel.pinned.connect(seen.append)

    panel.pin_btn.click()

    assert seen == [True]
    assert panel.pin_btn.toolTip() == "Unpin this node"


def test_socket_chip_only_for_several_outputs():
    panel = DataPreviewPanel()
    seen: list = []
    panel.socketChanged.connect(seen.append)

    panel.set_sockets(["out 1"])
    assert panel.socket_chip.isHidden()

    panel.set_sockets(["out 1", "left"], 1)
    assert not panel.socket_chip.isHidden()
    assert panel.socket_combo.currentText() == "left"
    assert seen == []

    panel.socket_combo.setCurrentIndex(0)
    assert seen == [0]

    panel.set_sockets([])
    assert panel.socket_chip.isHidden()


# -- options menu, refresh ---------------------------------------------------


def test_options_menu_follows_the_data_state():
    panel = DataPreviewPanel()

    panel._sync_options_menu()
    assert not panel.export_csv_action.isEnabled()
    assert not panel.copy_action.isEnabled()

    panel.controller.previewReady.emit(collect_preview(_cities(), max_rows=1000))
    panel._sync_options_menu()
    assert panel.export_csv_action.isEnabled()
    assert panel.copy_action.isEnabled()


def test_refresh_shortcut_is_widget_scoped_ctrl_r():
    panel = DataPreviewPanel()

    assert panel._refresh_shortcut.key() == QKeySequence("Ctrl+R")
    assert panel._refresh_shortcut.context() == Qt.ShortcutContext.WidgetShortcut


def test_find_shortcut_is_widget_scoped_ctrl_f():
    panel = DataPreviewPanel()

    assert panel._find_shortcut.key() == QKeySequence("Ctrl+F")
    assert panel._find_shortcut.context() == Qt.ShortcutContext.WidgetShortcut


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


def test_refresh_button_follows_payload_and_busy():
    panel = DataPreviewPanel()
    assert not panel.refresh_btn.isEnabled()

    df = pl.DataFrame({"n": range(10)})
    panel._payload = df
    panel._sync_refresh_enabled()
    assert panel.refresh_btn.isEnabled()

    panel.controller._busy = True
    panel._sync_refresh_enabled()
    assert not panel.refresh_btn.isEnabled()


def test_standalone_window_hosts_the_panel():
    window = DataPreviewWindow(pl.DataFrame({"n": range(10)}), "Data Preview - Test")
    try:
        assert window.windowTitle() == "Data Preview - Test"
        panel = window.panel
        assert isinstance(panel, DataPreviewPanel)
        assert _wait_until(
            lambda: panel.viewer.model.total_rows == 10 and not panel.controller.busy
        )
        assert panel.status_label.text() == "10 rows · 1 cols"
        # A standalone window tracks no node: chip and pin stay out of sight.
        assert panel.node_chip.isHidden()
        assert not panel.pin_btn.isEnabled()
    finally:
        window.close()
