#!/usr/bin/env python3
"""The Graph node's data contract, without the Config Dock.

Three defects used to live here:

* the output socket returned an empty list, because ``processInputs`` stored
  ``content.data`` (never updated) instead of the incoming frame;
* the generated code called ``plt.show()`` on the workflow worker thread,
  which popped a window and blocked headless runs;
* an old dock rebuild could overwrite the saved X/Y before the next save.

The dock half lives in ``tests/ui/test_graph_dock.py``; this file pins the
node-side contract: pass-through output, data-only code generation, run data
published through a signal, a lossless serialization round trip, and a chart
backend that stays out of the startup import sweep.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import copy
import subprocess

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QApplication, QMainWindow

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    ReportNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode

APP = QApplication.instance() or QApplication([])


class _Stub(TriggerNode):
    """Source node evaluating to a fixed frame."""

    def evalImplementation(self):
        return [{"data": self._df, "variable_name": self._var}]


def _graph_node(scene):
    cls = get_class_from_opcode(ReportNodes.GRAPH, NodeTypes.REPORT)
    return cls(scene)


def _wired_graph(df):
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    scene = window.scene
    stub = _Stub(scene, inputs=[], outputs=[3])
    stub._df, stub._var = df, "var_up"
    stub.markDirty(True)
    graph = _graph_node(scene)
    Edge(scene, stub.outputs[0], graph.inputs[0])
    graph.eval()
    APP.processEvents()
    return {"parent": parent, "window": window, "stub": stub, "graph": graph}


def _rename_headless(content, mapping):
    """Rename through the Select settings path and re-evaluate."""
    columns = [dict(column) for column in content.settings["columns"]]
    for column in columns:
        if column["name"] in mapping:
            column["rename"] = mapping[column["name"]]
    content.set_setting("columns", columns, "Select Columns Changed")
    content.node.markDirty(True)
    content.node.eval()
    APP.processEvents()


def test_output_socket_carries_the_incoming_frame() -> None:
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]}).lazy()
    refs = _wired_graph(df)
    graph = refs["graph"]

    assert graph.param, "evaluation produced no output"
    forwarded = graph.param[0]["data"]
    assert forwarded is not None
    assert forwarded.collect().equals(df.collect())
    assert graph.content.incom_data is not None


def test_saved_settings_survive_serialize_and_deserialize() -> None:
    refs = _wired_graph(pl.DataFrame({"a": [1], "b": [2]}).lazy())
    content = refs["graph"].content
    content.graph_type = "bar"
    content.x_column = "b"
    content.y_column = "a"
    content.title = "Saved title"
    content.aggregation = "mean"
    payload = copy.deepcopy(content.serialize())

    fresh = _graph_node(refs["window"].scene)
    fresh.content.deserialize(payload)

    assert fresh.content.graph_type == "bar"
    assert fresh.content.x_column == "b"
    assert fresh.content.y_column == "a"
    assert fresh.content.title == "Saved title"
    assert fresh.content.aggregation == "mean"
    assert fresh.content.serialize() == payload


def test_payload_predating_new_fields_still_loads() -> None:
    refs = _wired_graph(pl.DataFrame({"a": [1], "b": [2]}).lazy())
    content = refs["graph"].content
    content.graph_type = "bar"
    content.x_column = "b"
    content.y_column = "a"
    payload = copy.deepcopy(content.serialize())
    payload.pop("color_column", None)
    payload.pop("aggregation", None)

    fresh = _graph_node(refs["window"].scene)
    fresh.content.deserialize(payload)

    assert fresh.content.graph_type == "bar"
    assert fresh.content.x_column == "b"
    assert fresh.content.y_column == "a"
    assert fresh.content.color_column == ""
    assert fresh.content.aggregation == ""


def test_generated_code_is_data_only() -> None:
    refs = _wired_graph(pl.DataFrame({"a": [1]}).lazy())
    content = refs["graph"].content

    code = content.get_code()

    assert "matplotlib" not in code
    assert "plt" not in code
    assert f"{content.variable_name} = {content.incoming_variable}" in code
    assert "pl.DataFrame()" not in code


def test_generated_code_without_input_still_defines_the_output() -> None:
    refs = _wired_graph(pl.DataFrame({"a": [1]}).lazy())
    orphan = _graph_node(refs["window"].scene)

    code = orphan.content.get_code()

    assert "pl.DataFrame()" in code
    assert orphan.content.variable_name in code


def test_run_data_is_announced_and_adopted() -> None:
    refs = _wired_graph(pl.DataFrame({"a": [1, 2]}).lazy())
    content = refs["graph"].content
    seen = []
    content.runDataReady.connect(seen.append)
    run_frame = pl.DataFrame({"a": [9], "b": [8]}).lazy()

    content.after_execution({content.variable_name: run_frame})

    assert seen == [run_frame]
    assert content.incom_data is run_frame
    assert content.workflow_ran_successfully is True


def test_run_without_a_frame_is_still_announced() -> None:
    refs = _wired_graph(pl.DataFrame({"a": [1]}).lazy())
    content = refs["graph"].content
    seen = []
    content.runDataReady.connect(seen.append)

    content.after_execution({})

    assert seen == [None]


def test_run_data_keeps_a_selection_whose_columns_survive() -> None:
    refs = _wired_graph(pl.DataFrame({"a": [1], "b": [2]}).lazy())
    content = refs["graph"].content
    content.x_column = "b"
    content.y_column = "a"

    content.after_execution(
        {content.variable_name: pl.DataFrame({"a": [3], "b": [4], "c": [5]}).lazy()}
    )

    assert content.x_column == "b"
    assert content.y_column == "a"


def test_run_data_falls_back_only_for_columns_that_vanished() -> None:
    refs = _wired_graph(pl.DataFrame({"a": [1], "b": [2]}).lazy())
    content = refs["graph"].content
    content.x_column = "b"
    content.y_column = "a"

    content.after_execution(
        {content.variable_name: pl.DataFrame({"b2": [3], "a": [4]}).lazy()}
    )

    assert content.x_column == "b2"
    assert content.y_column == "a"


def test_saved_column_follows_an_upstream_rename() -> None:
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    scene = window.scene
    stub = _Stub(scene, inputs=[], outputs=[3])
    stub._df, stub._var = pl.DataFrame({"a": [1], "b": [2]}).lazy(), "var_up"
    stub.markDirty(True)

    select_cls = get_class_from_opcode(PreparationNodes.SELECT, NodeTypes.PREPARATION)
    select = select_cls(scene)
    Edge(scene, stub.outputs[0], select.inputs[0])
    select.eval()
    APP.processEvents()
    _rename_headless(select.content, {"b": "b2"})

    graph = _graph_node(scene)
    Edge(scene, select.outputs[0], graph.inputs[0])
    graph.content.x_column = "b"
    graph.content.y_column = "a"
    graph.eval()
    APP.processEvents()

    assert graph.content.x_column == "b2"


def test_combo_labels_map_to_stored_values() -> None:
    refs = _wired_graph(pl.DataFrame({"a": [1]}).lazy())
    content = refs["graph"].content

    content.on_graph_type_changed("Bar")
    content.on_aggregation_changed("Mean")
    content.on_color_column_changed("(none)")
    content.on_color_column_changed("a")

    assert content.graph_type == "bar"
    assert content.aggregation == "mean"
    assert content.color_column == "a"

    content.on_color_column_changed("(none)")
    assert content.color_column == ""


def test_changing_type_leaves_an_auto_aggregation_auto() -> None:
    refs = _wired_graph(pl.DataFrame({"a": [1]}).lazy())
    content = refs["graph"].content

    content.on_graph_type_changed("Bar")

    # "" means "the chart type's default", resolved at build time.
    assert content.aggregation == ""


def test_startup_import_sweep_keeps_the_chart_backend_out() -> None:
    """The nodes package sweeps every module it is not told to skip.

    pyqtgraph and matplotlib are only needed when a chart window opens; if the
    sweep imports them, every launch pays for them. A subprocess keeps this
    independent of what the rest of the suite has already imported.
    """
    src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
    code = (
        "import sys;"
        f"sys.path.insert(0, {src!r});"
        "import trigger_designer.qt.widgets.nodes;"
        "leaked = ["
        "name for name in ('pyqtgraph', 'matplotlib') if name in sys.modules"
        "];"
        "assert not leaked, f'imported during the startup sweep: {leaked}'"
    )
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
