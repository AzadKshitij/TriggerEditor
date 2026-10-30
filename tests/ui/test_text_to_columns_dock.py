"""Text to Columns dock: controls, visibility, undo/redo, .tds round trip."""

from __future__ import annotations

import orjson
import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QCheckBox, QLineEdit, QSpinBox

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.common import ColumnPicker


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


FRAME = pl.DataFrame({"id": [1, 2], "acct": ["a-b-c", "d"], "amt": [1.5, 2.5]}).lazy()


def _node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, FRAME)
    cls = get_class_from_opcode(PreparationNodes.TEXT_TO_COLUMNS, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, dock


def test_dock_controls_and_text_only_column_picker(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    for key in (
        "column",
        "split_mode",
        "pattern",
        "output",
        "max_splits",
        "names",
        "trim",
        "keep_original",
    ):
        assert key in content._widgets, key
    picker = content._widgets["column"]
    assert isinstance(picker, ColumnPicker)
    assert picker.column_names() == ["acct"]  # numeric columns are filtered out
    assert isinstance(content._widgets["pattern"], QLineEdit)
    assert isinstance(content._widgets["max_splits"], QSpinBox)
    assert isinstance(content._widgets["trim"], QCheckBox)


def test_visibility_follows_output_mode(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    assert content._rows["names"].isHidden() is False
    assert content._rows["row_index_column"].isHidden() is True
    assert content._rows["skip_empty"].isHidden() is True

    content._widgets["output"]._buttons["Rows"].click()
    assert content.settings["output"] == "rows"
    assert content._rows["names"].isHidden() is True
    assert content._rows["row_index_column"].isHidden() is False
    assert content._rows["skip_empty"].isHidden() is False

    window.scene.history.undo()
    assert content.settings["output"] == "columns"
    assert content._rows["names"].isHidden() is False
    assert content._rows["skip_empty"].isHidden() is True


def test_edit_undo_redo_and_live_output(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")

    # Unconfigured: the node reports a missing column.
    assert node.isInvalid()

    content._widgets["column"].set_selected(["acct"], emit=True)
    assert content.settings["column"] == "acct"
    # Edits reach the model at once; the node runs when the dock is left.
    assert node.isInvalid()

    pattern = content._widgets["pattern"]
    pattern.setText("-")
    qtbot.wait(350)
    assert content.settings["pattern"] == "-"
    content.commit_pending_dock_edits()
    assert not node.isInvalid()
    live = node.value[0]["data"].collect()
    assert live.columns == ["id", "acct", "amt", "acct_1", "acct_2", "acct_3"]
    assert live["acct_3"].to_list() == ["c", None]
    assert live["acct_2"].to_list() == ["b", None]

    assert history.canUndo()
    history.undo()
    assert content.settings["pattern"] == ","
    assert content._widgets["pattern"] is pattern
    assert pattern.text() == ","
    history.redo()
    assert content.settings["pattern"] == "-"
    assert pattern.text() == "-"


def test_max_splits_is_one_undo_step(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    spin = content._widgets["max_splits"]
    spin.setValue(5)
    qtbot.wait(350)
    assert content.settings["max_splits"] == 5
    history.undo()
    assert content.settings["max_splits"] == 2
    assert spin.value() == 2


def test_regex_that_matches_nothing_marks_node_invalid(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    content._widgets["column"].set_selected(["acct"], emit=True)
    content._widgets["split_mode"]._buttons["Regex"].click()
    content._widgets["pattern"].setText(r"\s*")
    qtbot.wait(350)
    content.commit_pending_dock_edits()
    assert node.isInvalid()
    content._widgets["pattern"].setText(r"\s+")
    qtbot.wait(350)
    content.commit_pending_dock_edits()
    assert not node.isInvalid()


def test_tds_round_trip_keeps_op_id_and_settings(qtbot, tmp_path) -> None:
    window, node, _dock = _node(qtbot)
    node.content.settings.update(
        {
            "column": "acct",
            "pattern": "-",
            "output": "rows",
            "max_splits": 0,
            "row_index_column": "n",
            "skip_empty": True,
            "trim": False,
        }
    )
    path = tmp_path / "ttc.tds"
    window.scene.saveToFile(str(path))
    saved = orjson.loads(path.read_bytes())
    ops = [item.get("op") for item in saved["nodes"]]
    assert "preparation.text_to_columns" in ops

    other = TriggerSubWindow()
    qtbot.addWidget(other)
    other.scene.loadFromFile(str(path))
    (loaded,) = [n for n in other.getAllNodes() if n.title == "Text to Columns"]
    for key, value in node.content.settings.items():
        assert loaded.content.settings[key] == value, key
    assert type(loaded).node_code is PreparationNodes.TEXT_TO_COLUMNS
