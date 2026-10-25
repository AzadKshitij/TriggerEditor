#!/usr/bin/env python3
"""The Graph Config Dock: the editor half of the node.

The regression these guard: every dock rebuild used to clear and refill the
column combos while their change handlers were connected, so merely selecting
the node (or any upstream evaluation) overwrote the saved X/Y with the first
columns - and the next save quietly wrote ``graph_type=bar, x=y=a`` over the
user's chart.

Also pinned here: a schema refresh keeps the selection, Show graph unlocks only
after a successful run, and the non-modal chart window follows later setting
edits through the debounce.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import copy

import polars as pl
import pytest
from qtpy.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from tests.support.qt_widgets import dispose_plot_widget
from trigger_designer.core.node_configuration import (
    NodeTypes,
    ReportNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

APP = QApplication.instance() or QApplication([])

#: Contents built by this module, so teardown can dispose their chart windows.
_BUILT: list = []


@pytest.fixture(autouse=True)
def _dispose_chart_windows():
    """Delete chart windows before the shared leak fixture batches widgets.

    A chart window owns a matplotlib canvas; releasing it before the batch
    keeps teardown deterministic. See ``tests/support/qt_widgets.py``.
    """
    yield
    while _BUILT:
        content = _BUILT.pop()
        dispose_plot_widget(getattr(content, "_chart_window", None))


#: Columns ordered so "the first two columns" is never the right answer.
FRAME = pl.DataFrame(
    {
        "a": [1.0, 2.0, 3.0, 4.0],
        "b": [10, 20, 10, 20],
        "g": ["x", "x", "y", "y"],
        "c": [1, 2, 3, 4],
    }
)

SAVED = {
    "graph_type": "bar",
    "x_column": "b",
    "y_column": "a",
    "color_column": "g",
    "aggregation": "mean",
    "title": "Saved title",
}


def _graph(frame=FRAME, saved=None):
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    cls = get_class_from_opcode(ReportNodes.GRAPH, NodeTypes.REPORT)
    node = cls(window.scene)
    window.scene.nodes.append(node)
    content = node.content
    for name, value in (saved or {}).items():
        setattr(content, name, value)
    if frame is not None:
        content.incom_data = frame
        content.incoming_variable = "var_in"
    return {"parent": parent, "window": window, "node": node, "content": content}


def _build(refs):
    """Build the dock layout the way ConfigDock does, suspension included.

    The host widget is kept on the content: dropping the ``refs`` dict would
    otherwise let Qt delete the host (and every control with it) while the
    test still holds the content.
    """
    host = QWidget()
    content = refs["content"]
    content._suspend_input_tracking = True
    content.create_layout(QVBoxLayout(host))
    content._suspend_input_tracking = False
    content._dock_host = host
    refs["host"] = host
    _BUILT.append(content)
    return refs


def test_dock_projects_saved_settings_without_touching_them() -> None:
    refs = _graph(saved=SAVED)
    before = copy.deepcopy(refs["content"].serialize())

    content = _build(refs)["content"]

    assert content.graph_type_combo.currentText() == "Bar"
    assert content.x_column_combo.currentText() == "b"
    assert content.y_column_combo.currentText() == "a"
    assert content.color_column_combo.currentText() == "g"
    assert content.aggregation_combo.currentText() == "Mean"
    assert content.title_edit.text() == "Saved title"

    assert content.serialize() == before


def test_schema_refresh_keeps_the_selection() -> None:
    content = _build(_graph(saved=SAVED))["content"]
    before = copy.deepcopy(content.serialize())

    content.incom_data = pl.DataFrame(
        {"g": ["x"], "a": [1.0], "b": [2], "c": [3], "new": [4]}
    ).lazy()
    content.update_column_options()

    assert (content.x_column, content.y_column) == ("b", "a")
    assert content.color_column == "g"
    assert content.x_column_combo.currentText() == "b"
    assert content.y_column_combo.currentText() == "a"
    assert content.color_column_combo.currentText() == "g"
    assert content.serialize() == before


def test_removed_column_falls_back_and_shows_the_fallback() -> None:
    content = _build(_graph(saved={"x_column": "b", "y_column": "a"}))["content"]

    content.incom_data = pl.DataFrame({"c": [3, 4], "a": [1, 2]}).lazy()
    content.update_column_options()

    assert content.x_column == "c"
    assert content.y_column == "a"
    assert content.x_column_combo.currentText() == "c"


def test_no_data_leaves_the_saved_selection_alone() -> None:
    content = _build(
        _graph(
            frame=None, saved={"x_column": "b", "y_column": "a", "color_column": "g"}
        )
    )["content"]

    assert (content.x_column, content.y_column, content.color_column) == ("b", "a", "g")
    assert content.x_column_combo.count() == 0

    # The upstream evaluates later; the saved names are still the selection.
    content.incom_data = FRAME
    content.update_column_options()

    assert content.x_column_combo.currentText() == "b"
    assert content.y_column_combo.currentText() == "a"


def test_open_window_follows_setting_edits_after_the_debounce(qtbot) -> None:
    refs = _build(_graph(saved=SAVED))
    content = refs["content"]
    content.after_execution({content.variable_name: FRAME.lazy()})
    content.open_graph_in_new_window()
    window = content._chart_window

    content.x_column_combo.setCurrentText("c")

    qtbot.waitUntil(lambda: window.chart_view.spec.x_column == "c", timeout=3000)
    assert window.chart_view.spec.renderable


def test_show_graph_button_unlocks_only_after_a_run() -> None:
    content = _build(_graph(saved=SAVED))["content"]

    assert content.open_graph_button.isEnabled() is False
    assert content.open_graph_button.toolTip() == "Show graph (run the workflow first)"

    content.after_execution({content.variable_name: FRAME.lazy()})
    APP.processEvents()

    assert content.workflow_ran_successfully is True
    assert content.open_graph_button.isEnabled() is True
    assert content.open_graph_button.toolTip() == "Show graph"
    assert content.open_graph_button.accessibleName() == "Show graph"


def test_show_graph_button_reports_a_run_without_data() -> None:
    refs = _graph(frame=None, saved={"x_column": "b", "y_column": "a"})
    content = _build(refs)["content"]

    content.after_execution({})
    APP.processEvents()

    assert content.workflow_ran_successfully is True
    assert content.open_graph_button.isEnabled() is False
    assert content.open_graph_button.toolTip() == "Show graph (no data to draw)"


def test_open_before_a_run_is_ignored() -> None:
    content = _build(_graph(saved=SAVED))["content"]

    content.open_graph_in_new_window()

    assert content._chart_window is None


def test_setting_edits_do_not_relock_the_button() -> None:
    content = _build(_graph(saved=SAVED))["content"]
    content.after_execution({content.variable_name: FRAME.lazy()})
    APP.processEvents()

    content.graph_type_combo.setCurrentText("Line")
    APP.processEvents()

    assert content.open_graph_button.isEnabled() is True


def test_run_frame_reaches_the_click_before_the_gui_signal() -> None:
    # ``after_execution`` runs on the workflow worker and queues its slot.
    # If that slot never runs, the click must still chart the frame the run
    # handed over - otherwise a successful run leaves a dead button.
    refs = _graph(frame=None, saved=SAVED)
    content = _build(refs)["content"]

    content.runDataReady.disconnect(content._on_run_data_ready)
    content.after_execution({content.variable_name: FRAME.lazy()})
    content.runDataReady.connect(content._on_run_data_ready)
    assert content.incom_data is None

    content.open_graph_in_new_window()

    window = content._chart_window
    assert window is not None
    assert window.chart_view.spec is not None
    assert window.chart_view.spec.renderable
    window.close()


def test_dock_rebuild_after_a_run_keeps_the_button_live() -> None:
    refs = _graph(saved=SAVED)
    content = _build(refs)["content"]
    content.after_execution({content.variable_name: FRAME.lazy()})
    APP.processEvents()
    assert content.open_graph_button.isEnabled() is True

    # Selecting the node again rebuilds every control from scratch.
    _build(refs)

    assert content.open_graph_button.isEnabled() is True
    assert content.open_graph_button.toolTip() == "Show graph"


def test_a_latched_click_never_silently_does_nothing() -> None:
    # The run happened but handed over no frame: the window opens on its
    # message page rather than the click vanishing without a trace.
    content = _build(_graph(frame=None, saved=SAVED))["content"]

    content.after_execution({})
    APP.processEvents()
    assert content.open_graph_button.isEnabled() is False

    content.open_graph_in_new_window()

    window = content._chart_window
    assert window is not None
    assert window.chart_view.showing_message is True
    window.close()


def test_chart_window_is_non_modal_and_reused() -> None:
    content = _build(_graph(saved=SAVED))["content"]
    content.after_execution({content.variable_name: FRAME.lazy()})
    APP.processEvents()

    content.open_graph_in_new_window()
    window = content._chart_window

    assert window is not None
    assert window.isModal() is False
    assert all(action.text() != "Subplots" for action in window.toolbar.actions())
    assert window.chart_view.spec == content.build_spec()
    assert window.windowTitle() == "Graph \u2014 Saved title"
    status = window.status_label.text()
    assert status.startswith("4 points")
    assert "mean of a per b" in status
    assert "colored by g" in status

    content.open_graph_in_new_window()
    assert content._chart_window is window
    window.close()


def test_undo_restores_the_widget_from_the_model() -> None:
    refs = _build(_graph(saved={"graph_type": "bar"}))
    content = refs["content"]
    history = refs["window"].scene.history
    assert content.graph_type_combo.currentText() == "Bar"

    assert content.push_property_change(("graph_type",), "bar", "line", "Graph type")
    assert history.controller.count == 1

    history.undo()
    APP.processEvents()

    assert content.graph_type == "bar"
    assert content.graph_type_combo.currentText() == "Bar"


def test_renderer_round_trips_and_old_files_default_to_matplotlib() -> None:
    content = _build(_graph(saved=SAVED))["content"]
    assert content.renderer == "matplotlib"
    assert content.renderer_combo.currentText() == "matplotlib"

    content.renderer_combo.setCurrentText("pyqtgraph")
    state = copy.deepcopy(content.serialize())
    assert state["renderer"] == "pyqtgraph"

    content.renderer = "matplotlib"
    content.deserialize_content_state(state)
    content._sync_widgets_from_model()
    assert content.renderer == "pyqtgraph"
    assert content.renderer_combo.currentText() == "pyqtgraph"

    # A .tds saved before the setting existed carries no key at all.
    old_file = {key: value for key, value in state.items() if key != "renderer"}
    content.renderer = "matplotlib"
    content.deserialize_content_state(old_file)
    content._sync_widgets_from_model()
    assert content.renderer == "matplotlib"
    assert content.renderer_combo.currentText() == "matplotlib"


def test_undo_restores_the_renderer_widget_from_the_model() -> None:
    refs = _build(_graph(saved={}))
    content = refs["content"]
    history = refs["window"].scene.history
    assert content.renderer_combo.currentText() == "matplotlib"

    assert content.push_property_change(
        ("renderer",), "matplotlib", "pyqtgraph", "Graph renderer"
    )
    assert history.controller.count == 1
    assert content.renderer == "pyqtgraph"

    history.undo()
    APP.processEvents()

    assert content.renderer == "matplotlib"
    assert content.renderer_combo.currentText() == "matplotlib"


def test_renderer_switch_swaps_the_open_window_and_its_title(qtbot) -> None:
    from trigger_designer.qt.widgets.nodes.Report.pyqtgraph_view import (
        PyqtgraphChartView,
    )

    refs = _build(_graph(saved=SAVED))
    content = refs["content"]
    content.after_execution({content.variable_name: FRAME.lazy()})
    content.open_graph_in_new_window()
    window = content._chart_window
    assert window.renderer == "matplotlib"
    assert window.windowTitle() == "Graph \u2014 Saved title"

    content.renderer_combo.setCurrentText("pyqtgraph")

    qtbot.waitUntil(lambda: window.renderer == "pyqtgraph", timeout=3000)
    assert isinstance(window.chart_view, PyqtgraphChartView)
    assert window.windowTitle() == "Graph \u2014 Saved title (pyqtgraph)"
    qtbot.waitUntil(
        lambda: (
            window.chart_view.spec is not None and window.chart_view.spec.renderable
        ),
        timeout=3000,
    )
    assert window.toolbar is not None
    window.close()


def test_aggregation_widget_surfaces_the_type_default_while_auto() -> None:
    content = _build(_graph(saved={}))["content"]

    assert content.aggregation_combo.currentText() == "None"
    assert content.aggregation == ""

    content.graph_type_combo.setCurrentText("Bar")

    assert content.aggregation_combo.currentText() == "Sum"
    assert content.aggregation == ""
