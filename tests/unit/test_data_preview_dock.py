#!/usr/bin/env python3
"""DataPreviewDock: follow / pin / socket choice, per-window state, coalescing."""

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.docks.data_preview import DataPreviewDock

_APP = QApplication.instance() or QApplication([])


# -- stand-ins for the design window -----------------------------------------


class _GraphicsSocket:
    """nodeeditor's socket graphic: it holds the label the node passed."""

    def __init__(self, text: str = "") -> None:
        self._text = text


class _Socket:
    def __init__(self, text: str = "") -> None:
        self.grSocket = _GraphicsSocket(text)


class _Node:
    def __init__(
        self, title: str, labels: list[str] | None = None, values: list | None = None
    ) -> None:
        self.title = title
        self.outputs = [_Socket(label) for label in (labels or [""])]
        self.value = values


class _Item:
    """A graphics item: nodes are reached through it, sockets stop there."""

    def __init__(self, node: _Node) -> None:
        self.node = node


class _SocketItem:
    def __init__(self) -> None:
        self.socket = object()


class _ConfigDock:
    def __init__(self) -> None:
        self.node = None

    def currentNode(self):
        return self.node


class _Scene:
    def __init__(self) -> None:
        self.nodes: list = []


class _Window:
    """A TriggerSubWindow with just the surface the dock touches."""

    def __init__(self, title: str = "Design 1") -> None:
        self._title = title
        self.config_dock = _ConfigDock()
        self.scene = _Scene()
        self.execution_results: dict = {}
        self.selected: list = []

    def windowTitle(self) -> str:
        return self._title

    def _find_config_dock(self) -> _ConfigDock:
        return self.config_dock

    def getSelectedItems(self) -> list:
        return self.selected

    def getSocketData(self, node: _Node, index: int):
        return self.execution_results.get(node, {}).get(f"var{index}")


def _envelope(rows: int, column: str = "n") -> dict:
    return {"data": pl.DataFrame({column: range(rows)}), "variable_name": column}


def _node(title: str, labels: list[str] | None = None, rows: list[int] | None = None):
    values = [_envelope(count) for count in rows] if rows is not None else None
    return _Node(title, labels, values)


def _select(window: _Window, node: _Node) -> None:
    """Select ``node`` in the window and register it in its scene."""
    window.selected = [_Item(node)]
    if node not in window.scene.nodes:
        window.scene.nodes.append(node)


# -- helpers -----------------------------------------------------------------


def _stub_requests(panel) -> list:
    """Keep set_source/refresh thread-free; records the requested payloads."""
    requested: list = []
    panel.controller.request = requested.append
    return requested


def _dock() -> tuple[DataPreviewDock, list]:
    dock = DataPreviewDock()
    return dock, _stub_requests(dock.panel)


def _wait_until(predicate, timeout_ms: int = 10_000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    QApplication.processEvents()
    return predicate()


# -- follow / pin ------------------------------------------------------------


def test_initial_state_is_blind_and_empty():
    dock, _ = _dock()

    assert dock.windowTitle() == "Data Preview"
    assert dock.title_label.text() == "Data Preview"
    assert dock.socket_combo.isHidden()
    assert not dock.pin_btn.isEnabled()
    assert not dock.refresh_btn.isEnabled()
    assert dock.panel._state_label.text() == "Select a node to preview its output"


def test_switch_follows_the_config_dock_node_and_titles_the_dock():
    dock, requested = _dock()
    window = _Window("Preparation")
    node = _node("Select", rows=[3])
    window.config_dock.node = node

    dock.switch_to_design_window(window)

    assert dock.windowTitle() == "Data Preview - Preparation"
    assert dock.title_label.text() == "Data Preview - Select"
    assert requested[-1] is node.value[0]["data"]
    assert dock.pin_btn.isEnabled()
    assert dock.refresh_btn.isEnabled()


def test_selection_is_used_when_the_config_dock_is_empty_and_sockets_skipped():
    dock, requested = _dock()
    window = _Window()
    node = _node("Filter", rows=[4])
    window.selected = [_SocketItem(), _Item(node)]
    window.scene.nodes.append(node)

    dock.switch_to_design_window(window)

    assert requested[-1] is node.value[0]["data"]
    assert dock.title_label.text() == "Data Preview - Filter"


def test_selection_change_switches_the_preview():
    dock, requested = _dock()
    window = _Window()
    first = _node("Select", rows=[2])
    second = _node("Filter", rows=[5])
    window.config_dock.node = first
    dock.switch_to_design_window(window)

    window.config_dock.node = second
    dock.note_selection_changed(window)
    assert requested[-1] is second.value[0]["data"]

    window.config_dock.node = None
    _select(window, first)
    dock.note_selection_changed(window)
    assert requested[-1] is first.value[0]["data"]


def test_clearing_the_selection_blanks_the_panel():
    dock, requested = _dock()
    window = _Window()
    window.config_dock.node = _node("Select", rows=[2])
    dock.switch_to_design_window(window)
    before = len(requested)

    window.config_dock.node = None
    window.selected = []
    dock.note_selection_changed(window)

    assert len(requested) == before
    assert dock.panel._state_label.text() == "Select a node to preview its output"
    assert dock.title_label.text() == "Data Preview"
    assert not dock.pin_btn.isEnabled()
    assert not dock.refresh_btn.isEnabled()


def test_pin_freezes_the_node_until_it_is_unpinned():
    dock, requested = _dock()
    window = _Window()
    pinned = _node("Select", rows=[2])
    other = _node("Filter", rows=[5])
    window.config_dock.node = pinned
    _select(window, pinned)
    dock.switch_to_design_window(window)

    dock.pin_btn.setChecked(True)
    assert dock.pin_btn.isChecked()

    window.config_dock.node = other
    dock.note_selection_changed(window)
    assert requested[-1] is pinned.value[0]["data"]

    dock.pin_btn.setChecked(False)
    assert not dock.pin_btn.isChecked()
    assert requested[-1] is other.value[0]["data"]


def test_pinned_node_leaving_the_scene_unpins_with_a_note():
    dock, requested = _dock()
    window = _Window()
    node = _node("Select", rows=[2])
    window.config_dock.node = node
    _select(window, node)
    dock.switch_to_design_window(window)
    dock.pin_btn.setChecked(True)
    before = len(requested)

    window.scene.nodes.remove(node)
    window.config_dock.node = None
    window.selected = []
    dock.note_selection_changed(window)

    assert not dock.pin_btn.isChecked()
    assert len(requested) == before
    assert "no longer in the scene" in dock.panel._state_label.text()

    # The next selection follows again.
    other = _node("Filter", rows=[5])
    _select(window, other)
    window.config_dock.node = other
    dock.note_selection_changed(window)
    assert requested[-1] is other.value[0]["data"]


# -- per-window state --------------------------------------------------------


def test_pins_are_kept_per_window():
    dock, requested = _dock()
    first_window = _Window("First")
    second_window = _Window("Second")
    pinned = _node("Select", rows=[2])
    followed = _node("Filter", rows=[9])
    _select(first_window, pinned)
    _select(second_window, followed)
    first_window.config_dock.node = pinned
    second_window.config_dock.node = followed

    dock.switch_to_design_window(first_window)
    dock.pin_btn.setChecked(True)

    dock.switch_to_design_window(second_window)
    assert not dock.pin_btn.isChecked()
    assert requested[-1] is followed.value[0]["data"]

    dock.switch_to_design_window(first_window)
    assert dock.pin_btn.isChecked()
    assert requested[-1] is pinned.value[0]["data"]


def test_remove_design_window_clears_only_that_window():
    dock, requested = _dock()
    first_window = _Window("First")
    second_window = _Window("Second")
    pinned = _node("Select", rows=[2])
    followed = _node("Filter", rows=[9])
    _select(first_window, pinned)
    _select(second_window, followed)
    first_window.config_dock.node = pinned
    second_window.config_dock.node = followed
    dock.switch_to_design_window(first_window)
    dock.pin_btn.setChecked(True)

    dock.switch_to_design_window(second_window)
    dock.remove_design_window(str(id(second_window)))

    assert str(id(second_window)) not in dock._states
    assert dock.windowTitle() == "Data Preview"
    assert dock.panel._state_label.text() == "Select a node to preview its output"
    assert str(id(first_window)) in dock._states

    dock.switch_to_design_window(first_window)
    assert dock.pin_btn.isChecked()
    assert requested[-1] is pinned.value[0]["data"]


def test_hooks_of_another_window_are_ignored():
    dock, requested = _dock()
    current = _Window("Current")
    other = _Window("Other")
    current.config_dock.node = _node("Select", rows=[2])
    other.config_dock.node = _node("Filter", rows=[7])
    dock.switch_to_design_window(current)
    before = len(requested)

    dock.note_selection_changed(other)
    dock.note_node_evaluated(other, other.config_dock.node)
    dock.note_run_finished(other)

    assert len(requested) == before


# -- sockets -----------------------------------------------------------------


def test_socket_combo_is_hidden_for_a_single_output():
    dock, _ = _dock()
    window = _Window()
    window.config_dock.node = _node("Select", rows=[2])

    dock.switch_to_design_window(window)

    assert dock.socket_combo.isHidden()
    assert dock.socket_combo.count() == 1


def test_socket_combo_choice_requests_that_socket():
    dock, requested = _dock()
    window = _Window()
    node = _node("Join", labels=["L", "J", "R"], rows=[1, 2, 3])
    window.config_dock.node = node
    dock.switch_to_design_window(window)

    assert not dock.socket_combo.isHidden()
    assert [dock.socket_combo.itemText(i) for i in range(3)] == ["L", "J", "R"]
    assert requested[-1] is node.value[0]["data"]

    dock.socket_combo.setCurrentIndex(2)
    assert requested[-1] is node.value[2]["data"]


def test_socket_choice_resets_for_another_node():
    dock, requested = _dock()
    window = _Window()
    joined = _node("Join", labels=["L", "J"], rows=[1, 2])
    other = _node("Filter", rows=[5])
    window.config_dock.node = joined
    dock.switch_to_design_window(window)
    dock.socket_combo.setCurrentIndex(1)
    assert requested[-1] is joined.value[1]["data"]

    window.config_dock.node = other
    dock.note_selection_changed(window)

    assert dock.socket_combo.currentIndex() == 0
    assert requested[-1] is other.value[0]["data"]


# -- empty and failure states ------------------------------------------------


def test_no_output_on_the_socket_shows_the_empty_state():
    dock, requested = _dock()
    window = _Window()
    window.config_dock.node = _node("Select")

    dock.switch_to_design_window(window)

    assert requested == []
    assert dock.panel._state_label.text() == "No previewable data on this socket"
    assert dock.title_label.text() == "Data Preview - Select"
    assert dock.pin_btn.isEnabled()
    assert not dock.refresh_btn.isEnabled()


def test_non_tabular_output_counts_as_no_data():
    dock, _ = _dock()
    window = _Window()
    window.config_dock.node = _Node("Graph", [""], [{"data": pl.Series([1, 2])}])

    dock.switch_to_design_window(window)

    assert dock.panel._state_label.text() == "No previewable data on this socket"


def test_collect_failure_is_reported_by_the_panel():
    dock, _ = _dock()

    dock.panel.controller.failed.emit("boom")

    assert dock.panel._state_label.text() == "Preview failed: boom"


def test_untitled_node_falls_back_to_its_class_name():
    dock, _ = _dock()
    window = _Window()
    window.config_dock.node = _Node("", None, None)

    dock.switch_to_design_window(window)

    assert dock.title_label.text() == "Data Preview - _Node"


# -- evaluation and runs -----------------------------------------------------


def test_eval_refresh_is_coalesced_and_only_for_the_shown_node():
    dock, requested = _dock()
    window = _Window()
    node = _node("Select", rows=[2])
    window.config_dock.node = node
    dock.switch_to_design_window(window)
    assert len(requested) == 1

    for _ in range(3):
        dock.note_node_evaluated(window, node)
    assert _wait_until(lambda: len(requested) == 2)
    assert len(requested) == 2
    assert requested[-1] is node.value[0]["data"]

    other = _node("Filter", rows=[5])
    dock.note_node_evaluated(window, other)
    assert not _wait_until(lambda: len(requested) > 2, timeout_ms=400)


def test_eval_of_the_config_dock_node_refreshes_the_pinned_preview():
    dock, requested = _dock()
    window = _Window()
    pinned = _node("Select", rows=[2])
    edited = _node("Filter", rows=[5])
    window.config_dock.node = pinned
    _select(window, pinned)
    dock.switch_to_design_window(window)
    dock.pin_btn.setChecked(True)

    window.config_dock.node = edited
    dock.note_node_evaluated(window, edited)

    assert _wait_until(lambda: len(requested) == 2)
    assert requested[-1] is pinned.value[0]["data"]


def test_run_finished_pulls_results_from_the_run_store():
    dock, requested = _dock()
    window = _Window()
    node = _node("Select")
    window.config_dock.node = node
    dock.switch_to_design_window(window)
    assert requested == []

    window.execution_results = {node: {"var0": _envelope(4)}}
    dock.note_run_finished(window)

    assert requested[-1] is window.execution_results[node]["var0"]["data"]


def test_run_finished_keeps_the_shown_node_when_nothing_is_selected():
    dock, requested = _dock()
    window = _Window()
    node = _node("Select", rows=[2])
    window.config_dock.node = node
    dock.switch_to_design_window(window)

    window.config_dock.node = None
    window.selected = []
    dock.note_run_finished(window)

    assert requested[-1] is node.value[0]["data"]


# -- header controls ---------------------------------------------------------


def test_refresh_button_follows_the_busy_signal():
    dock, _ = _dock()
    window = _Window()
    window.config_dock.node = _node("Select", rows=[2])
    dock.switch_to_design_window(window)
    assert dock.refresh_btn.isEnabled()

    dock.panel.controller.busyChanged.emit(True)
    assert not dock.refresh_btn.isEnabled()

    dock.panel.controller.busyChanged.emit(False)
    assert dock.refresh_btn.isEnabled()


def test_options_menu_tracks_payload_and_pin():
    dock, _ = _dock()
    window = _Window()
    window.config_dock.node = _node("Select", rows=[2])

    dock.options_menu.aboutToShow.emit()
    assert not dock.export_csv_action.isEnabled()
    assert not dock.open_window_action.isEnabled()
    assert not dock.unpin_action.isEnabled()

    dock.switch_to_design_window(window)
    dock.options_menu.aboutToShow.emit()
    assert dock.export_csv_action.isEnabled()
    assert dock.export_excel_action.isEnabled()
    assert dock.open_window_action.isEnabled()
    assert not dock.unpin_action.isEnabled()

    dock.pin_btn.setChecked(True)
    dock.options_menu.aboutToShow.emit()
    assert dock.unpin_action.isEnabled()


def test_newest_selection_wins_with_a_collect_in_flight():
    dock = DataPreviewDock()
    window = _Window("Live")
    first = _node("Select", rows=[2])
    second = _node("Filter", rows=[5])
    window.config_dock.node = first

    dock.switch_to_design_window(window)
    window.config_dock.node = second
    dock.note_selection_changed(window)

    assert _wait_until(
        lambda: (
            dock.panel.viewer.model.rowCount() == 5 and not dock.panel.controller.busy
        )
    )
    assert "5 rows" in dock.panel.info_label.text()


def test_switch_re_reads_the_window_state():
    dock = DataPreviewDock()
    window = _Window("Live")
    window.config_dock.node = _node("Select", rows=[3])
    dock.switch_to_design_window(window)
    assert _wait_until(
        lambda: (
            dock.panel.viewer.model.rowCount() == 3 and not dock.panel.controller.busy
        )
    )

    dock.switch_to_design_window(window)
    assert dock.title_label.text() == "Data Preview - Select"
    assert _wait_until(
        lambda: (
            dock.panel.viewer.model.rowCount() == 3 and not dock.panel.controller.busy
        )
    )
